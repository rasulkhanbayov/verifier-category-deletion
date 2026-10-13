"""
soundver.rates -- estimate every quantity the paper reports, from records only.

This is the module that closes B2, B3, B6 and B7. Nothing here reads a summary
file, a cached table, or a previous pass's output. Every number is recomputed
from per-instance records, which is the only way the contradictions between
Table 2 and Table 4 can be adjudicated.
"""
from __future__ import annotations
import numpy as np
from dataclasses import dataclass
from typing import Sequence
from .records import Record, CHECKS


@dataclass
class Rates:
    task: str
    model: str
    subset: tuple
    n_base: int
    n_cand: int
    p0: float
    p: float
    delta: float
    eps: float
    delta_base: float          # measured on the base output alone
    delta_cand: float          # measured on the samples alone
    eps_base: float
    eps_cand: float

    @property
    def q(self) -> float:
        return self.p * (1 - self.delta) + (1 - self.p) * self.eps

    @property
    def r(self) -> float:
        return self.p * (1 - self.delta) / self.q if self.q > 0 else 0.0

    @property
    def sound(self) -> bool:
        return self.delta == 0.0

    def ceiling_pts(self) -> float:
        """Cor. 3(b). Only meaningful when sound; returns nan otherwise."""
        if not self.sound:
            return float("nan")
        q = self.p + (1 - self.p) * self.eps
        return 0.0 if q <= 0 else 100 * (1 - self.p0) * (1 - self.eps) * self.p / q

    def gain_pts(self, N: int) -> float:
        """Cor. 2 at finite N, in accuracy points."""
        if not self.sound:
            return float("nan")
        q = self.p + (1 - self.p) * self.eps
        if q <= 0:
            return 0.0
        return 100 * (1 - self.p0) * (1 - self.eps) * (1 - (1 - q) ** N) * self.p / q


def _rate(num: int, den: int) -> float:
    return float("nan") if den == 0 else num / den


def estimate(recs: Sequence[Record], subset: Sequence[str] | None = None,
             seed: int | None = None, prompt_id: str = "base") -> Rates:
    """
    Estimate p0, p, delta, epsilon for one (task, model) cell under one subset
    of the check stack. delta and eps are reported pooled AND split by
    base/sample, because Appendix A claims the split matters and the paper
    should be able to show it.
    """
    if not recs:
        raise ValueError("no records")
    task = recs[0].task
    model = recs[0].model
    subset = tuple(subset) if subset else tuple(CHECKS[task])
    recs = [r for r in recs
            if r.prompt_id == prompt_id and (seed is None or r.seed == seed)]
    if not recs:
        raise ValueError(f"no records for prompt={prompt_id!r} seed={seed!r}")

    base = [r for r in recs if r.is_base]
    cand = [r for r in recs if not r.is_base]

    def dc(rs):
        cor = [r for r in rs if r.correct]
        inc = [r for r in rs if not r.correct]
        d = _rate(sum(1 for r in cor if not r.accepted_by(subset)), len(cor))
        e = _rate(sum(1 for r in inc if r.accepted_by(subset)), len(inc))
        return d, e

    d_b, e_b = dc(base)
    d_c, e_c = dc(cand)
    d_all, e_all = dc(base + cand)

    return Rates(
        task=task, model=model, subset=subset,
        n_base=len(base), n_cand=len(cand),
        p0=_rate(sum(1 for r in base if r.correct), len(base)),
        p=_rate(sum(1 for r in cand if r.correct), len(cand)),
        delta=0.0 if (d_all == 0 or np.isnan(d_all)) and d_all == 0 else d_all,
        eps=e_all, delta_base=d_b, delta_cand=d_c, eps_base=e_b, eps_cand=e_c)


# ----------------------------------------------------------------- selection

def simulate_rules(recs: Sequence[Record], subset: Sequence[str],
                   N: int, scorer: str = "score",
                   rng: np.random.Generator | None = None) -> dict:
    """
    Run the three rules on the SAME candidate pool, per instance, so the
    comparison isolates the rule. Returns per-instance correctness arrays,
    which is what B6 needs: a zero-width paired bootstrap CI is only
    interpretable once you can see whether the gate ever changed an outcome.
    """
    rng = rng or np.random.default_rng(0)
    by_inst: dict[str, list[Record]] = {}
    for r in recs:
        by_inst.setdefault(r.instance_id, []).append(r)

    gated, homog, ungated, base_acc, gate_fired = [], [], [], [], []
    for iid, rs in sorted(by_inst.items()):
        b = next((r for r in rs if r.is_base), None)
        cs = [r for r in rs if not r.is_base][:N]
        if b is None or not cs:
            continue
        base_acc.append(b.correct)
        acc = [r for r in cs if r.accepted_by(subset)]

        # reject-gated: return base if it passes, else best accepted candidate
        if b.accepted_by(subset):
            gated.append(b.correct); gate_fired.append(False)
        else:
            gate_fired.append(True)
            gated.append(max(acc, key=lambda r: r.score or 0.0).correct
                         if acc else b.correct)

        # homogeneous rejection sampling: no distinguished first draw
        homog.append(max(acc, key=lambda r: r.score or 0.0).correct
                     if acc else rng.choice(cs).correct)

        # ungated best-of-N over the pool INCLUDING the base
        pool = cs + [b]
        ungated.append(max(pool, key=lambda r: r.score or 0.0).correct)

    return {"base": np.array(base_acc), "gated": np.array(gated),
            "homogeneous": np.array(homog), "ungated": np.array(ungated),
            "gate_fired": np.array(gate_fired)}


# ---------------------------------------------------------------------- E5
def degradation(recs: Sequence[Record], sound_stack: Sequence[str], N: int,
               reject_percentile: float = 25.0) -> dict:
    """
    E5: a deliberately UNSOUND scorer -- mean log-probability of the
    completion, with the bottom `reject_percentile` of an instance's own
    candidate pool rejected (\S{Findings}, paper's own E5 design) -- run
    both ungated (ranked among the candidates the confidence gate alone
    accepts) and gated behind `sound_stack` (ranked by confidence only
    among candidates the SOUND stack accepts). Cor.~\\ref{cor:degrade}
    predicts the ungated rule can degrade below the greedy base; the
    corresponding proposition predicts the gated rule cannot.

    Requires `Record.score` to be a real per-candidate log-probability
    (generate.py's --want-logprobs); records with score=None cannot run
    this experiment and are skipped per instance (not silently zeroed).
    """
    by_inst: dict[str, list[Record]] = {}
    for r in recs:
        by_inst.setdefault(r.instance_id, []).append(r)

    base_acc, ungated_unsound, gated_then_unsound = [], [], []
    skipped_no_score = 0
    for iid, rs in sorted(by_inst.items()):
        b = next((r for r in rs if r.is_base), None)
        cs = [r for r in rs if not r.is_base][:N]
        if b is None or not cs:
            continue
        pool = [b] + cs
        if any(r.score is None for r in pool):
            skipped_no_score += 1
            continue

        scores = [r.score for r in pool]
        threshold = float(np.percentile(scores, reject_percentile))
        confidence_accepted = [r for r in pool if r.score > threshold]

        base_acc.append(b.correct)

        # ungated best-of-N ranked among confidence-accepted candidates
        # only (the unsound scorer IS the gate here, matching the paper's
        # "reject the bottom quartile" design -- not a ranking-only score
        # over the whole pool)
        if confidence_accepted:
            ungated_unsound.append(
                max(confidence_accepted, key=lambda r: r.score).correct)
        else:
            ungated_unsound.append(b.correct)

        # sound-gated: return base if the SOUND stack accepts it; else the
        # highest-confidence candidate among those the sound stack accepts
        if b.accepted_by(sound_stack):
            gated_then_unsound.append(b.correct)
        else:
            sound_accepted = [r for r in cs if r.accepted_by(sound_stack)]
            gated_then_unsound.append(
                max(sound_accepted, key=lambda r: r.score).correct
                if sound_accepted else b.correct)

    return {"base": np.array(base_acc),
            "ungated_unsound": np.array(ungated_unsound),
            "gated_then_unsound": np.array(gated_then_unsound),
            "n_skipped_no_score": skipped_no_score,
            "n_used": len(base_acc)}


def paired_bootstrap(a: np.ndarray, b: np.ndarray, n_boot: int = 10000,
                     seed: int = 0) -> tuple:
    """Paired bootstrap CI on (mean(a) - mean(b)) in accuracy points."""
    rng = np.random.default_rng(seed)
    n = len(a)
    idx = rng.integers(0, n, size=(n_boot, n))
    d = (a[idx].mean(1) - b[idx].mean(1)) * 100
    return float(d.mean()), float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))


def permutation_test(a: np.ndarray, b: np.ndarray, n_perm: int = 10000,
                     seed: int = 0) -> float:
    """Two-sided paired permutation test on the mean difference."""
    rng = np.random.default_rng(seed)
    d = a.astype(float) - b.astype(float)
    obs = abs(d.mean())
    if obs == 0:
        return 1.0
    signs = rng.choice([-1.0, 1.0], size=(n_perm, len(d)))
    return float(((abs((signs * d).mean(1)) >= obs).sum() + 1) / (n_perm + 1))


def degenerate(res: dict, rule: str = "gated") -> bool:
    """
    B6. A rule is DEGENERATE against the base when it never changed an outcome:
    the paired difference is identically zero, so a zero-width CI is a
    statement about the mechanism not firing, not about the floor holding.
    """
    return bool(np.array_equal(res[rule], res["base"]))
