"""
certver.ci -- paired bootstrap CIs for gated best-of-N accuracy on test.

  python -m certver.ci --task ie --curve out/curve_ie.json \
      --candidates "out/candidates/ie_*.jsonl" --test data/pilot/pool_ie_test_seed0.jsonl \
      --selection "tau=0.02" --N 32

Per instance: expected accuracy of reject-gated selection (exact, as in
curve.gated_bon) under the chosen selection, the hand-written stack, and the
base output. Reports mean differences with 95% paired-bootstrap intervals
over instances (10,000 resamples), per model.
"""
from __future__ import annotations
import argparse, json, sys
from math import comb
import numpy as np

from .admit import load_examples
from .curve import verdict_matrix, load_candidates, conj


def per_instance(examples, acc, N):
    by = {}
    for e, a in zip(examples, acc):
        by.setdefault((e["model"], e["instance_id"]), []).append((e["cand_idx"], e["correct"], bool(a)))
    out = {}
    for (m, iid), rows in by.items():
        base = [r for r in rows if r[0] == -1]
        samp = [r for r in rows if r[0] >= 0]
        if not base or not samp:
            continue
        b_cor, b_acc = base[0][1], base[0][2]
        if b_acc:
            v = float(b_cor)
        else:
            S, A = len(samp), sum(r[2] for r in samp)
            n = min(N, S)
            p_none = comb(S - A, n) / comb(S, n) if S - A >= n else 0.0
            prec = sum(r[1] and r[2] for r in samp) / A if A else 0.0
            v = (1 - p_none) * prec + p_none * float(b_cor)
        out[(m, iid)] = (v, float(b_cor))
    return out


def boot(d, n_boot=10000, seed=0):
    rng = np.random.default_rng(seed)
    d = np.asarray(d)
    idx = rng.integers(0, len(d), size=(n_boot, len(d)))
    means = d[idx].mean(axis=1)
    return float(d.mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True); ap.add_argument("--curve", required=True)
    ap.add_argument("--candidates", nargs="+", required=True); ap.add_argument("--test", required=True)
    ap.add_argument("--selection", required=True); ap.add_argument("--N", type=int, default=32)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    sel = {r["selection"]: r["checks"] for r in json.load(open(a.curve))["results"]}
    ex = [e for e in load_examples(a.task, a.test) if e["model"] != "gold"]
    ids = set(sel[a.selection]) | set(sel["handwritten"])
    cands = [c for c in load_candidates(a.task, a.candidates, ex) if c["id"] in ids]
    V = verdict_matrix(a.task, cands, ex)
    S = per_instance(ex, conj(V, sel[a.selection], len(ex)), a.N)
    H = per_instance(ex, conj(V, sel["handwritten"], len(ex)), a.N)
    res = {}
    for m in sorted({k[0] for k in S}):
        keys = sorted(k for k in S if k[0] == m)
        s = np.array([S[k][0] for k in keys]); h = np.array([H[k][0] for k in keys])
        b = np.array([S[k][1] for k in keys])
        res[m] = {"n": len(keys), "base": float(b.mean()), "handwritten": float(h.mean()),
                  "synth": float(s.mean()), "synth_minus_base": boot(s - b),
                  "synth_minus_handwritten": boot(s - h), "handwritten_minus_base": boot(h - b)}
        r = res[m]
        f = lambda t: f"{100*t[0]:+.1f} [{100*t[1]:+.1f}, {100*t[2]:+.1f}]"
        print(f"{m.split('/')[-1][:26]:26s} n={r['n']} base={100*r['base']:.1f} hw={100*r['handwritten']:.1f} "
              f"synth={100*r['synth']:.1f} | synth-base {f(r['synth_minus_base'])} | "
              f"synth-hw {f(r['synth_minus_handwritten'])} | hw-base {f(r['handwritten_minus_base'])}")
    if a.out:
        json.dump({"task": a.task, "selection": a.selection, "N": a.N, "by_model": res},
                  open(a.out, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
