"""
certver.figdata -- data for the mechanism figure (paper/make_figures.py).

  python -m certver.figdata --out out/figdata_mechanism.json

Per task, for every candidate check added alone to the empty verifier on
split A: precision of the outputs it rejects (gold included), the largest
fraction of any group (>= 50 inputs) whose inputs it loses entirely, the
change in F1, and flags (the CoNLL deleting check, Few-NERD stress-test
checks, the casing check from the natural feedback round, chosen by F1).
"""
from __future__ import annotations
import argparse, json, sys
import numpy as np
from .robust import Pool, _f1, greedy, MIN_N
from .curve import verdict_matrix, load_candidates

TASKS = ["ie", "fewnerd", "fc", "sql", "math", "morph"]


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); a = ap.parse_args(argv)
    res = {}
    for t in TASKS:
        A = Pool(t, f"data/pools/pool_{t}_admit_seed0.jsonl")
        pats = [f"out/candidates/{t}_*.jsonl"]
        if t == "fewnerd":
            pats += ["out/candidates_inject/fewnerd.jsonl", "out/candidates_e5/fewnerd_round1_*.jsonl"]
        cands = load_candidates(t, pats, A.ex)
        V = verdict_matrix(t, cands, A.ex)
        base = _f1(np.ones(len(A.cor), bool), A.cor); big = A.n_g >= MIN_N
        f1sel = set(greedy(V, A, [c["id"] for c in cands if not c["id"].startswith(("inj:",)) and "round1" not in c["id"]], "f1"))
        pts = []
        for c in cands:
            r = ~V[c["id"]]
            if not r.any():
                continue
            w = A.wiped(V[c["id"]]); wg = (A.M & w[:, None]).sum(0)
            frac = np.where(big, wg / np.maximum(1, A.n_g), 0)
            kind = ("injected" if c["id"].startswith("inj:") else "casing" if c["id"] == "fewnerd-r1_gpt4o-3815bf311d"
                    else "feedback" if "round1" in c["id"] else "deleter" if c["id"] == "ie-r0-84f7d14832" else "pool")
            pts.append({"id": c["id"], "kind": kind, "precision": float(A.cor[r].mean()), "max_wiped": float(frac.max()),
                        "group": A.gnames[int(np.argmax(frac))], "dF1": float(_f1(V[c["id"]], A.cor) - base),
                        "f1_selected": c["id"] in f1sel})
        res[t] = {"threshold": base / 2, "points": pts}
        print(t, len(pts), "threshold %.3f" % (base / 2), flush=True)
    json.dump(res, open(a.out, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
