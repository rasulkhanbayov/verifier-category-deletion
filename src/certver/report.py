"""
certver.report -- all test-set analyses over every test seed, one task at a time.

  python -m certver.report --task ie --seeds 0 1 2 --out out/report_ie.json

Selections come from out/curve_{task}_inst.json (built on splits A/B only):
  handwritten   version3's stack
  certified     the smallest budget in {1%, 2%, 5%} whose INSTANCE-level
                certificate holds on B (pre-specified rule, not chosen on test)
  f1_baseline   AutoPyVerifier-style F1 selection, uncertified
Per model, pooled over seeds: delta, instance-averaged delta, eps; gated
best-of-32 accuracy with paired bootstrap CIs (resampling (seed, instance)
units); and the filtering metrics of certver.filtering.
"""
from __future__ import annotations
import argparse, json, sys
import numpy as np

from .admit import load_examples
from .curve import verdict_matrix, load_candidates, conj
from .ci import per_instance, boot
from .filtering import subgroups

BUDGETS = (0.01, 0.02, 0.05)


def pick_certified(results):
    by = {r["selection"]: r for r in results}
    for b in BUDGETS:
        r = by.get(f"itau={b}")
        if r and r["certified"]:
            return f"itau={b}", r
    raise SystemExit("no instance-level certified selection in the budget grid")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", required=True)
    ap.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    ap.add_argument("--test-dir", default="data/test")
    ap.add_argument("--N", type=int, default=32)
    ap.add_argument("--curve", default=None, help="default out/curve_{task}_inst.json")
    ap.add_argument("--pools", nargs="+", default=None,
                    help="explicit test pool files (e.g. the fresh draw); overrides --test-dir/--seeds")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)

    curve = json.load(open(a.curve or f"out/curve_{a.task}_inst.json"))["results"]
    cert_name, cert_row = pick_certified(curve)
    sel = {r["selection"]: r["checks"] for r in curve}
    S = {"handwritten": sel["handwritten"], "certified": sel[cert_name], "f1_baseline": sel["f1_baseline"]}
    if "apv_baseline" in sel:
        S["apv_baseline"] = sel["apv_baseline"]
    print(f"certified selection: {cert_name} ({len(S['certified'])} checks; "
          f"B gamma {cert_row['B_gamma_k']}/{cert_row['B_gamma_n']}, U95 {cert_row['B_gamma_upper95']:.4f})")

    gated = {s: {} for s in S}        # (model) -> list of (key, value, base)
    rate = {s: {} for s in S}         # model -> accumulators
    filt = {s: {"kept": 0, "kept_cor": 0, "cor": 0, "has": {}, "keep": {}} for s in S}
    groups = {}
    pools = a.pools or [f"{a.test_dir}/pool_{a.task}_test_seed{s}.jsonl" for s in a.seeds]
    for seed, pool in enumerate(pools):
        items = {json.loads(l)["instance_id"]: json.loads(l)
                 for l in open(pool.replace(".jsonl", ".items.jsonl")) if l.strip()}
        for iid, it in items.items():
            groups[(seed, iid)] = subgroups(a.task, it)
        ex = [e for e in load_examples(a.task, pool) if e["model"] != "gold"]
        ids = {c for v in S.values() for c in v}
        V = verdict_matrix(a.task, [c for c in load_candidates(a.task, [f"out/candidates/{a.task}_*.jsonl"], ex)
                                    if c["id"] in ids], ex)
        cor = np.array([e["correct"] for e in ex])
        for s, chk in S.items():
            acc = conj(V, chk, len(ex))
            for (m, iid), (v, b) in per_instance(ex, acc, a.N).items():
                gated[s].setdefault(m, []).append(((seed, iid), v, b))
            for e, ac, c in zip(ex, acc, cor):
                R = rate[s].setdefault(e["model"], {"rc": 0, "c": 0, "ai": 0, "i": 0, "inst": {}})
                if c:
                    R["c"] += 1; R["rc"] += int(not ac)
                    t = R["inst"].setdefault((seed, e["instance_id"]), [0, 0]); t[0] += 1; t[1] += int(not ac)
                else:
                    R["i"] += 1; R["ai"] += int(ac)
                F = filt[s]; key = (seed, e["model"], e["instance_id"])
                F["kept"] += int(ac); F["kept_cor"] += int(ac and c); F["cor"] += int(c)
                if c:
                    F["has"][key] = True; F["keep"][key] = F["keep"].get(key, False) or bool(ac)

    out = {"task": a.task, "certified_selection": cert_name,
           "certificate": {k: cert_row[k] for k in ("B_gamma_k", "B_gamma_n", "B_gamma_upper95",
                                                    "B_false_rejections", "B_n_correct", "B_catch")},
           "by_model": {}, "filtering": {}}
    fmt = lambda t: f"{100*t[0]:+.1f} [{100*t[1]:+.1f}, {100*t[2]:+.1f}]"
    for m in sorted(gated["certified"]):
        row = {}
        base = None
        vals = {}
        for s in S:
            L = sorted(gated[s][m]); vals[s] = np.array([v for _, v, _ in L])
            base = np.array([b for _, _, b in L])
            R = rate[s][m]
            inst_delta = np.mean([r / n for n, r in R["inst"].values()])
            row[s] = {"acc": float(vals[s].mean()), "delta": R["rc"] / max(1, R["c"]),
                      "inst_avg_delta": float(inst_delta), "eps": R["ai"] / max(1, R["i"])}
        row["base_acc"] = float(base.mean()); row["n_units"] = int(len(base))
        row["cert_minus_base"] = boot(vals["certified"] - base)
        row["cert_minus_hw"] = boot(vals["certified"] - vals["handwritten"])
        row["cert_minus_f1"] = boot(vals["certified"] - vals["f1_baseline"])
        if "apv_baseline" in vals:
            row["cert_minus_apv"] = boot(vals["certified"] - vals["apv_baseline"])
        row["hw_minus_base"] = boot(vals["handwritten"] - base)
        out["by_model"][m] = row
        print(f"{m.split('/')[-1][:24]:24s} n={row['n_units']} base={100*row['base_acc']:.1f} "
              f"hw={100*row['handwritten']['acc']:.1f} cert={100*row['certified']['acc']:.1f} "
              f"f1={100*row['f1_baseline']['acc']:.1f} | cert-hw {fmt(row['cert_minus_hw'])} | "
              f"cert-f1 {fmt(row['cert_minus_f1'])} | hw-base {fmt(row['hw_minus_base'])}")
        if "cert_minus_apv" in row:
            print(f"{'':24s} apv acc={100*row['apv_baseline']['acc']:.1f} cert-apv {fmt(row['cert_minus_apv'])} "
                  f"apv inst-avg delta={row['apv_baseline']['inst_avg_delta']:.4f}")
        print(f"{'':24s} inst-avg delta: hw={row['handwritten']['inst_avg_delta']:.4f} "
              f"cert={row['certified']['inst_avg_delta']:.4f} (bound {cert_row['B_gamma_upper95']:.4f}) "
              f"f1={row['f1_baseline']['inst_avg_delta']:.4f} | eps: hw={row['handwritten']['eps']:.3f} "
              f"cert={row['certified']['eps']:.3f} f1={row['f1_baseline']['eps']:.3f}")
    for s, F in filt.items():
        lost = [k for k in F["has"] if not F["keep"][k]]
        sub = {}
        for k in F["has"]:
            for g in groups[(k[0], k[2])]:
                t = sub.setdefault(g, [0, 0]); t[0] += 1; t[1] += int(not F["keep"][k])
        out["filtering"][s] = {"precision": F["kept_cor"] / max(1, F["kept"]),
                               "recall": F["kept_cor"] / max(1, F["cor"]),
                               "lost": len(lost), "n": len(F["has"]),
                               "subgroups": {g: {"n": n, "lost": l} for g, (n, l) in sub.items()}}
        worst = sorted(((l / n, g, l, n) for g, (n, l) in sub.items() if n >= 30), reverse=True)[:3]
        print(f"filter {s:12s} precision={out['filtering'][s]['precision']:.3f} "
              f"recall={out['filtering'][s]['recall']:.3f} lost={len(lost)}/{len(F['has'])} | worst: "
              + ", ".join(f"{g} {l}/{n}" for _, g, l, n in worst))
    json.dump(out, open(a.out, "w"), indent=1, default=float)
    return 0


if __name__ == "__main__":
    sys.exit(main())
