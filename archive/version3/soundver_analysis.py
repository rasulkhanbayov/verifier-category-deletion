"""
soundver_analysis.py -- reference implementation for
"Gate Before You Rank: Soundness Buys a Floor, Not a Gain, in
Verifier-Based Test-Time Scaling"

NAME MAP (this file predates the current numbering in the paper; the
functions were not renamed, so read them through this table):

    code name                paper result
    ---------------------    ----------------------------------------
    accuracy_sound           Cor. 2  (gain decomposition, sound case)
    gain_sound               Cor. 2, asymptotic form
    accuracy_unsound_inf     Cor. 3  (degradation)
    degrades                 Cor. 3, the exact condition
    stack_eps                Prop. 2 (stacking)
    gain_heterogeneous       Prop. 3 (heterogeneous gain)
    gain_plugin              Cor. 4  (pooled rates are conservative)
    -- the floor itself is Prop. 1 and needs no code: it is the
       termwise non-negativity of the correction in accuracy_sound.

Contents
  1. The closed forms.
  2. A Monte Carlo simulator of the reject-gated rule, used to CHECK the
     closed forms rather than to assert them.
  3. Estimators for p0, p, delta, eps from real candidate dumps.
  4. Paired bootstrap CIs and a paired permutation test.
  5. Equivalence testing (TOST) and minimum detectable effect.   [SECTION 7]
  6. Table reconciliation from raw per-instance records.         [SECTION 8]
  7. A smoke test that verifies every result on a grid.

numpy only. This file COMPUTES. It never asserts an experimental outcome.
Nothing here produces a number that may be reported as a result about any
model; only Sections 3 and 8 touch real data, and they only estimate rates
and re-derive table cells from records the caller supplies.
"""

import numpy as np

# ---------------------------------------------------------------- 1. theory

def accuracy_sound(p0, p, eps, N):
    """Proposition 2. Accuracy of reject-gated selection with a SOUND
    verifier (delta = 0), uniform scoring, budget N.

        A_N = p0 + (1-p0)(1-eps) * (1-(1-q)^N) * p/q,   q = p+(1-p)eps

    Proposition 1 is the corollary A_N >= p0, which holds termwise because
    every factor is non-negative.
    """
    q = p + (1.0 - p) * eps
    if q <= 0.0:
        return float(p0)
    return p0 + (1.0 - p0) * (1.0 - eps) * (1.0 - (1.0 - q) ** N) * (p / q)


def gain_sound(p0, p, eps):
    """Asymptotic gain, Proposition 2. Factorises as
    headroom (1-p0) x caught (1-eps) x replacement precision p/q."""
    q = p + (1.0 - p) * eps
    return 0.0 if q <= 0.0 else (1.0 - p0) * (1.0 - eps) * (p / q)


def accuracy_unsound_inf(p0, p, eps, delta):
    """Proposition 3. Asymptotic accuracy when the verifier is NOT sound."""
    qp = p * (1.0 - delta) + (1.0 - p) * eps
    if qp <= 0.0:
        return float(p0)
    r = p * (1.0 - delta) / qp
    return p0 * (1.0 - delta) + (p0 * delta + (1.0 - p0) * (1.0 - eps)) * r


def degrades(p0, p, eps, delta):
    """Proposition 3 degradation condition:
        p0 * delta * (1-r)  >  (1-p0) * (1-eps) * r
    Returns True when an unsound verifier is predicted to fall below base."""
    qp = p * (1.0 - delta) + (1.0 - p) * eps
    if qp <= 0.0:
        return False
    r = p * (1.0 - delta) / qp
    return p0 * delta * (1.0 - r) > (1.0 - p0) * (1.0 - eps) * r


def stack_eps(eps_list, independent=True):
    """Proposition 4. Conjunction of sound checks.

    The PROVEN bound is eps_V <= min(eps_i), which holds with no
    independence assumption. The product is the special case in which the
    checks fail independently on incorrect outputs; it is returned only as
    an optimistic reference and MUST NOT be reported as the measured value.
    """
    bound = float(np.min(eps_list))
    prod = float(np.prod(eps_list))
    return {"proven_upper_bound": bound, "independent_case": prod}


# ------------------------------------------------------------ 2. simulation

def simulate_reject_gated(p0, p, eps, delta, N, trials=200_000, seed=0):
    """Monte Carlo of the rule in Section 3 of the paper:
       return y0 if accepted; else return a uniformly random accepted
       sample; else return y0.
    Used ONLY to check the closed forms above."""
    rng = np.random.default_rng(seed)
    c0 = rng.random(trials) < p0
    # a correct output is rejected w.p. delta; an incorrect one accepted w.p. eps
    v0 = np.where(c0, rng.random(trials) >= delta, rng.random(trials) < eps)
    out = c0.copy()
    idx = np.flatnonzero(~v0)
    if len(idx) and N > 0:
        c = rng.random((len(idx), N)) < p
        v = np.where(c, rng.random((len(idx), N)) >= delta,
                        rng.random((len(idx), N)) < eps)
        # uniformly random accepted candidate, else keep y0
        for j, row in enumerate(idx):
            acc = np.flatnonzero(v[j])
            if len(acc):
                out[row] = c[j, rng.choice(acc)]
    return float(out.mean())


# -------------------------------------------------------- 3. rate estimation

def estimate_rates(correct_base, verdict_base, correct_samp, verdict_samp):
    """Estimate p0, p, delta, eps from real candidate dumps.

    correct_base  (n,)   bool, is the greedy output correct
    verdict_base  (n,)   bool, did the verifier accept it
    correct_samp  (n,N)  bool, per-sample correctness
    verdict_samp  (n,N)  bool, per-sample verifier verdict

    delta and eps are pooled over base and samples but ALSO returned
    separately, because the paper's constancy assumption is exactly the
    claim that the two agree. Report both; do not silently pool.
    """
    cb, vb = np.asarray(correct_base, bool), np.asarray(verdict_base, bool)
    cs, vs = np.asarray(correct_samp, bool), np.asarray(verdict_samp, bool)

    def rates(c, v):
        d = float((~v[c]).mean()) if c.any() else float("nan")     # reject|correct
        e = float((v[~c]).mean()) if (~c).any() else float("nan")  # accept|incorrect
        return d, e

    d_b, e_b = rates(cb, vb)
    d_s, e_s = rates(cs.ravel(), vs.ravel())
    c_all = np.concatenate([cb, cs.ravel()])
    v_all = np.concatenate([vb, vs.ravel()])
    d_p, e_p = rates(c_all, v_all)
    return {
        "p0": float(cb.mean()), "p": float(cs.mean()),
        "delta_base": d_b, "eps_base": e_b,
        "delta_samples": d_s, "eps_samples": e_s,
        "delta_pooled": d_p, "eps_pooled": e_p,
        "soundness_violated": bool(d_p > 0.0),
    }


def bootstrap_ci(diffs, B=10_000, alpha=0.05, seed=0):
    """Paired bootstrap CI over instances for a per-instance difference."""
    x = np.asarray(diffs, float)
    rng = np.random.default_rng(seed)
    boot = x[rng.integers(0, len(x), size=(B, len(x)))].mean(axis=1)
    lo, hi = np.quantile(boot, [alpha / 2, 1 - alpha / 2])
    return float(x.mean()), float(lo), float(hi)


def paired_permutation_p(a, b, B=10_000, seed=0):
    """Two-sided paired permutation test on per-instance scores.
    Appropriate for bounded, non-normal accuracy differences, where a
    t-test is not."""
    d = np.asarray(a, float) - np.asarray(b, float)
    rng = np.random.default_rng(seed)
    obs = abs(d.mean())
    signs = rng.choice([-1.0, 1.0], size=(B, len(d)))
    null = np.abs((signs * d).mean(axis=1))
    return float((np.sum(null >= obs) + 1) / (B + 1))


# ------------------------------------------- 6. instance-heterogeneous case

def gain_heterogeneous(p0, p, eps_samples):
    """Appendix E. True aggregate gain when eps varies across instances:
    E_x[g(eps(x))], estimated from a sample of per-instance eps values."""
    e = np.asarray(eps_samples, float)
    q = p + (1.0 - p) * e
    return float((1.0 - p0) * np.mean((1.0 - e) * p / q))


def gain_plugin(p0, p, eps_samples):
    """The homogeneous formula evaluated at the POOLED mean eps.
    Proposition 6 says this is a lower bound on gain_heterogeneous, because
    g is convex in eps. A measured gain ABOVE this is therefore the expected
    direction and is not evidence against the decomposition."""
    return gain_sound(p0, p, float(np.mean(eps_samples)))


def _smoke_hetero():
    print("\nPROP 5 & 6  instance-heterogeneous rates (Appendix E)")
    rng = np.random.default_rng(2)

    # Prop 5: the floor holds POINTWISE, so no homogeneity is needed.
    n = 50_000
    p0v = rng.uniform(0.2, 0.95, n)
    pv = rng.uniform(0.1, 0.90, n)
    ev = rng.uniform(0.0, 1.0, n)
    A = np.array([accuracy_sound(a, b, c, 16) for a, b, c in
                  zip(p0v[:4000], pv[:4000], ev[:4000])])
    viol = int((A < p0v[:4000] - 1e-12).sum())
    assert viol == 0, "Prop 5 floor violated pointwise"
    print(f"  Prop 5: pointwise floor violations = {viol} / 4000"
          f"   aggregate {A.mean():.4f} >= {p0v[:4000].mean():.4f}")

    # Prop 6: convexity of g in eps, hence plug-in is conservative.
    for p0, p, sd in [(0.6, 0.55, 0.35), (0.7, 0.65, 0.20), (0.5, 0.50, 0.45)]:
        e = np.clip(rng.normal(0.7, sd, 200_000), 0.0, 1.0)
        true, plug = gain_heterogeneous(p0, p, e), gain_plugin(p0, p, e)
        assert plug <= true + 1e-9, "Prop 6 (Jensen) violated"
        print(f"  Prop 6: p0={p0} p={p} sd(eps)={e.std():.2f}  "
              f"true={true:.4f} >= plug-in={plug:.4f}  (conservative)")


# ------------------------------------------------------------- 5. smoke test

def _smoke():
    print("=" * 66)
    print("PROP 1 & 2  sound verifier: closed form vs simulation")
    worst = 0.0
    for (p0, p, eps, N) in [(0.70, 0.60, 0.30, 8), (0.55, 0.50, 0.80, 16),
                            (0.85, 0.80, 0.05, 4), (0.40, 0.35, 0.50, 32),
                            (0.30, 0.45, 0.95, 16)]:
        sim = simulate_reject_gated(p0, p, eps, 0.0, N)
        th = accuracy_sound(p0, p, eps, N)
        worst = max(worst, abs(sim - th))
        assert th >= p0 - 1e-12, "Prop 1 violated in closed form"
        assert sim >= p0 - 0.01, "Prop 1 violated in simulation"
        print(f"  p0={p0} p={p} eps={eps} N={N:2d}  sim={sim:.4f} theory={th:.4f}")
    print(f"  max |sim - theory| = {worst:.4f}   Prop 1 floor held everywhere")

    print("\nPROP 2  monotonicity")
    prev = -1.0
    for N in [0, 1, 2, 4, 8, 16, 32, 64]:
        a = accuracy_sound(0.6, 0.55, 0.4, N)
        assert a >= prev - 1e-12, "not monotone in N"
        prev = a
    eps_grid = np.linspace(0, 1, 21)
    g = [gain_sound(0.6, 0.55, e) for e in eps_grid]
    assert all(g[i] >= g[i + 1] - 1e-12 for i in range(len(g) - 1)), "not monotone in eps"
    print(f"  non-decreasing in N, non-increasing in eps.  gain(eps=0)={g[0]:.3f}"
          f"  gain(eps=0.9)={gain_sound(0.6,0.55,0.9):.3f}  gain(eps=1)={g[-1]:.3f}")

    print("\nPROP 3  unsound verifier: predicted vs observed degradation")
    for (p0, p, eps, delta) in [(0.80, 0.50, 0.60, 0.30), (0.60, 0.62, 0.20, 0.10),
                                (0.90, 0.30, 0.70, 0.40), (0.50, 0.55, 0.40, 0.05)]:
        sim = simulate_reject_gated(p0, p, eps, delta, 256)
        pred = degrades(p0, p, eps, delta)
        obs = sim < p0 - 0.01
        assert pred == obs, "Prop 3 condition mispredicted"
        print(f"  p0={p0} delta={delta} eps={eps}  sim={sim:.4f} base={p0}"
              f"  predicted_degrade={pred} observed={obs}")

    print("\nPROP 4  stacking sound checks")
    e = [0.85, 0.70, 0.60]
    for k in range(1, 4):
        s = stack_eps(e[:k])
        assert s["proven_upper_bound"] <= min(e[:k]) + 1e-12
        print(f"  {k} check(s): proven eps <= {s['proven_upper_bound']:.3f}"
              f"   independent-case eps={s['independent_case']:.3f}"
              f"   gain@bound={gain_sound(0.7,0.6,s['proven_upper_bound']):+.4f}")

    print("\nSTATISTICS  bootstrap CI and paired permutation on synthetic data")
    rng = np.random.default_rng(1)
    a = rng.random(500) < 0.62
    b = rng.random(500) < 0.58
    m, lo, hi = bootstrap_ci(a.astype(float) - b.astype(float))
    print(f"  mean diff={m:+.4f}  95% CI=({lo:+.4f},{hi:+.4f})"
          f"  permutation p={paired_permutation_p(a, b):.4f}")

    print("\nRATE ESTIMATION  on synthetic dumps (NOT a result about any model)")
    n, N = 400, 8
    cb = rng.random(n) < 0.65
    vb = np.where(cb, True, rng.random(n) < 0.8)          # sound: delta = 0
    cs = rng.random((n, N)) < 0.55
    vs = np.where(cs, True, rng.random((n, N)) < 0.8)
    r = estimate_rates(cb, vb, cs, vs)
    for k in ("p0", "p", "delta_pooled", "eps_pooled", "soundness_violated"):
        print(f"  {k:>18} = {r[k]}")

    _smoke_hetero()

    print("\nAll behavioural checks passed. These are algebra and synthetic")
    print("demonstrations only, and are not results about any model.")
    print("=" * 66)


if __name__ == "__main__":
    _smoke()


# ============================================================================
# 7. EQUIVALENCE TESTING AND POWER
#
# Section 6 of the paper pre-registers a two-one-sided-test (TOST)
# equivalence analysis at a 1.0 accuracy-point margin, and a minimum
# detectable effect at the achieved sample size, for every near-null claim.
# Neither was reported in the build this file was audited against. These are
# the functions that produce them. They do not decide anything on their own:
# feed them the real per-instance records.
# ============================================================================

def tost_equivalence(diffs, margin_pts, alpha=0.05, B=10_000, seed=0):
    """Two one-sided tests for equivalence on a PAIRED per-instance difference.

    diffs       (n,)  per-instance accuracy difference, in PROPORTION units
                      (0/1 per instance, or the signed correctness delta)
    margin_pts        equivalence margin in ACCURACY POINTS (paper fixes 1.0)

    Equivalence is concluded when the (1-2*alpha) CI for the mean difference
    lies entirely inside (-margin, +margin). Returns the verdict together with
    the CI, so a null result can be reported as 'equivalent', 'different', or
    -- the honest third option the paper currently needs -- 'inconclusive'.
    """
    x = np.asarray(diffs, float)
    n = len(x)
    m = margin_pts / 100.0
    rng = np.random.default_rng(seed)
    boot = x[rng.integers(0, n, size=(B, n))].mean(axis=1)
    lo, hi = np.quantile(boot, [alpha, 1.0 - alpha])   # 1-2a CI, the TOST CI
    inside = bool(lo > -m and hi < m)
    excludes_zero = bool(lo > 0.0 or hi < 0.0)
    if inside:
        verdict = "equivalent"
    elif excludes_zero:
        verdict = "different"
    else:
        verdict = "inconclusive"          # neither equivalent nor different
    return {
        "n": n,
        "mean_diff_pts": float(x.mean() * 100),
        "tost_ci_pts": (float(lo * 100), float(hi * 100)),
        "margin_pts": float(margin_pts),
        "verdict": verdict,
    }


def mde(se_pts, alpha=0.05, power=0.80):
    """Minimum detectable effect in accuracy points, two-sided.

    se_pts may be taken straight from a reported CI half-width: se = hw/1.96.
    """
    from math import sqrt
    z_a = 1.959963985
    z_b = {0.80: 0.8416, 0.90: 1.2816, 0.95: 1.6449}.get(power, 0.8416)
    return float((z_a + z_b) * se_pts)


def n_for_equivalence(sd_pts, margin_pts, alpha=0.05, power=0.80):
    """Instances per condition needed to conclude equivalence at `margin_pts`
    when the true effect is zero. sd_pts is the per-instance SD in points."""
    z_a = {0.05: 1.6449, 0.025: 1.9600}.get(alpha, 1.6449)
    z_b = {0.80: 0.8416, 0.90: 1.2816}.get(power, 0.8416)
    return float(((z_a + z_b) * sd_pts / margin_pts) ** 2)


# ============================================================================
# 8. TABLE RECONCILIATION FROM RAW RECORDS
#
# The audit of the shipped build found that the main comparison table's
# "Delta vs. greedy" and "Floor" columns could not be reproduced from the
# numbers printed beside them. This regenerates both from per-instance
# records so the table has a single source of truth.
# ============================================================================

def reconcile_row(correct_rule, correct_baseline, margin_pts=1.0, seed=0):
    """Recompute one table row from raw per-instance correctness.

    correct_rule      (n,) bool  was the rule's returned output correct
    correct_baseline  (n,) bool  was the greedy baseline correct, SAME instances

    Returns the accuracy, the paired difference with a bootstrap CI, the
    Floor verdict, the TOST verdict, and a degeneracy flag that fires when
    the rule never changed the outcome -- the case that produced the
    zero-width CIs in the audited build.
    """
    a = np.asarray(correct_rule, bool)
    b = np.asarray(correct_baseline, bool)
    if a.shape != b.shape:
        raise ValueError("rule and baseline must cover the same instances")
    d = a.astype(float) - b.astype(float)
    mean, lo, hi = bootstrap_ci(d, seed=seed)
    return {
        "n": int(len(a)),
        "acc_rule_pct": float(a.mean() * 100),
        "acc_baseline_pct": float(b.mean() * 100),
        "delta_pts": float(mean * 100),
        "ci_pts": (float(lo * 100), float(hi * 100)),
        "floor_held": bool(a.mean() >= b.mean()),
        "n_changed": int((a != b).sum()),
        "degenerate": bool((a != b).sum() == 0),   # gate never fired
        "tost": tost_equivalence(d, margin_pts, seed=seed),
    }


def _smoke_equivalence():
    print("\nSECTION 7  equivalence testing and power")
    rng = np.random.default_rng(7)

    # (a) a genuinely null effect at the paper's actual n
    n = 200
    base = rng.random(n) < 0.72
    rule = base.copy()
    flip = rng.random(n) < 0.05          # rule differs on 5% of instances, no bias
    rule[flip] = rng.random(flip.sum()) < 0.72
    r = tost_equivalence(rule.astype(float) - base.astype(float), 1.0)
    print(f"  n={r['n']}  mean diff={r['mean_diff_pts']:+.2f} pts  "
          f"TOST CI=({r['tost_ci_pts'][0]:+.2f},{r['tost_ci_pts'][1]:+.2f})  "
          f"margin=+/-{r['margin_pts']:.1f}  ->  {r['verdict'].upper()}")
    assert r["verdict"] == "inconclusive", (
        "a true null at n=200 should read INCONCLUSIVE at a 1-point margin, "
        "not EQUIVALENT -- this is the distinction the paper's near-null needs")

    # (b) what the design can actually resolve
    for hw, name in [(6.50, "SQL"), (5.25, "IE"), (5.50, "Morph")]:
        print(f"  {name:6s} CI half-width {hw:.2f} pts -> SE {hw/1.96:.2f} "
              f"-> MDE(80%) {mde(hw/1.96):.2f} pts")
    sd = (6.50 / 1.96) * np.sqrt(200)
    for m_pts in (1.0, 3.0, 5.0):
        print(f"  equivalence at {m_pts:.1f} pts needs n ~= "
              f"{n_for_equivalence(sd, m_pts):,.0f} instances per condition")

    # (c) degeneracy detection: the zero-width-CI case
    ident = reconcile_row(base, base)
    print(f"  degenerate row check: n_changed={ident['n_changed']}  "
          f"CI={ident['ci_pts']}  degenerate={ident['degenerate']}")
    assert ident["degenerate"] and ident["ci_pts"] == (0.0, 0.0), \
        "a rule identical to baseline must be flagged degenerate"
    print("  -> a [0.0, 0.0] CI is detected as 'gate never fired', not as evidence.")


if __name__ == "__main__":
    _smoke_equivalence()
