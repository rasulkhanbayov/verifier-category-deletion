"""
certver.subgroup_acc -- gated best-of-N accuracy per gold-defined subgroup.

  python -m certver.subgroup_acc --task ie --out out/subgroup_ie.json

Same selections as certver.report (hand-written, certified, F1-selected) from
out/curve_{task}_inst_multi.json; same test grid; per subgroup (defined from
gold only, certver.filtering.subgroups) and model, the mean gated accuracy
and the paired bootstrap CI of certified minus F1, and the worst-group
accuracy across subgroups with at least --min-n units.
"""
from __future__ import annotations
import argparse, json, sys
import numpy as np

from .admit import load_examples
from .curve import verdict_matrix, load_candidates, conj
from .ci import per_instance, boot
from .filtering import subgroups
from .report import pick_certified


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--curve", default=None)
    ap.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    ap.add_argument("--N", type=int, default=32)
    ap.add_argument("--min-n", type=int, default=30)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    curve = json.load(open(a.curve or f"out/curve_{a.task}_inst_multi.json"))["results"]
    cname, _ = pick_certified(curve)
    sel = {r["selection"]: r["checks"] for r in curve}
    S = {"handwritten": sel["handwritten"], "certified": sel[cname], "f1_baseline": sel["f1_baseline"]}
    vals = {s: {} for s in S}
    base = {}
    for seed in a.seeds:
        pool = f"data/test/pool_{a.task}_test_seed{seed}.jsonl"
        items = {json.loads(l)["instance_id"]: json.loads(l)
                 for l in open(pool.replace(".jsonl", ".items.jsonl")) if l.strip()}
        ex = [e for e in load_examples(a.task, pool) if e["model"] != "gold"]
        ids = {c for v in S.values() for c in v}
        V = verdict_matrix(a.task, [c for c in load_candidates(a.task, [f"out/candidates/{a.task}_*.jsonl"], ex)
                                    if c["id"] in ids], ex)
        for s, chk in S.items():
            for (m, iid), (v, b) in per_instance(ex, conj(V, chk, len(ex)), a.N).items():
                for g in subgroups(a.task, items[iid]) + ["ALL"]:
                    vals[s].setdefault((g, m), {})[(seed, iid)] = v
                    base.setdefault((g, m), {})[(seed, iid)] = b
    out = {}
    for (g, m) in sorted(vals["certified"]):
        keys = sorted(vals["certified"][(g, m)])
        if len(keys) < a.min_n:
            continue
        arr = {s: np.array([vals[s][(g, m)][k] for k in keys]) for s in S}
        b = np.array([base[(g, m)][k] for k in keys])
        out[f"{g}|{m}"] = {"n": len(keys), "base": float(b.mean()),
                           **{s: float(arr[s].mean()) for s in S},
                           "cert_minus_f1": boot(arr["certified"] - arr["f1_baseline"]),
                           "cert_minus_hw": boot(arr["certified"] - arr["handwritten"])}
        r = out[f"{g}|{m}"]
        f = lambda t: f"{100*t[0]:+.1f} [{100*t[1]:+.1f},{100*t[2]:+.1f}]"
        print(f"{g:32s} {m.split('/')[-1][:20]:20s} n={r['n']:4d} base={100*r['base']:.1f} "
              f"hw={100*r['handwritten']:.1f} f1={100*r['f1_baseline']:.1f} cert={100*r['certified']:.1f} "
              f"| cert-f1 {f(r['cert_minus_f1'])}")
    json.dump(out, open(a.out, "w"), indent=1, default=float)
    return 0


if __name__ == "__main__":
    sys.exit(main())
