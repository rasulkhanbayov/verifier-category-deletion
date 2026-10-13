"""
certver.redteam -- analyses of existing outputs requested by the simulated ARR review.

  python -m certver.redteam --out out/redteam.json

(M2) gold-admission + F1: drop candidates that reject any gold output on A
     (and, separately, more than 1% of A's gold outputs), then F1 selection;
     deletion and gamma on B, per task; plus 200-replicate resampling on CoNLL.
(M6) the certified verifier's gamma on the FRESH draws restructured like B
     (greedy + first three samples per model, gold added), vs U_B.
(m6) the gold-only SQL verifier's gamma on the like-with-like test pools.
(m8) F1 selection with gold rows excluded from F1 (CoNLL): takes the deleting check?
(m13) group certificate status of the certified selection per task.
"""
from __future__ import annotations
import argparse, json, os, sys
import numpy as np
from scipy.stats import beta

from .robust import Pool, greedy, conj, certify, MIN_N, BUDGETS, TAU_G
from .curve import verdict_matrix, load_candidates

TASKS = ["ie", "fewnerd", "fc", "sql", "math", "morph"]
DELETER = "ie-r0-84f7d14832"


def cp(k, n, a):
    return 1.0 if k >= n else float(beta.ppf(1 - a, k + 1, n - k))


def pick(t):
    C = {r["selection"]: r for r in json.load(open(f"out/curve_{t}_inst_multi.json"))["results"]}
    for b in BUDGETS:
        if C[f"itau={b}"]["certified"]:
            return b, C[f"itau={b}"]["checks"]


def restructure(src, dst):
    with open(dst, "w") as f:
        for l in open(src):
            if l.strip() and json.loads(l)["cand_idx"] in (-1, 0, 1, 2):
                f.write(l)
    import shutil
    shutil.copy(src.replace(".jsonl", ".items.jsonl"), dst.replace(".jsonl", ".items.jsonl"))


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); a = ap.parse_args(argv)
    out = {"gold_admission_f1": {}, "fresh_bstruct": {}, "group_certificate": {}}
    os.makedirs("data/fresh_bstruct", exist_ok=True)
    for t in TASKS:
        A = Pool(t, f"data/pools/pool_{t}_admit_seed0.jsonl")
        B = Pool(t, f"data/pools/pool_{t}_certify_seed0.jsonl", A.km, A.vec, A.gnames)
        cands = load_candidates(t, [f"out/candidates/{t}_*.jsonl"], A.ex)
        ids = [c["id"] for c in cands]
        VA = verdict_matrix(t, cands, A.ex); VB = verdict_matrix(t, cands, B.ex)
        G = int((B.n_g >= MIN_N).sum())
        gold_rows = np.where(A.gold)[0]
        res = {}
        for name, tol in (("zero", 0.0), ("one_pct", 0.01)):
            adm = [c for c in ids if (~VA[c][gold_rows]).mean() <= tol]
            sel = greedy(VA, A, adm, "f1")
            cB = certify(B, conj(VB, sel, len(B.cor)), 0.05, 0.05 / max(1, G))
            res[name] = {"admitted": len(adm), "of": len(ids), "n_checks": len(sel), "takes_deleter": DELETER in sel,
                         "B_gamma_k": cB["k"], "worst_wiped": cB["worst_group_wiped_frac"], "worst_group": cB["worst_group_wiped"],
                         "catch": cB["catch"], "deleted": cB["worst_group_wiped_frac"] >= 0.5}
        out["gold_admission_f1"][t] = res
        # group certificate status of the certified (picked) selection
        b, sel = pick(t)
        cB = certify(B, conj(VB, sel, len(B.cor)), 0.05 / len(BUDGETS), 0.05 / (len(BUDGETS) * max(1, G)))
        out["group_certificate"][t] = {"tau": b, "U": cB["U"], "U_group_max": cB["U_group_max"],
                                       "worst_group": cB["worst_group"], "certified_group": cB["U_group_max"] <= TAU_G and cB["U"] <= b}
        # fresh draws restructured like B
        src = f"data/fresh/pool_{t}_fresh_seed0.jsonl"
        if os.path.exists(src):
            dst = f"data/fresh_bstruct/pool_{t}_fresh_seed0.jsonl"; restructure(src, dst)
            F = Pool(t, dst, A.km, A.vec, A.gnames)
            VF = verdict_matrix(t, [c for c in cands if c["id"] in set(sel)], F.ex)
            k, n, _, _ = F.gamma(conj(VF, sel, len(F.cor)))
            out["fresh_bstruct"][t] = {"tau": b, "gamma_fresh": k / n, "k": k, "n": n, "U_B": cB["U"], "holds": k / n <= cB["U"]}
        print(t, json.dumps({"gold_adm": res, "group_cert": out["group_certificate"][t], "fresh": out["fresh_bstruct"].get(t)}), flush=True)
    # (m6) gold-only SQL verifier on like-with-like test pools
    t = "sql"; A = Pool(t, f"data/pools/pool_{t}_admit_seed0.jsonl")
    g = [r for r in json.load(open("out/ablate_sql_multi.json"))["rows"] if r["tau"] == 0.05 and r["variant"] == "gold_only"][0]
    cands = load_candidates(t, [f"out/candidates/{t}_*.jsonl"], A.ex)
    tg = []
    for s in (0, 1, 2):
        T = Pool(t, f"data/test_bstruct/pool_{t}_test_seed{s}.jsonl", A.km, A.vec, A.gnames)
        VT = verdict_matrix(t, [c for c in cands if c["id"] in set(g["checks"])], T.ex)
        k, n, _, _ = T.gamma(conj(VT, g["checks"], len(T.cor))); tg.append(k / n)
    out["gold_only_sql_test_gamma"] = {"per_draw": tg, "mean": float(np.mean(tg))}
    # (m8) CoNLL F1 without gold rows
    t = "ie"; A = Pool(t, f"data/pools/pool_{t}_admit_seed0.jsonl")
    cands = load_candidates(t, [f"out/candidates/{t}_*.jsonl"], A.ex); VA = verdict_matrix(t, cands, A.ex)
    keep = ~A.gold
    sub = Pool.__new__(Pool); sub.cor = A.cor[keep]; sub.gold = A.gold[keep]; sub.inst = A.inst[keep]; sub.n_inst = A.n_inst
    sub.M = A.M; sub.gnames = A.gnames; sub.has = np.bincount(sub.inst, weights=sub.cor, minlength=sub.n_inst) > 0
    sub.n_g = (sub.M & sub.has[:, None]).sum(0)
    sel = greedy({c: VA[c][keep] for c in VA}, sub, [c["id"] for c in cands], "f1")
    tp = int(sub.cor.sum()); fp = int((~sub.cor).sum())
    out["f1_without_gold_ie"] = {"takes_deleter": DELETER in sel, "n_checks": len(sel), "F1_0": 2 * tp / (2 * tp + fp)}
    print("m6", out["gold_only_sql_test_gamma"], "m8", out["f1_without_gold_ie"], flush=True)
    json.dump(out, open(a.out, "w"), indent=1, default=float)
    return 0


if __name__ == "__main__":
    sys.exit(main())
