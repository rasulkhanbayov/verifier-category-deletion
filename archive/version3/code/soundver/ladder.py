"""
soundver.ladder -- the decisive experiment for the redesign.

Measures epsilon across a capability ladder and tests whether the decay in
verifier power (1-eps) is governed by the TASK or by the MODEL.

The distinction is the whole question:
  task-governed  -> curves for one task collapse onto a line across families
  model-governed -> curves separate by family

Both outcomes are publishable; they are different papers. This decides which.

  python -m soundver.ladder --records data/records.jsonl --out out/
"""
from __future__ import annotations
import argparse, json, os, sys
import numpy as np
from collections import defaultdict
from .records import load
from .rates import estimate

FAMILY = lambda m: m.split("/")[0] if "/" in m else m.split("-")[0]


def fit_log_linear(acc, power):
    """log(1-eps) = s*acc + i. Returns slope, intercept, R^2."""
    ok = power > 1e-6
    if ok.sum() < 3:
        return None
    x, y = acc[ok], np.log(power[ok])
    A = np.vstack([x, np.ones_like(x)]).T
    s, i = np.linalg.lstsq(A, y, rcond=None)[0]
    r2 = 1 - ((y - A @ [s, i]) ** 2).sum() / max(((y - y.mean()) ** 2).sum(), 1e-12)
    return float(s), float(i), float(r2)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--records", required=True)
    ap.add_argument("--out", default="out")
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)

    g = defaultdict(list)
    for r in load(a.records):
        g[(r.task, r.model)].append(r)

    by_task = defaultdict(list)
    print("=" * 74)
    print("CAPABILITY LADDER: verifier precision vs verifier power")
    print("=" * 74)
    print(f"  {'task':6s} {'model':22s} {'acc':>6} {'eps':>7} {'power':>7} {'prec':>7}")
    print("  " + "-" * 62)
    for (task, model), rs in sorted(g.items()):
        R = estimate(rs)
        if not R.sound:
            print(f"  {task:6s} {model[:22]:22s}  unsound (delta={R.delta:.3f}), excluded")
            continue
        q = R.p + (1 - R.p) * R.eps
        prec = R.p / q if q > 0 else float("nan")
        by_task[task].append((model, R.p0, R.eps, 1 - R.eps, prec))
        print(f"  {task:6s} {model[:22]:22s} {R.p0:6.3f} {R.eps:7.3f} "
              f"{1-R.eps:7.3f} {prec:7.3f}")

    print()
    print("=" * 74)
    print("THE TRAP: does precision rise while power collapses?")
    print("=" * 74)
    payload = {}
    for task, rows in sorted(by_task.items()):
        if len(rows) < 3:
            print(f"  {task}: only {len(rows)} sound cells. Need >=3 (ideally >=8).")
            continue
        rows.sort(key=lambda r: r[1])
        acc = np.array([r[1] for r in rows]); pw = np.array([r[3] for r in rows])
        pr = np.array([r[4] for r in rows])
        print(f"\n  {task}: {len(rows)} models, accuracy {acc.min():.3f}->{acc.max():.3f}")
        print(f"     power     {pw[0]:.3f} -> {pw[-1]:.3f}   "
              f"({pw.max()/max(pw.min(),1e-9):.0f}x collapse)")
        print(f"     precision {pr[0]:.3f} -> {pr[-1]:.3f}   "
              f"({'RISES' if pr[-1]>pr[0] else 'falls'})")
        if pr[-1] > pr[0] and pw[-1] < pw[0]:
            print("     -> TRAP CONFIRMED: the metric people report improves while")
            print("        the metric that matters collapses.")
        f = fit_log_linear(acc, pw)
        if f:
            s, i, r2 = f
            print(f"     log(1-eps) = {s:.1f}*acc + {i:.1f}   R^2 = {r2:.3f}")
            print(f"     each +1 accuracy point costs "
                  f"{100*(1-np.exp(s*0.01)):.0f}% of remaining power")
            payload[task] = dict(slope=s, intercept=i, r2=r2, n=len(rows))

    print()
    print("=" * 74)
    print("TASK-GOVERNED OR MODEL-GOVERNED?")
    print("=" * 74)
    for task, rows in sorted(by_task.items()):
        fams = defaultdict(list)
        for m, p0, e, pw, pr in rows:
            fams[FAMILY(m)].append((p0, pw))
        usable = {k: v for k, v in fams.items() if len(v) >= 3}
        if len(usable) < 2:
            print(f"  {task}: need >=3 models in >=2 families to separate these.")
            print(f"         have {[(k,len(v)) for k,v in fams.items()]}")
            continue
        print(f"\n  {task}: per-family fits")
        slopes = []
        for fam, v in sorted(usable.items()):
            acc = np.array([x[0] for x in v]); pw = np.array([x[1] for x in v])
            f = fit_log_linear(acc, pw)
            if f:
                slopes.append(f[0])
                print(f"     {fam:18s} slope {f[0]:8.1f}  R^2 {f[2]:.3f}  n={len(v)}")
        if len(slopes) >= 2:
            spread = max(slopes) - min(slopes)
            print(f"     slope spread across families: {spread:.1f}")
            print("     -> " + ("TASK-governed: families agree, the task sets the rate."
                                if spread < 0.3 * abs(np.mean(slopes))
                                else "MODEL-governed: families disagree; the rate is not"
                                     " a task property."))
    if payload:
        with open(os.path.join(a.out, "ladder.json"), "w") as fh:
            json.dump(payload, fh, indent=2)
        print(f"\n  wrote {a.out}/ladder.json")
    print("\n  Pre-registered reading: fixed before the numbers are seen. Do not")
    print("  reinterpret the slope spread after looking at it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
