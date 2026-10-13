"""
certver.resample_detail -- per-replicate detail of robust.py's resampling study.

  python -m certver.resample_detail --task ie --out out/resample_detail_ie.json
  python -m certver.resample_detail --task fewnerd --inject out/candidates_inject/fewnerd.jsonl \
      --out out/resample_detail_fewnerd_inject.json

Replays robust.py's random stream exactly (default_rng(0); per replicate a
bootstrap of A's inputs, then a random 70% of the LLM-written candidates plus
all hand-written ones) and records, per replicate: which "isolating" candidates
were available (candidates that alone wipe >= 50% of some group with >= 50
inputs on A), and for each selector whether it deletes a group on B. Adds an
OUTPUT-LEVEL budget selector (SPADE-style constraint: false-failure rate over
correct model outputs <= budget, gold excluded) next to the input-level one.
Budget as in robust.py's resampling: 1% on A (tau = 2%).
"""
from __future__ import annotations
import argparse, json, sys
import numpy as np

from .robust import Pool, greedy, certify, conj, MIN_N
from .curve import verdict_matrix, load_candidates, select_apv


def greedy_output_level(V, P, cands, budget):
    """Max catch s.t. false-failure rate over correct MODEL outputs <= budget."""
    acc = np.ones(len(P.cor), dtype=bool); chosen = []
    model_cor = P.cor & ~P.gold; ncor = max(1, model_cor.sum())
    while True:
        best, bv = None, 0
        for c in cands:
            if c in chosen:
                continue
            new = acc & V[c]
            if ((~new) & model_cor).sum() / ncor > budget:
                continue
            val = int(((acc & ~new) & ~P.cor).sum())
            if val > bv:
                best, bv = c, val
        if best is None:
            return chosen
        chosen.append(best); acc &= V[best]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", required=True); ap.add_argument("--inject", default=None)
    ap.add_argument("--replicates", type=int, default=200); ap.add_argument("--out", required=True)
    ap.add_argument("--budget", type=float, default=0.01, help="empirical budget on A (tau/2); 0.01 = tau 2%")
    a = ap.parse_args(argv); t = a.task
    A = Pool(t, f"data/pools/pool_{t}_admit_seed0.jsonl")
    B = Pool(t, f"data/pools/pool_{t}_certify_seed0.jsonl", A.km, A.vec, A.gnames)
    cands = load_candidates(t, [f"out/candidates/{t}_*.jsonl"] + ([a.inject] if a.inject else []), A.ex)
    VA = verdict_matrix(t, cands, A.ex); VB = verdict_matrix(t, cands, B.ex)
    hw = [c["id"] for c in cands if c["id"].startswith("hw:")]
    synth = [c["id"] for c in cands if not c["id"].startswith("hw:")]
    big = A.n_g >= MIN_N
    isolating = []
    for c in synth + hw:
        w = A.wiped(VA[c]); wg = (A.M & w[:, None]).sum(0)
        if np.any(np.where(big, wg / np.maximum(1, A.n_g), 0) >= 0.5):
            isolating.append(c)
    G = int((B.n_g >= MIN_N).sum())
    rng = np.random.default_rng(0)
    inst_rows = {}
    for i, ii in enumerate(A.inst):
        inst_rows.setdefault(ii, []).append(i)
    reps = []
    for rep in range(a.replicates):
        pick = rng.integers(0, A.n_inst, A.n_inst)
        rows_idx = np.concatenate([inst_rows[p] for p in pick])
        sub = Pool.__new__(Pool)
        sub.cor = A.cor[rows_idx]; sub.gold = A.gold[rows_idx]
        sub.inst = np.repeat(np.arange(len(pick)), [len(inst_rows[p]) for p in pick]); sub.n_inst = len(pick)
        sub.M = A.M[pick]; sub.gnames = A.gnames
        sub.has = np.bincount(sub.inst, weights=sub.cor, minlength=sub.n_inst) > 0
        sub.n_g = (sub.M & sub.has[:, None]).sum(0)
        Vs = {c: VA[c][rows_idx] for c in synth + hw}
        cs = list(rng.choice(synth, size=max(1, int(0.7 * len(synth))), replace=False)) + hw
        sels = {"f1": greedy(Vs, sub, cs, "f1"),
                "apv": select_apv({k: Vs[k] for k in cs}, sub.cor),
                "f1_constrained": greedy(Vs, sub, cs, "f1", budget=a.budget),
                "budgeted": greedy(Vs, sub, cs, "catch", budget=a.budget),
                "group": greedy(Vs, sub, cs, "catch", budget=a.budget, group=True),
                "output_level": greedy_output_level(Vs, sub, cs, a.budget)}
        r = {"available_isolating": sorted(set(cs) & set(isolating))}
        for k, ids in sels.items():
            accB = conj(VB, ids, len(B.cor))
            c = certify(B, accB, 0.05, 0.05 / max(1, G))
            wB = B.wiped(accB); wgB = (B.M & wB[:, None]).sum(0); bigB = B.n_g >= MIN_N
            r[k] = {"deleted": bool(c["worst_group_wiped_frac"] >= 0.5), "worst": c["worst_group_wiped"],
                    "worst_frac": c["worst_group_wiped_frac"],
                    "wiped_frac": {g: float(wgB[j] / max(1, B.n_g[j])) for j, g in enumerate(B.gnames) if bigB[j]},
                    "isolating_taken": sorted(set(ids) & set(isolating)), "catch": c["catch"], "gamma_k": c["k"]}
        reps.append(r)
        if (rep + 1) % 25 == 0:
            print(f"  {rep + 1}/{a.replicates}", flush=True)
    summ = {}
    for k in ("f1", "apv", "f1_constrained", "budgeted", "group", "output_level"):
        av = [r for r in reps if r["available_isolating"]]; na = [r for r in reps if not r["available_isolating"]]
        summ[k] = {"deletion_rate": float(np.mean([r[k]["deleted"] for r in reps])),
                   "deletion_rate_if_isolating_available": float(np.mean([r[k]["deleted"] for r in av])) if av else None,
                   "deletion_rate_if_not_available": float(np.mean([r[k]["deleted"] for r in na])) if na else None,
                   "takes_isolating_if_available": float(np.mean([bool(r[k]["isolating_taken"]) for r in av])) if av else None,
                   "catch_mean": float(np.mean([r[k]["catch"] for r in reps])),
                   "n_available": len(av), "n_not_available": len(na)}
        print(k, summ[k], flush=True)
    json.dump({"task": t, "inject": a.inject, "budget": a.budget, "isolating": isolating, "summary": summ, "replicates": reps},
              open(a.out, "w"), indent=1, default=float)
    return 0


if __name__ == "__main__":
    sys.exit(main())
