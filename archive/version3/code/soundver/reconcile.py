"""
soundver.reconcile -- regenerate every reported number from records.

Run this the moment the per-instance records exist. It is the single script
that closes B2, B3, B6 and B7, and it emits the LaTeX for every table so the
paper cannot drift from the data again.

  python -m soundver.reconcile --records data/records.jsonl --out out/

Also provides:
  --exhaustive   B11: every 2^k - 1 sub-conjunction, not one chain
  --seeds        B4: rates and CIs per seed, with across-seed spread
"""
from __future__ import annotations
import argparse, itertools, json, os, sys
import numpy as np
from collections import defaultdict
from .records import load, CHECKS
from .rates import (estimate, simulate_rules, paired_bootstrap,
                    permutation_test, degenerate, degradation)


def group(recs):
    g = defaultdict(list)
    for r in recs:
        g[(r.task, r.model)].append(r)
    return g


# ---------------------------------------------------------------- B2 / B3 / B7
def reconcile(recs, N=32, out=None):
    print("=" * 78)
    print("RATES AND CEILING, RECOMPUTED FROM RECORDS  (closes B2, B3, B7)")
    print("=" * 78)
    print(f"  {'task':6s} {'model':26s} {'p0':>6} {'p':>6} {'delta':>7} "
          f"{'eps':>6} {'ceil':>7}  sound")
    print("  " + "-" * 74)
    rows = []
    for (task, model), rs in sorted(group(recs).items()):
        R = estimate(rs)
        rows.append(R)
        c = R.ceiling_pts()
        print(f"  {task:6s} {model[:26]:26s} {R.p0:6.3f} {R.p:6.3f} "
              f"{R.delta:7.4f} {R.eps:6.3f} "
              f"{('%.2f' % c) if c == c else '   n/a':>7}  "
              f"{'YES' if R.sound else 'no'}")
        if R.delta_base != R.delta_cand:
            print(f"  {'':6s} {'':26s} delta differs base vs samples: "
                  f"{R.delta_base:.4f} / {R.delta_cand:.4f}")
        if abs(R.eps_base - R.eps_cand) > 0.02:
            print(f"  {'':6s} {'':26s} A2 VIOLATED for eps: "
                  f"base {R.eps_base:.3f} vs samples {R.eps_cand:.3f}")
    print()
    print("  B2 is settled by the `delta` column above: it is the ONLY measured")
    print("  delta. Whichever printed table disagrees with it is the wrong one.")
    if out:
        with open(os.path.join(out, "rates.json"), "w") as fh:
            json.dump([{**vars(R), "subset": list(R.subset),
                        "ceiling_pts": R.ceiling_pts()} for R in rows], fh, indent=2)
    return rows


# ---------------------------------------------------------------------- B6
def rules(recs, N=32, out=None):
    print("=" * 78)
    print("RULE COMPARISON ON A SHARED POOL  (closes B3's Delta/Floor, flags B6)")
    print("=" * 78)
    payload = []
    for (task, model), rs in sorted(group(recs).items()):
        sub = CHECKS[task]
        res = simulate_rules(rs, sub, N)
        base = res["base"].mean() * 100
        fired = res["gate_fired"].mean() * 100
        print(f"\n  {task} / {model}")
        print(f"    greedy baseline {base:.1f}%   gate fired on {fired:.1f}% "
              f"of instances")
        for rule in ("gated", "homogeneous", "ungated"):
            m, lo, hi = paired_bootstrap(res[rule], res["base"])
            p = permutation_test(res[rule], res["base"])
            deg = degenerate(res, rule)
            flag = "  <-- DEGENERATE: outcome identical to base on every " \
                   "instance (B6)" if deg else ""
            print(f"    {rule:12s} {res[rule].mean()*100:5.1f}%  "
                  f"D={m:+5.2f} [{lo:+.2f},{hi:+.2f}] p={p:.3f}{flag}")
            payload.append(dict(task=task, model=model, rule=rule,
                                acc=float(res[rule].mean()), delta_pts=m,
                                ci=[lo, hi], p=p, degenerate=deg,
                                gate_fired_frac=float(res["gate_fired"].mean())))
        m, lo, hi = paired_bootstrap(res["gated"], res["homogeneous"])
        p = permutation_test(res["gated"], res["homogeneous"])
        print(f"    gated vs homogeneous: {m:+.2f} [{lo:+.2f},{hi:+.2f}] p={p:.3f}")
    print()
    print("  Any row marked DEGENERATE must not be cited as evidence for")
    print("  Cor. 1. Report the cells where an ungated scorer degraded and")
    print("  gating recovered it; those are the mechanism evidence.")
    if out:
        with open(os.path.join(out, "rules.json"), "w") as fh:
            json.dump(payload, fh, indent=2)
    return payload


# --------------------------------------------------------------------- B11
def exhaustive(recs, N=32, out=None):
    print("=" * 78)
    print("EVERY SUB-CONJUNCTION  (closes B11: Cor. 3(a) over the design space)")
    print("=" * 78)
    payload, violations = [], 0
    for (task, model), rs in sorted(group(recs).items()):
        names = CHECKS[task]
        full = estimate(rs, names)
        if not full.sound:
            print(f"\n  {task}/{model}: full stack UNSOUND (delta={full.delta:.4f}); "
                  f"Cor. 3's hypothesis fails, cell excluded.")
            continue
        cap = full.ceiling_pts()
        print(f"\n  {task} / {model}   full-stack ceiling {cap:.3f} pts")
        for k in range(1, len(names) + 1):
            for S in itertools.combinations(names, k):
                R = estimate(rs, S)
                g = R.gain_pts(N)
                bad = (g == g) and g > cap + 1e-9
                violations += bad
                payload.append(dict(task=task, model=model, subset=list(S),
                                    eps=R.eps, delta=R.delta, gain_pts=g,
                                    exceeds_full=bool(bad)))
                mark = "  <-- EXCEEDS THE BOUND" if bad else ""
                print(f"    {'+'.join(S):46s} eps={R.eps:.3f} "
                      f"gain={g:6.3f}{mark}")
    print()
    print(f"  sub-conjunctions exceeding the full-stack bound: {violations}")
    print("  Cor. 3(a) is a proof, so a violation means a MEASUREMENT problem:")
    print("  a check that is not actually sound, or a correctness label that")
    print("  presupposes one of the checks (Section 6's circularity condition).")
    if out:
        with open(os.path.join(out, "exhaustive.json"), "w") as fh:
            json.dump(payload, fh, indent=2)
    return payload


# ---------------------------------------------------------------------- B4
def seeds(recs, N=32, out=None):
    print("=" * 78)
    print("SEED REPLICATION  (closes B4)")
    print("=" * 78)
    payload = []
    for (task, model), rs in sorted(group(recs).items()):
        ss = sorted({r.seed for r in rs})
        if len(ss) < 2:
            print(f"  {task}/{model}: only seed(s) {ss} present. "
                  f"B4 STAYS OPEN for this cell.")
            continue
        eps, ceil = [], []
        for s in ss:
            R = estimate(rs, seed=s)
            eps.append(R.eps); ceil.append(R.ceiling_pts())
        print(f"  {task}/{model}: {len(ss)} seeds   "
              f"eps {np.mean(eps):.3f} +/- {np.std(eps, ddof=1):.3f}   "
              f"ceiling {np.nanmean(ceil):.2f} +/- {np.nanstd(ceil, ddof=1):.2f} pts")
        payload.append(dict(task=task, model=model, seeds=ss,
                            eps_mean=float(np.mean(eps)),
                            eps_sd=float(np.std(eps, ddof=1)),
                            ceiling_mean=float(np.nanmean(ceil)),
                            ceiling_sd=float(np.nanstd(ceil, ddof=1))))
    print()
    print("  Report the across-seed SD alongside every headline number. A")
    print("  ceiling whose SD exceeds the ceiling itself is not a result.")
    if out:
        with open(os.path.join(out, "seeds.json"), "w") as fh:
            json.dump(payload, fh, indent=2)
    return payload


# ------------------------------------------------------------------ E3/E4
def gain_curve(recs, budgets=(1, 2, 4, 8, 16, 32), out=None):
    """
    E3: Cor.~gain's predicted A_N against the OBSERVED gated-rule accuracy
    (bootstrap 95% CI) at every budget in `budgets`, for every SOUND cell
    (delta=0 at the full stack; an unsound cell's prediction is not
    evaluated, since the corollary assumes delta=0). Reports whether the
    prediction falls inside the observed interval at each (model, budget)
    cell -- the paper's own confirm/falsify criterion.

    E4: for each task, adds checks one at a time in CHECKS[task]'s order
    and reports whether epsilon is non-increasing and observed accuracy
    (gated rule, at the LARGEST budget in `budgets`) is non-decreasing at
    every step -- Prop.~stack's two monotonicity predictions.
    """
    print("=" * 78)
    print("E3: PREDICTED VS. OBSERVED GAIN ACROSS THE BUDGET GRID")
    print("=" * 78)
    e3_payload = []
    for (task, model), rs in sorted(group(recs).items()):
        full_stack = CHECKS[task]
        R_full = estimate(rs, full_stack)
        if not R_full.sound:
            print(f"\n  {task} / {model}: full stack UNSOUND (delta="
                  f"{R_full.delta:.4f}); Cor. gain's precondition fails, "
                  f"prediction not evaluated for this cell.")
            continue
        print(f"\n  {task} / {model}  (p0={R_full.p0:.3f} p={R_full.p:.3f} "
              f"eps={R_full.eps:.3f})")
        for N in budgets:
            pred = R_full.gain_pts(N) / 100.0 + R_full.p0
            res = simulate_rules(rs, full_stack, N)
            zeros = np.zeros_like(res["gated"], dtype=float)
            m_pts, lo_pts, hi_pts = paired_bootstrap(res["gated"], zeros)
            obs = res["gated"].mean()
            obs_lo, obs_hi = lo_pts / 100.0, hi_pts / 100.0
            inside = obs_lo <= pred <= obs_hi
            print(f"    N={N:<3d} predicted={pred:.4f}  observed={obs:.4f} "
                  f"[{obs_lo:.4f},{obs_hi:.4f}]  {'inside' if inside else 'OUTSIDE'}")
            e3_payload.append(dict(task=task, model=model, N=N,
                                   predicted=pred, observed=obs,
                                   observed_lo=obs_lo, observed_hi=obs_hi,
                                   inside=bool(inside)))
    print()
    n_inside = sum(1 for r in e3_payload if r["inside"])
    print(f"  {n_inside}/{len(e3_payload)} (model, budget) cells: prediction "
          f"inside the observed interval.")

    print()
    print("=" * 78)
    print("E4: STACKING -- ADD CHECKS ONE AT A TIME")
    print("=" * 78)
    e4_payload = []
    N_top = max(budgets)
    for (task, model), rs in sorted(group(recs).items()):
        names = CHECKS[task]
        print(f"\n  {task} / {model}")
        eps_seq, acc_seq = [], []
        for k in range(1, len(names) + 1):
            subset = names[:k]
            R = estimate(rs, subset)
            res = simulate_rules(rs, subset, N_top)
            acc = res["gated"].mean()
            eps_seq.append(R.eps)
            acc_seq.append(acc)
            print(f"    {'+'.join(subset):40s} eps={R.eps:.4f} delta="
                  f"{R.delta:.4f} acc(N={N_top})={acc:.4f}")
        eps_mono = all(eps_seq[i] >= eps_seq[i + 1] - 1e-9
                       for i in range(len(eps_seq) - 1))
        acc_mono = all(acc_seq[i] <= acc_seq[i + 1] + 1e-9
                       for i in range(len(acc_seq) - 1))
        print(f"    eps non-increasing: {eps_mono}   "
              f"acc non-decreasing: {acc_mono}")
        e4_payload.append(dict(task=task, model=model, eps_seq=eps_seq,
                               acc_seq=acc_seq, eps_monotone=eps_mono,
                               acc_monotone=acc_mono))
    if out:
        with open(os.path.join(out, "gain_curve.json"), "w") as fh:
            json.dump(e3_payload, fh, indent=2)
        with open(os.path.join(out, "stacking.json"), "w") as fh:
            json.dump(e4_payload, fh, indent=2)
    return e3_payload, e4_payload


# ---------------------------------------------------------------------- E5
def degradation_experiment(recs, N=8, out=None):
    print("=" * 78)
    print("E5: DEGRADATION AND THE FLOOR, WITH AN UNSOUND CONFIDENCE SCORER")
    print("=" * 78)
    payload = []
    for (task, model), rs in sorted(group(recs).items()):
        sound_stack = CHECKS[task]
        res = degradation(rs, sound_stack, N)
        if res["n_used"] == 0:
            print(f"\n  {task} / {model}: no records with a real score "
                  f"(--want-logprobs not used for this cell). SKIPPED.")
            continue
        base = res["base"].mean() * 100
        ungated = res["ungated_unsound"].mean() * 100
        gated = res["gated_then_unsound"].mean() * 100
        print(f"\n  {task} / {model}  (n={res['n_used']}, "
              f"{res['n_skipped_no_score']} skipped for missing score)")
        print(f"    base                {base:5.1f}%")
        m_u, lo_u, hi_u = paired_bootstrap(res["ungated_unsound"], res["base"])
        p_u = permutation_test(res["ungated_unsound"], res["base"])
        degraded_ungated = bool(res["ungated_unsound"].mean() < res["base"].mean() - 1e-9)
        print(f"    ungated (unsound)   {ungated:5.1f}%  D={m_u:+.2f} "
              f"[{lo_u:+.2f},{hi_u:+.2f}] p={p_u:.3f}"
              f"{'  <-- DEGRADED' if degraded_ungated else ''}")
        m_g, lo_g, hi_g = paired_bootstrap(res["gated_then_unsound"], res["base"])
        p_g = permutation_test(res["gated_then_unsound"], res["base"])
        floor_holds = bool(res["gated_then_unsound"].mean() >= res["base"].mean() - 1e-9)
        print(f"    gated-then-unsound  {gated:5.1f}%  D={m_g:+.2f} "
              f"[{lo_g:+.2f},{hi_g:+.2f}] p={p_g:.3f}"
              f"{'  (floor holds)' if floor_holds else '  <-- FLOOR VIOLATED'}")
        payload.append(dict(task=task, model=model, n=res["n_used"],
                            base_pct=float(base), ungated_pct=float(ungated),
                            gated_pct=float(gated), degraded_ungated=degraded_ungated,
                            floor_holds=floor_holds,
                            ungated_diff_ci=[m_u, lo_u, hi_u],
                            gated_diff_ci=[m_g, lo_g, hi_g]))
    print()
    print("  Informative cells are those where the ungated rule DEGRADED and the")
    print("  gated rule's floor still held -- that pair is the direct evidence")
    print("  for the floor guarantee (Prop. floor), not the average case.")
    if out:
        with open(os.path.join(out, "degradation.json"), "w") as fh:
            json.dump(payload, fh, indent=2)
    return payload


# ----------------------------------------------------------- LaTeX emission
def emit_ceiling_table(rows, path):
    L = [r"\begin{tabular}{@{}ll ccc@{}}", r"\toprule",
         r"Task & Model & $p_0$ & $\varepsilon$ & Ceiling (pts) \\", r"\midrule"]
    for R in rows:
        if not R.sound:
            continue
        L.append(f"{R.task.upper()} & {R.model.split('/')[-1]} & "
                 f"{R.p0:.3f} & {R.eps:.3f} & {R.ceiling_pts():.2f} \\\\")
    L += [r"\bottomrule", r"\end{tabular}"]
    with open(path, "w") as fh:
        fh.write("\n".join(L) + "\n")
    print(f"  wrote {path}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--records", required=True)
    ap.add_argument("--out", default="out")
    ap.add_argument("--budget", type=int, default=32)
    ap.add_argument("--exhaustive", action="store_true")
    ap.add_argument("--seeds", action="store_true")
    ap.add_argument("--degradation", action="store_true",
                    help="E5: requires records with a real score "
                         "(generate.py --want-logprobs)")
    ap.add_argument("--degradation-n", type=int, default=8,
                    help="candidate budget for the E5 experiment")
    ap.add_argument("--gain-curve", action="store_true",
                    help="E3/E4: predicted-vs-observed gain across the "
                         "budget grid, and stacking monotonicity")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    recs = load(a.records)
    print(f"loaded {len(recs)} records from {a.records}\n")
    rows = reconcile(recs, a.budget, a.out)
    print(); rules(recs, a.budget, a.out)
    if a.exhaustive or a.all:
        print(); exhaustive(recs, a.budget, a.out)
    if a.seeds or a.all:
        print(); seeds(recs, a.budget, a.out)
    if a.gain_curve or a.all:
        print(); gain_curve(recs, out=a.out)
    if a.degradation or a.all:
        print(); degradation_experiment(recs, a.degradation_n, a.out)
    print()
    emit_ceiling_table(rows, os.path.join(a.out, "tab_ceiling.tex"))
    print("\nEvery number above came from the records. Nothing was read from a")
    print("summary file or a previous pass.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
