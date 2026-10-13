"""
certver.adversarial -- analyses of existing outputs for the adversarial audit.

  python -m certver.adversarial --out out/adversarial_ie.json

(1) For the CoNLL deleting check: on A and B, among inputs with a
    miscellaneous entity, how often it rejects the GOLD answer itself.
(2) Distillation training-set composition: per filter, the share of kept
    examples whose output lists a miscellaneous entity, and the number of
    distinct inputs with a miscellaneous entity represented.
(3) Gold-free view: F1-selected verifier's wiped fraction on B per k-means
    cluster, next to the gold-defined groups.
(4) Labelled-data parity: F1 selection on A+B (2,000 inputs) and the
    wiped fraction of has_else_type on the like-with-like test pools.
"""
from __future__ import annotations
import argparse, json, sys
import numpy as np

from .robust import Pool, greedy, conj, MIN_N
from .curve import verdict_matrix, load_candidates
from soundver import generate as g


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    t = "ie"; out = {}
    A = Pool(t, f"data/pools/pool_{t}_admit_seed0.jsonl")
    B = Pool(t, f"data/pools/pool_{t}_certify_seed0.jsonl", A.km, A.vec, A.gnames)
    T = [Pool(t, f"data/test_bstruct/pool_{t}_test_seed{s}.jsonl", A.km, A.vec, A.gnames) for s in (0, 1, 2)]
    cands = load_candidates(t, [f"out/candidates/{t}_*.jsonl"], A.ex)
    ids = [c["id"] for c in cands]
    dele = "ie-r0-84f7d14832"
    j = A.gnames.index("has_else_type")
    res = {}
    for name, P in (("A", A), ("B", B)):
        V = verdict_matrix(t, [c for c in cands if c["id"] == dele], P.ex)[dele]
        in_g = P.M[:, j]
        gold_rows = np.where(P.gold)[0]
        rej = [not V[r] for r in gold_rows if in_g[P.inst[r]]]
        res[name] = {"n_inputs": int(len(rej)), "gold_rejected": int(sum(rej)), "frac": float(np.mean(rej))}
    out["deleter_rejects_gold"] = res
    # (2) distillation composition
    comp = {}
    for cond in ("none", "handwritten", "f1_baseline", "certified", "oracle"):
        rows = [json.loads(l) for l in open(f"data/distill/sft_ie_{cond}.jsonl") if l.strip()]
        has = []
        for r in rows:
            try:
                obj = json.loads(r["completion"])
            except ValueError:
                obj = None
            has.append(bool(isinstance(obj, dict) and obj.get("else")))
        comp[cond] = {"n": len(rows), "share_with_misc": float(np.mean(has)),
                      "inputs_with_misc": len({r["instance_id"] for r, h in zip(rows, has) if h})}
    out["distill_composition"] = comp
    # (3) gold-free clusters vs gold groups, F1 on full A, wiped on B
    VA = verdict_matrix(t, cands, A.ex); VB = verdict_matrix(t, cands, B.ex)
    f1 = greedy(VA, A, ids, "f1")
    accB = conj(VB, f1, len(B.cor)); w = B.wiped(accB); wg = (B.M & w[:, None]).sum(0)
    out["f1_wiped_on_B"] = {gname: {"n": int(B.n_g[k]), "wiped": float(wg[k] / max(1, B.n_g[k]))}
                            for k, gname in enumerate(B.gnames) if B.n_g[k] >= MIN_N}
    # cluster composition: share of has_else inputs per cluster on B
    ce = {}
    for k, gname in enumerate(B.gnames):
        if gname.startswith("cluster_") and B.n_g[k] >= MIN_N:
            m = B.M[:, k]; ce[gname] = float((m & B.M[:, j]).sum() / max(1, m.sum()))
    out["cluster_share_has_else"] = ce
    # (4) F1 on A+B
    AB = Pool.__new__(Pool)
    AB.cor = np.concatenate([A.cor, B.cor]); AB.gold = np.concatenate([A.gold, B.gold])
    AB.inst = np.concatenate([A.inst, B.inst + A.n_inst]); AB.n_inst = A.n_inst + B.n_inst
    AB.M = np.concatenate([A.M, B.M]); AB.gnames = A.gnames
    AB.has = np.bincount(AB.inst, weights=AB.cor, minlength=AB.n_inst) > 0
    AB.n_g = (AB.M & AB.has[:, None]).sum(0)
    VAB = {c: np.concatenate([VA[c], VB[c]]) for c in ids}
    f1ab = greedy(VAB, AB, ids, "f1")
    tw = []
    for P in T:
        VT = verdict_matrix(t, [c for c in cands if c["id"] in f1ab], P.ex)
        acc = conj(VT, f1ab, len(P.cor)); w = P.wiped(acc)
        tw.append(float((P.M[:, j] & w).sum() / max(1, (P.M[:, j] & P.has).sum())))
    out["f1_on_AplusB"] = {"n_checks": len(f1ab), "takes_deleter": dele in f1ab, "has_else_wiped_on_test_pools": tw}
    json.dump(out, open(a.out, "w"), indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "f1_wiped_on_B"}, indent=1))
    print("F1 wiped on B:", {k: round(v["wiped"], 3) for k, v in out["f1_wiped_on_B"].items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
