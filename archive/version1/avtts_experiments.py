#!/usr/bin/env python3
"""
avtts_experiments.py
--------------------
Runnable harness for the two GATING experiments of the AV-TTS paper:

  E1  ORACLE HEADROOM (positive control, run first)
      Does candidate selection have any headroom? Compare the base prediction
      to an oracle that selects the candidate with the best Dice-against-GT.
      Labels are used ONLY by the oracle and for evaluation, never by the method.
      If oracle headroom is ~0 -> STOP, there is no paper. (See runbook rule 1.)

  E2  SOUNDNESS ISOLATION
      Is it SOUNDNESS that captures the headroom, not just having many candidates?
      Compare four selectors on the SAME candidate sets:
        base | entropy (unsound proxy) | anatomy verifier (ours) | oracle (upper bound)
      Expected: anatomy >> entropy; entropy may not beat base. (Thesis of the paper.)

WHAT YOU MUST PLUG IN FOR REAL RUNS (search for "TODO: REAL DATA"):
  - load_cases(dataset, split): yield Case objects from your data.
  - generate_candidates(image, model): return candidate masks + an entropy/confidence
    signal, using YOUR frozen segmenter with test-time augmentation / MC-dropout.
  - pick the verifier for each dataset (single_blob / containment / annulus).

This file RUNS AS-IS on synthetic data (no downloads) so you can verify the
harness behaves correctly before wiring in your model:  python3 avtts_experiments.py

Integrity: this computes metrics from inputs. The synthetic generator demonstrates
the EXPECTED behavior; it is not, and must not be reported as, a paper result.
"""

from dataclasses import dataclass, field
from typing import Callable, List
import numpy as np

import avtts_analysis as av  # verified verifiers, select_best, dice, bootstrap_ci

try:
    from scipy.stats import wilcoxon
    _HAVE_SCIPY = True
except Exception:
    _HAVE_SCIPY = False


# ----------------------------------------------------------------------
# data structures
# ----------------------------------------------------------------------
@dataclass
class Case:
    """One test image's worth of material.
    candidates[0] is ALWAYS the base prediction y0 (unperturbed model output)."""
    gt: np.ndarray                      # ground-truth mask (eval/oracle only)
    candidates: List[np.ndarray]        # candidate masks, candidates[0] == base y0
    entropy: List[float]                # per-candidate predictive entropy (lower = more confident)
    verifier: Callable[[np.ndarray], float] = field(default=av.verifier_single_blob)


# ----------------------------------------------------------------------
# selectors  (each returns an index into case.candidates)
# ----------------------------------------------------------------------
def sel_base(case: Case) -> int:
    return 0

def sel_entropy(case: Case) -> int:
    # unsound proxy: pick the most confident (lowest entropy) candidate
    return int(np.argmin(case.entropy))

def sel_anatomy(case: Case) -> int:
    # ours: pick the highest sound-verifier score, safeguarded toward base (Prop. 1)
    idx, _ = av.select_best(case.candidates, case.verifier, base_index=0)
    return idx

def sel_oracle(case: Case) -> int:
    # upper bound: pick the candidate with the best Dice-against-GT (uses labels)
    return int(np.argmax([av.dice(c, case.gt) for c in case.candidates]))


# ----------------------------------------------------------------------
# experiments
# ----------------------------------------------------------------------
def _dice_of(selector, cases):
    return np.array([av.dice(c.candidates[selector(c)], c.gt) for c in cases], dtype=float)

def run_e1(cases):
    """E1: oracle headroom over base. Returns per-case (base, oracle, headroom)."""
    base = _dice_of(sel_base, cases)
    orac = _dice_of(sel_oracle, cases)
    head = orac - base
    return base, orac, head

def run_e2(cases):
    """E2: Dice per selector + fraction of oracle headroom recovered."""
    out = {name: _dice_of(fn, cases)
           for name, fn in [("base", sel_base), ("entropy", sel_entropy),
                            ("anatomy", sel_anatomy), ("oracle", sel_oracle)]}
    base, orac = out["base"], out["oracle"]
    headroom = orac - base
    usable = headroom > 1e-6                      # cases where selection can help at all
    rec = {}
    for name in ("entropy", "anatomy", "oracle"):
        frac = np.where(usable, (out[name] - base) / np.where(usable, headroom, 1.0), 0.0)
        rec[name] = float(np.mean(frac[usable])) if usable.any() else float("nan")
    return out, rec


def _sig(a, b):
    """Wilcoxon signed-rank p-value for paired a vs b (a=anatomy, b=entropy)."""
    if not _HAVE_SCIPY:
        return float("nan")
    d = a - b
    if np.allclose(d, 0):
        return 1.0
    try:
        return float(wilcoxon(a, b, zero_method="wilcox").pvalue)
    except ValueError:
        return float("nan")


# ----------------------------------------------------------------------
# SYNTHETIC dataset  (so the harness runs end-to-end here)
# Replace this whole section with real data + model for actual experiments.
# ----------------------------------------------------------------------
def _make_synthetic_case(rng):
    """Build one case under the paper's stated assumptions (clearly labeled synthetic):
      - the base y0 is degraded by shift and structurally invalid;
      - valid candidates have high Dice; invalid candidates have LOW Dice
        (structural violations co-occur with gross errors, Assumption 1's rationale);
      - entropy is miscalibrated: some invalid, low-Dice candidates are highly
        confident (low entropy), so entropy selection is misled.
    This is a behavior demonstration, NOT a paper result."""
    gt = av.disk(size=64, cx=32, cy=32, r=14)

    cands, ents = [], []

    # index 0 = base y0: shifted ~7px AND a stray component -> invalid, low-ish Dice
    base = av.add_speck(av.disk(cx=37, cy=37, r=14), cx=9, cy=9, r=4)
    cands.append(base); ents.append(rng.uniform(0.25, 0.38))

    # valid, high-Dice candidates near GT (these should be selected)
    for _ in range(3):
        m = av.disk(cx=32 + rng.integers(-2, 3), cy=32 + rng.integers(-2, 3), r=14)
        cands.append(m); ents.append(rng.uniform(0.40, 0.60))   # good but not most-confident

    # invalid, LOW-Dice distractors that are CONFIDENT (the trap for entropy)
    trap_a = av.add_speck(av.disk(cx=32, cy=32, r=9), cx=8, cy=8, r=4)   # too small + speck
    cands.append(trap_a); ents.append(rng.uniform(0.04, 0.16))
    trap_b = av.punch_hole(av.disk(cx=40, cy=32, r=14), r=6)             # shifted + hole
    cands.append(trap_b); ents.append(rng.uniform(0.05, 0.17))

    return Case(gt=gt, candidates=cands, entropy=ents, verifier=av.verifier_single_blob)

def synthetic_dataset(n_cases=120, seed=0):
    rng = np.random.default_rng(seed)
    return [_make_synthetic_case(rng) for _ in range(n_cases)]


# ----------------------------------------------------------------------
# TODO: REAL DATA  (stubs to implement for actual experiments)
# ----------------------------------------------------------------------
def load_cases(dataset: str, split: str):
    """Yield Case objects from a real benchmark (prostate / optic / cardiac).
    For each test image: run your FROZEN segmenter with N label-free perturbations
    (flips, multi-scale, gamma, MC-dropout) to get candidate masks; set
    candidates[0] to the unperturbed prediction; record per-candidate predictive
    entropy; choose the verifier for the dataset. Then evaluate with the same code."""
    raise NotImplementedError(
        "Wire in your model + dataset here. Return a list of Case objects. "
        "Use av.verifier_single_blob (prostate), av.verifier_containment "
        "(optic cup/disc), or an annulus verifier (cardiac).")


# ----------------------------------------------------------------------
# reporting
# ----------------------------------------------------------------------
def _ms(x):
    return f"{np.mean(x):.4f}+/-{np.std(x):.4f}"

def main(seeds=(0, 1, 2), n_cases=120):
    print("=" * 70)
    print("AV-TTS gating experiments  (SYNTHETIC data: behavior check, NOT results)")
    print("=" * 70)

    e1_head, e2_dice, e2_rec, sig_ae = [], {k: [] for k in
        ("base", "entropy", "anatomy", "oracle")}, {k: [] for k in ("entropy", "anatomy", "oracle")}, []

    for s in seeds:
        cases = synthetic_dataset(n_cases=n_cases, seed=s)
        base, orac, head = run_e1(cases)
        e1_head.append(np.mean(head))
        out, rec = run_e2(cases)
        for k in e2_dice: e2_dice[k].append(np.mean(out[k]))
        for k in e2_rec:  e2_rec[k].append(rec[k])
        sig_ae.append(_sig(out["anatomy"], out["entropy"]))

    # E1
    print("\n[E1] ORACLE HEADROOM (run first)")
    base, orac, head = run_e1(synthetic_dataset(n_cases=n_cases, seed=seeds[0]))
    m, lo, hi = av.bootstrap_ci(head)
    print(f"  base Dice   : {np.mean(base):.4f}")
    print(f"  oracle Dice : {np.mean(orac):.4f}")
    print(f"  headroom    : {np.mean(e1_head):.4f}+/-{np.std(e1_head):.4f}  "
          f"(seed-0 95% CI [{lo:.4f}, {hi:.4f}])")
    print("  GATE: if headroom ~ 0 -> STOP and re-scope. Here it is clearly positive.")

    # E2
    print("\n[E2] SOUNDNESS ISOLATION (mean Dice over seeds)")
    for k in ("base", "entropy", "anatomy", "oracle"):
        print(f"  {k:8s}: {_ms(e2_dice[k])}")
    print("  fraction of oracle headroom recovered:")
    for k in ("entropy", "anatomy", "oracle"):
        print(f"    {k:8s}: {np.nanmean(e2_rec[k]):+.3f}")
    print(f"  Wilcoxon anatomy vs entropy p-value (per seed): "
          f"{['%.1e' % p for p in sig_ae]}")
    print("  EXPECTED: anatomy recovers most headroom and >> entropy; "
          "entropy may not beat base.")
    print("\nHarness OK. Swap synthetic_dataset() for load_cases() + your model "
          "to produce real E1/E2 numbers.")


if __name__ == "__main__":
    main()
