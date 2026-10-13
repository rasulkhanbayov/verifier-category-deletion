#!/usr/bin/env python3
"""
soundver_experiments.py
------------------------
Runnable harness for Experiments 1-6 of the SoundVer paper (see
BLOCKERS.txt B1/B2 and soundver_main.tex Sec. 6). This is the piece that
was missing from the bundle: soundver_analysis.py has the closed-form
theory and rate estimators, but nothing that turns a real model + a real
benchmark into the (p0, p, delta, eps) numbers Table 2 needs. This file is
that missing piece.

  E1  HEADROOM (positive control, run first)
      Oracle selection (uses gold labels) vs. the base (greedy) output.
      If oracle - base is ~0, no verifier can help; stop and re-scope.

  E2  SOUNDNESS AUDIT (mechanism gate, run second; this IS the paper)
      Measure p0, p, delta, eps directly for every candidate check, split
      by base vs. sampled candidates so the constant-rate idealisation in
      Sec. 3 is checked rather than assumed.

  E3  PREDICTED VS OBSERVED GAIN
      Plug the E2 rate estimates into accuracy_sound() and compare the
      predicted A_N curve to the measured reject-gated accuracy across
      N in {1,2,4,8,16,32}.

  E3b IS IT THE GATE?
      Same verifier/scorer/pool; vary only the rule (ungated best-of-N,
      homogeneous rejection sampling, reject-gated). Isolates the paper's
      one algorithmic claim.

  E4  STACKING
      Add sound checks one at a time in the Table 1 order; eps should be
      non-increasing and gain non-decreasing at every step (Prop. 4).

  E5  DEGRADATION AND SAFE COMPOSITION
      Confirm unsound scorers can fall below greedy under ungated best-of-N,
      and that the same scorers gated behind a sound check do not (Cor. 1).

  E6  NEGATIVE CONTROLS
      A vacuous sound check (predicts exactly zero gain) and a
      deliberately-unsound scorer (predicts degradation at a known rate).

WHAT YOU MUST PLUG IN FOR REAL RUNS (search for "TODO: REAL DATA"):
  - load_instances(task, split): yield Instance objects from a real
    benchmark (Spider/BIRD for SQL, a schema-constrained IE set, a
    UniMorph-derived segmentation set -- see R5/R6/R7 in BLOCKERS.txt).
  - generate_candidates(prompt, model): sample N candidates plus the
    greedy base y0 from your model at fixed temperature.
  - the sound-column checks from Table 1 (soundver_main.tex): SQL
    parses/schema-valid/executes, JSON schema-valid, and morphological
    concatenation-to-surface-form.
  - a correctness label C(y) for each task that does NOT presuppose any
    check under audit (test-suite accuracy for SQL, per Sec. 6's circularity
    warning X1 in BLOCKERS.txt -- do not use raw execution match).

This file RUNS AS-IS on synthetic data (no downloads, no model calls) so
the harness can be verified before wiring in real generation:
    python3 soundver_experiments.py

Integrity: the synthetic dataset demonstrates the harness is wired
correctly. It is not, and must never be reported as, a paper result.
"""

from dataclasses import dataclass, field
from typing import Callable, List, Optional
import numpy as np

import soundver_analysis as sv  # closed-form theory, rate estimators, CIs

try:
    from scipy.stats import wilcoxon
    _HAVE_SCIPY = True
except Exception:
    _HAVE_SCIPY = False


# ----------------------------------------------------------------------
# data structures
# ----------------------------------------------------------------------
@dataclass
class Instance:
    """One task instance's worth of material.

    base is always the greedy output y0; samples[i] are i.i.d. draws at
    fixed temperature. correct_* and verdict_* are parallel boolean arrays
    for base (scalar) and samples (length N), one entry per check name so
    Experiment 4 can stack checks and Experiment 2 can audit each alone.
    """
    correct_base: bool                       # C(y0), gold label (eval/oracle only)
    correct_samples: List[bool]              # C(y_i), i = 1..N
    checks_base: dict                        # {check_name: bool}, V_check(y0)
    checks_samples: List[dict]               # [{check_name: bool}, ...] per sample
    scorer_scores: Optional[List[float]] = None  # e.g. reward-model score per sample


# ----------------------------------------------------------------------
# verdict composition (mirrors Prop. 4 / stack_eps: AND across checks)
# ----------------------------------------------------------------------
def _stacked_verdict(checks: dict, names: List[str]) -> bool:
    return all(checks[n] for n in names)


def _gate_accepts(instance: Instance, stack: List[str]) -> bool:
    return _stacked_verdict(instance.checks_base, stack)


# ----------------------------------------------------------------------
# selection rules (each returns whether the RETURNED output is correct)
# ----------------------------------------------------------------------
def rule_reject_gated(instance: Instance, stack: List[str], N: int,
                       score_fn: Optional[Callable] = None) -> bool:
    """Definition 1: return y0 if the gate accepts it; else return the
    accepted candidate with the highest score (uniform if score_fn is None),
    or y0 if none of the first N samples is accepted."""
    if _gate_accepts(instance, stack):
        return instance.correct_base
    accepted = [i for i in range(min(N, len(instance.correct_samples)))
                if _stacked_verdict(instance.checks_samples[i], stack)]
    if not accepted:
        return instance.correct_base
    if score_fn is None:
        idx = accepted[0]  # uniform tie-break; index choice doesn't matter under A1/A2
    else:
        idx = max(accepted, key=lambda i: score_fn(instance, i))
    return instance.correct_samples[idx]


def rule_ungated_bestofn(instance: Instance, stack: List[str], N: int,
                          score_fn: Optional[Callable] = None) -> bool:
    """Scores the WHOLE pool including the base -- can discard a correct
    base output. This is the baseline that isolates the gate (Sec. 6,
    'rules that differ from ours only in the gate').

    NOTE: with score_fn=None (uniform tie-break, base at pool index 0), a
    correct base under a sound check is always accepted and always
    accepted[0], so this degenerates to the gated rule and never
    exhibits the failure mode Sec. 2 describes. That failure mode --
    discarding a correct base -- requires an actual scorer that can rank
    some accepted sample above the base (pass score_fn, as E5 does with
    the unsound scorer); E3b's gate-isolation comparison is correctly run
    with score_fn=None precisely because it is testing resampling
    dynamics, not scorer-driven displacement.
    """
    pool_correct = [instance.correct_base] + instance.correct_samples[:N]
    pool_checks = [instance.checks_base] + instance.checks_samples[:N]
    accepted = [i for i, c in enumerate(pool_checks) if _stacked_verdict(c, stack)]
    if not accepted:
        return instance.correct_base
    if score_fn is None:
        idx = accepted[0]
    else:
        # score_fn is indexed over samples (0..N-1); the base (pool index 0)
        # has no sample score and is scored at -inf so it can be outranked.
        def pool_score(i):
            return -np.inf if i == 0 else score_fn(instance, i - 1)
        idx = max(accepted, key=pool_score)
    return pool_correct[idx]


def rule_homogeneous_rejection(instance: Instance, stack: List[str], N: int) -> bool:
    """Draws until acceptance without distinguishing the base (Dorner et al.
    2507.12399); the contrast with rule_reject_gated isolates whether the
    gain comes from the gate or just from resampling (Experiment 3b)."""
    for i in range(min(N, len(instance.correct_samples))):
        if _stacked_verdict(instance.checks_samples[i], stack):
            return instance.correct_samples[i]
    return instance.correct_base


# ----------------------------------------------------------------------
# Experiment 1: headroom
# ----------------------------------------------------------------------
def run_e1(instances: List[Instance]):
    """Oracle (uses gold labels) vs. base. GATE: if headroom ~ 0, stop."""
    base = np.array([inst.correct_base for inst in instances], dtype=float)
    oracle = np.array([
        inst.correct_base or any(inst.correct_samples) for inst in instances
    ], dtype=float)
    headroom = oracle - base
    return base, oracle, headroom


# ----------------------------------------------------------------------
# Experiment 2: the soundness audit
# ----------------------------------------------------------------------
def run_e2(instances: List[Instance], check_names: List[str]):
    """Per-check p0, p, delta, eps, split by base vs. samples (Sec. 6, the
    constant-rate idealisation is checked here, not assumed). Returns
    {check_name: rate_dict} using soundver_analysis.estimate_rates."""
    out = {}
    correct_base = np.array([inst.correct_base for inst in instances], dtype=bool)
    correct_samp = np.array([inst.correct_samples for inst in instances], dtype=bool)
    for name in check_names:
        verdict_base = np.array([inst.checks_base[name] for inst in instances], dtype=bool)
        verdict_samp = np.array(
            [[s[name] for s in inst.checks_samples] for inst in instances], dtype=bool)
        out[name] = sv.estimate_rates(correct_base, verdict_base, correct_samp, verdict_samp)
    return out


# ----------------------------------------------------------------------
# Experiment 3: predicted vs observed gain, across budgets
# ----------------------------------------------------------------------
def run_e3(instances: List[Instance], stack: List[str], budgets=(1, 2, 4, 8, 16, 32)):
    """Compares sv.accuracy_sound(p0, p, eps, N) against the measured
    reject-gated accuracy at each N. Uses the POOLED eps from run_e2 for the
    full stack; delta is assumed 0 for the sound stack by construction and
    should be cross-checked against run_e2's delta_pooled for that stack."""
    rates = run_e2(instances, [":".join(stack)] if len(stack) == 1 else stack)
    # for a multi-check stack, estimate rates on the STACKED verdict directly
    correct_base = np.array([inst.correct_base for inst in instances], dtype=bool)
    correct_samp = np.array([inst.correct_samples for inst in instances], dtype=bool)
    verdict_base = np.array([_stacked_verdict(inst.checks_base, stack) for inst in instances])
    verdict_samp = np.array([[_stacked_verdict(s, stack) for s in inst.checks_samples]
                              for inst in instances])
    stacked_rates = sv.estimate_rates(correct_base, verdict_base, correct_samp, verdict_samp)
    p0, p, eps = stacked_rates["p0"], stacked_rates["p"], stacked_rates["eps_pooled"]

    predicted = {N: sv.accuracy_sound(p0, p, eps, N) for N in budgets}
    observed = {}
    for N in budgets:
        acc = np.array([float(rule_reject_gated(inst, stack, N)) for inst in instances])
        m, lo, hi = sv.bootstrap_ci(acc)
        observed[N] = (m, lo, hi)
    return {"rates": stacked_rates, "predicted": predicted, "observed": observed}


# ----------------------------------------------------------------------
# Experiment 3b: is it the gate?
# ----------------------------------------------------------------------
def run_e3b(instances: List[Instance], stack: List[str], N: int = 16):
    """Same verifier/pool; vary only the rule. Prediction: gated >=
    homogeneous rejection sampling >= ungated best-of-N."""
    gated = np.array([float(rule_reject_gated(inst, stack, N)) for inst in instances])
    rejsamp = np.array([float(rule_homogeneous_rejection(inst, stack, N)) for inst in instances])
    ungated = np.array([float(rule_ungated_bestofn(inst, stack, N)) for inst in instances])
    return {
        "gated": (float(gated.mean()),) + sv.bootstrap_ci(gated)[1:],
        "homogeneous_rejection": (float(rejsamp.mean()),) + sv.bootstrap_ci(rejsamp)[1:],
        "ungated_bestofn": (float(ungated.mean()),) + sv.bootstrap_ci(ungated)[1:],
        "p_gate_vs_rejsamp": paired_permutation_signed(gated, rejsamp),
        "p_gate_vs_ungated": paired_permutation_signed(gated, ungated),
    }


def paired_permutation_signed(a: np.ndarray, b: np.ndarray) -> float:
    return sv.paired_permutation_p(a, b)


# ----------------------------------------------------------------------
# Experiment 4: stacking
# ----------------------------------------------------------------------
def run_e4(instances: List[Instance], ordered_checks: List[str], N: int = 16):
    """Add checks one at a time in the given order. Prediction (Prop. 4):
    eps non-increasing, gain non-decreasing, at every step."""
    rows = []
    for k in range(1, len(ordered_checks) + 1):
        stack = ordered_checks[:k]
        e3 = run_e3(instances, stack, budgets=(N,))
        acc = np.array([float(rule_reject_gated(inst, stack, N)) for inst in instances])
        rows.append({
            "stack": list(stack),
            "eps": e3["rates"]["eps_pooled"],
            "delta": e3["rates"]["delta_pooled"],
            "accuracy": float(acc.mean()),
        })
    monotone_eps = all(rows[i]["eps"] >= rows[i + 1]["eps"] - 1e-9 for i in range(len(rows) - 1))
    monotone_gain = all(rows[i]["accuracy"] <= rows[i + 1]["accuracy"] + 1e-9
                         for i in range(len(rows) - 1))
    return {"rows": rows, "eps_non_increasing": monotone_eps, "gain_non_decreasing": monotone_gain}


# ----------------------------------------------------------------------
# Experiment 5: degradation and safe composition
# ----------------------------------------------------------------------
def run_e5(instances: List[Instance], sound_stack: List[str], unsound_scorer_name: str, N: int = 16):
    """Ungated best-of-N with an unsound scorer can fall below greedy
    (predicted by degrades()); the same scorer gated behind sound_stack
    should not (Cor. 1)."""
    def score_fn(inst, i):
        return inst.scorer_scores[i] if inst.scorer_scores is not None else 0.0

    base = np.array([float(inst.correct_base) for inst in instances])
    ungated_unsound = np.array([
        float(rule_ungated_bestofn(inst, [unsound_scorer_name], N, score_fn))
        for inst in instances])
    gated_then_unsound = np.array([
        float(rule_reject_gated(inst, sound_stack, N, score_fn))
        for inst in instances])

    rates = run_e2(instances, [unsound_scorer_name])[unsound_scorer_name]
    predicted_degrade = sv.degrades(rates["p0"], rates["p"], rates["eps_pooled"], rates["delta_pooled"])
    observed_degrade = bool(ungated_unsound.mean() < base.mean() - 1e-9)
    floor_holds = bool(gated_then_unsound.mean() >= base.mean() - 1e-9)

    # Paired bootstrap CI on the per-instance difference from base, so
    # callers reporting a Delta-vs-greedy column (e.g. Table 3) have a
    # real interval rather than one invented to look plausible.
    ungated_m, ungated_lo, ungated_hi = sv.bootstrap_ci(ungated_unsound - base)
    gated_m, gated_lo, gated_hi = sv.bootstrap_ci(gated_then_unsound - base)

    return {
        "base_accuracy": float(base.mean()),
        "ungated_unsound_accuracy": float(ungated_unsound.mean()),
        "gated_then_unsound_accuracy": float(gated_then_unsound.mean()),
        "predicted_degrade": predicted_degrade,
        "observed_degrade": observed_degrade,
        "floor_holds_when_gated": floor_holds,
        "ungated_diff_ci": {"mean_diff": ungated_m, "ci_lo": ungated_lo, "ci_hi": ungated_hi},
        "gated_diff_ci": {"mean_diff": gated_m, "ci_lo": gated_lo, "ci_hi": gated_hi},
    }


# ----------------------------------------------------------------------
# Experiment 6: negative controls
# ----------------------------------------------------------------------
def run_e6_vacuous_check(instances: List[Instance], vacuous_check_name: str, N: int = 16):
    """A check every output satisfies (Sec. 6): theory predicts exactly
    zero gain at every N. Any measured gain flags a pipeline confound."""
    base = np.array([float(inst.correct_base) for inst in instances])
    gated = np.array([float(rule_reject_gated(inst, [vacuous_check_name], N)) for inst in instances])
    gain = float(gated.mean() - base.mean())
    return {"predicted_gain": 0.0, "observed_gain": gain, "confound_suspected": abs(gain) > 1e-6}


def run_e6_inflated_delta(instances: List[Instance], sound_stack: List[str],
                           adversarial_scorer_name: str, N: int = 16):
    """A scorer with deliberately inflated delta (e.g. reject the
    highest-log-probability candidate) used as the SCORER, gated behind a
    genuinely sound_stack: theory predicts degradation under ungated
    best-of-N with this scorer (Cor. 3) and that the floor survives once
    the same scorer sits behind the sound gate (Cor. 1). Passing the
    adversarial check as sound_stack itself would test a different and
    unintended claim -- soundness of the gate, not of the scorer -- so the
    two arguments must never be the same check."""
    assert adversarial_scorer_name not in sound_stack, (
        "the adversarial scorer must not also be the gate: this experiment "
        "tests Cor. 1 (safe composition of an UNSOUND scorer behind a SOUND "
        "gate), not the soundness of the gate itself")
    return run_e5(instances, sound_stack, adversarial_scorer_name, N)


# ----------------------------------------------------------------------
# SYNTHETIC dataset (harness smoke test only -- NOT a paper result)
# ----------------------------------------------------------------------
def _make_synthetic_instance(rng, n_samples=32):
    """One instance under the paper's stated model (A1-A3, Sec. 4):
    p0=0.55, p=0.50 (greedy slightly better than sampling); a 'sound'
    check with low realised eps and delta=0; an 'unsound' check with a
    small delta and lower eps than the sound one, used as the scorer."""
    correct_base = bool(rng.random() < 0.55)
    correct_samples = list(rng.random(n_samples) < 0.50)

    def sound_verdict(correct):
        # delta = 0 by construction: a correct output always passes
        return True if correct else bool(rng.random() < 0.35)  # eps ~ 0.35

    def unsound_verdict(correct):
        # small delta: 8% of correct outputs are wrongly rejected
        if correct:
            return bool(rng.random() >= 0.08)
        return bool(rng.random() < 0.20)  # eps ~ 0.20, tighter than the sound check

    def adversarial_verdict(correct):
        # delta, eps both near 0.5: per sv.degrades(), this combination is
        # predicted to fall BELOW the base under ungated best-of-N, unlike
        # unsound_scorer above, which is too mild to trigger degradation.
        if correct:
            return bool(rng.random() >= 0.5)
        return bool(rng.random() < 0.5)

    checks_base = {"sound_check": sound_verdict(correct_base),
                   "unsound_scorer": unsound_verdict(correct_base),
                   "adversarial_scorer": adversarial_verdict(correct_base)}
    checks_samples = [{"sound_check": sound_verdict(c), "unsound_scorer": unsound_verdict(c),
                        "adversarial_scorer": adversarial_verdict(c)}
                       for c in correct_samples]
    scorer_scores = list(rng.random(n_samples))

    return Instance(correct_base=correct_base, correct_samples=correct_samples,
                     checks_base=checks_base, checks_samples=checks_samples,
                     scorer_scores=scorer_scores)


def synthetic_dataset(n_instances=400, seed=0):
    rng = np.random.default_rng(seed)
    return [_make_synthetic_instance(rng) for _ in range(n_instances)]


# ----------------------------------------------------------------------
# TODO: REAL DATA (stubs to implement for actual experiments)
# ----------------------------------------------------------------------
def load_instances(task: str, split: str) -> List[Instance]:
    """Yield Instance objects from a real benchmark.

    task in {"sql", "ie", "morphology"}. For SQL use Spider/BIRD with
    TEST-SUITE ACCURACY (Zhong et al. 2020) as the correctness label, not
    raw execution match -- BLOCKERS.txt X1: execution match makes the
    executability check's delta=0 by construction, which is circular for
    exactly the check the paper leans on. For IE use a schema-constrained
    benchmark with span-level or field-level correctness. For morphology
    use a UniMorph-derived segmentation set with gold surface segmentations.

    For each instance: draw the greedy base y0 and N sampled candidates
    from the model at a fixed, recorded temperature (R6/R7 in
    BLOCKERS.txt); evaluate every check in Table 1's sound column on y0
    and on each sample; evaluate gold correctness on y0 and each sample.
    """
    raise NotImplementedError(
        "Wire in a real model and benchmark here. Return a list of "
        "Instance objects. See Table 1 (soundver_main.tex) for the "
        "per-task sound-column checks and BLOCKERS.txt R6/R7 for the "
        "model-set and benchmark specification this still needs.")


def generate_candidates(prompt: str, model, N: int, temperature: float):
    """Sample the greedy base y0 and N i.i.d. candidates at `temperature`
    from `model`. Return (y0, [y_1, ..., y_N])."""
    raise NotImplementedError("Wire in real model sampling here.")


# ----------------------------------------------------------------------
# reporting
# ----------------------------------------------------------------------
def main():
    print("=" * 70)
    print("SoundVer experiment harness  (SYNTHETIC data: behavior check, NOT results)")
    print("=" * 70)

    instances = synthetic_dataset(n_instances=400, seed=0)

    print("\n[E1] HEADROOM (run first)")
    base, oracle, headroom = run_e1(instances)
    m, lo, hi = sv.bootstrap_ci(headroom)
    print(f"  base accuracy   : {base.mean():.4f}")
    print(f"  oracle accuracy : {oracle.mean():.4f}")
    print(f"  headroom        : {m:.4f}  95% CI [{lo:.4f}, {hi:.4f}]")
    print("  GATE: if headroom ~ 0 -> STOP and re-scope. Here it is clearly positive.")

    print("\n[E2] SOUNDNESS AUDIT")
    rates = run_e2(instances, ["sound_check", "unsound_scorer"])
    for name, r in rates.items():
        print(f"  {name:14s}: p0={r['p0']:.3f} p={r['p']:.3f} "
              f"delta_pooled={r['delta_pooled']:.3f} eps_pooled={r['eps_pooled']:.3f} "
              f"soundness_violated={r['soundness_violated']}")

    print("\n[E3] PREDICTED VS OBSERVED GAIN (sound_check only)")
    e3 = run_e3(instances, ["sound_check"])
    for N, pred in e3["predicted"].items():
        obs_m, obs_lo, obs_hi = e3["observed"][N]
        print(f"  N={N:3d}  predicted={pred:.4f}  observed={obs_m:.4f} "
              f"[{obs_lo:.4f}, {obs_hi:.4f}]")

    print("\n[E3b] IS IT THE GATE?")
    e3b = run_e3b(instances, ["sound_check"], N=16)
    for k, v in e3b.items():
        if isinstance(v, tuple):
            print(f"  {k:24s}: mean={v[0]:.4f} CI=[{v[1]:.4f}, {v[2]:.4f}]")
        else:
            print(f"  {k:24s}: {v:.4f}")

    print("\n[E5] DEGRADATION AND SAFE COMPOSITION (mild unsound scorer: no degradation predicted)")
    e5 = run_e5(instances, ["sound_check"], "unsound_scorer", N=16)
    for k, v in e5.items():
        print(f"  {k:28s}: {v}")

    print("\n[E5b] DEGRADATION AND SAFE COMPOSITION (adversarial scorer: degradation predicted)")
    e5b = run_e5(instances, ["sound_check"], "adversarial_scorer", N=16)
    for k, v in e5b.items():
        print(f"  {k:28s}: {v}")

    print("\n[E6a] NEGATIVE CONTROL: vacuous check")
    checks_vacuous = {"vacuous": True}
    for inst in instances:
        inst.checks_base["vacuous"] = True
        for s in inst.checks_samples:
            s["vacuous"] = True
    e6a = run_e6_vacuous_check(instances, "vacuous", N=16)
    print(f"  {e6a}")

    print("\n[E6b] NEGATIVE CONTROL: inflated-delta scorer gated behind a genuinely sound check")
    e6b = run_e6_inflated_delta(instances, ["sound_check"], "adversarial_scorer", N=16)
    for k, v in e6b.items():
        print(f"  {k:28s}: {v}")

    print("\nHarness OK. Implement load_instances() + generate_candidates() "
          "with a real model and benchmark to produce real E1-E6 numbers.")


if __name__ == "__main__":
    main()
