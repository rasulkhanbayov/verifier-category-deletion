"""
certver.f1rule -- when does F1/agreement selection delete a group?

  python -m certver.f1rule --out out/f1rule.json

Fact: adding a check whose newly rejected rows have precision p (share of
correct outputs, gold rows included) raises F1 = 2TP/(2TP+FP+FN) iff
p < F1/2. Verified here on every candidate (added to the empty verifier) for
all six tasks. Also reports, on split A, the groups whose rows have
precision below F1_0/2 ("deletable" if a check isolates them), the
candidates that wipe >= 30% of some group, and, for the injected stress-test
checks (out/candidates_inject/), their rejected-row precision and the greedy
F1 step at which they are picked (with the threshold F1/2 at that step).
"""
from __future__ import annotations
import argparse, json, os, sys
import numpy as np

from .robust import Pool, _f1, greedy, MIN_N
from .curve import verdict_matrix, load_candidates

TASKS = ["ie", "fewnerd", "fc", "sql", "math", "morph"]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    res = {}
    for t in TASKS:
        A = Pool(t, f"data/pools/pool_{t}_admit_seed0.jsonl")
        inj = f"out/candidates_inject/{t}.jsonl"
        cands = load_candidates(t, [f"out/candidates/{t}_*.jsonl"] + ([inj] if os.path.exists(inj) else []), A.ex)
        V = verdict_matrix(t, cands, A.ex)
        base = _f1(np.ones(len(A.cor), bool), A.cor)
        n = agree = 0
        for c in cands:
            if c["id"].startswith("inj:"):
                continue
            rej = ~V[c["id"]]
            d = _f1(V[c["id"]], A.cor) - base
            if not rej.any() or abs(d) < 1e-12:
                continue
            n += 1; agree += int((A.cor[rej].mean() < base / 2) == (d > 0))
        gi = A.M[A.inst]; big = A.n_g >= MIN_N
        prec_g = {A.gnames[j]: float(A.cor[gi[:, j]].mean()) for j in range(len(A.gnames)) if big[j]}
        wipers = []
        for c in cands:
            if c["id"].startswith("inj:"):
                continue
            w = A.wiped(V[c["id"]]); wg = (A.M & w[:, None]).sum(0)
            frac = np.where(big, wg / np.maximum(1, A.n_g), 0); j = int(np.argmax(frac))
            if frac[j] >= 0.3:
                wipers.append({"id": c["id"], "group": A.gnames[j], "wiped": float(frac[j]),
                               "group_deletable": bool(prec_g[A.gnames[j]] < base / 2),
                               "solo_dF1": float(_f1(V[c["id"]], A.cor) - base)})
        sel = greedy(V, A, [c["id"] for c in cands], "f1")
        acc = np.ones(len(A.cor), bool); step = {}
        for i, c in enumerate(sel):
            step[c] = (i, _f1(acc, A.cor) / 2); acc &= V[c]
        injected = []
        for c in cands:
            if c["id"].startswith("inj:"):
                r = ~V[c["id"]]
                injected.append({"id": c["id"], "rejected_frac": float(r.mean()), "precision": float(A.cor[r].mean()),
                                 "solo_dF1": float(_f1(V[c["id"]], A.cor) - base),
                                 "picked_step": step.get(c["id"], (None, None))[0],
                                 "threshold_at_step": step.get(c["id"], (None, None))[1]})
        res[t] = {"F1_0": base, "threshold": base / 2, "rule_checked": n, "rule_agrees": agree,
                  "group_precision": prec_g, "deletable": [g for g, p in prec_g.items() if p < base / 2],
                  "wipers": wipers, "injected": injected}
        print(f"{t}: rule {agree}/{n}; deletable {res[t]['deletable']}; wipers of deletable groups "
              f"{[w['id'] for w in wipers if w['group_deletable']]}; injected picked "
              f"{[x['id'] for x in injected if x['picked_step'] is not None]}", flush=True)
    json.dump(res, open(a.out, "w"), indent=1, default=float)
    return 0


if __name__ == "__main__":
    sys.exit(main())
