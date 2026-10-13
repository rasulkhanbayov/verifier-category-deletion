"""
certver.curve -- certified false-rejection budget: select on A, certify on B,
evaluate on test, for a sweep of budgets tau.

  python -m certver.curve --task sql \
      --candidates out/candidates/sql_*.jsonl \
      --admit data/pools/pool_sql_admit_seed0.jsonl \
      --certify data/pools/pool_sql_certify_seed0.jsonl \
      --test data/pilot/pool_sql_test_seed0.jsonl \
      --taus 0 0.0025 0.005 0.01 0.02 0.05 --out out/curve_sql.json

Selection (split A only): start from the empty conjunction; repeatedly add
the candidate that catches the most additional incorrect outputs while the
conjunction's false-rejection rate on A stays <= tau/2 (half the budget, so
the bound on B has room). Stop when nothing adds catch.
Certification (split B only, never used for selection): k false rejections
among n correct outputs; 95% one-sided Clopper-Pearson upper bound U
(3/n when k = 0). The verifier is CERTIFIED at tau iff U <= tau.
Instance-level ("itau=") rows are certified with the Clopper-Pearson bound at
level 1 - 0.05/len(taus) (Bonferroni over the budget grid, because the
reported budget is the smallest certified one); B_gamma_upper95 keeps the
uncorrected 95% bound for reference, B_gamma_upper is the corrected one.
(Before 2026-10-13 certification used the uncorrected bound; on all six
tasks the picked budget is the same either way.)
Evaluation (test): per model, delta, eps, the closed-form asymptotic gain of
reject-gated selection (Thm. 1 of version3, valid for delta > 0), and the
empirical gated best-of-N accuracy on the actual pool.
"""
from __future__ import annotations
import argparse, glob, hashlib, json, os, sys
import numpy as np

from .admit import load_examples, verdicts_for, _hw_names, _upper_bound

CACHE_DIR = "out/verdicts"


def _pool_sig(examples) -> str:
    h = hashlib.sha1()
    for e in examples:
        h.update(f"{e['model']}|{e['instance_id']}|{e['cand_idx']}|{e['raw']}\n".encode())
    return h.hexdigest()[:16]


def cached_verdicts(task, cand, examples, sig):
    src_h = hashlib.sha1((cand.get("source") or cand["id"]).encode()).hexdigest()[:10]
    d = os.path.join(CACHE_DIR, sig)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"{cand['id'].replace(':', '_')}_{src_h}.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    v = verdicts_for(task, cand, examples)
    if v is not None:
        with open(path, "w") as f:
            json.dump(v, f)
    return v


def verdict_matrix(task, cands, examples):
    import concurrent.futures
    sig = _pool_sig(examples)
    out = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=int(os.environ.get("CERTVER_ADMIT_WORKERS", "8"))) as ex:
        futs = {ex.submit(cached_verdicts, task, c, examples, sig): c["id"] for c in cands}
        for fu in concurrent.futures.as_completed(futs):
            v = fu.result()
            if v is not None:
                out[futs[fu]] = np.array(v, dtype=bool)
    return out


def load_candidates(task, patterns, examples):
    cands, seen = [], set()
    for pat in patterns:
        for p in sorted(glob.glob(pat)):
            if p.endswith(".jsonl"):
                for line in open(p):
                    if line.strip():
                        c = json.loads(line)
                        if c["id"] not in seen:
                            seen.add(c["id"]); cands.append(c)
    cands += [{"id": f"hw:{n}", "name": f"hw:{n}", "source": None} for n in _hw_names(examples)]
    return cands


def select(V, correct, budget):
    """Greedy on split A. Returns list of candidate ids."""
    n_c = correct.sum()
    inc = ~correct
    acc = np.ones(len(correct), dtype=bool)
    chosen = []
    while True:
        best, best_gain = None, 0
        for cid, v in V.items():
            if cid in chosen:
                continue
            new = acc & v
            if (~new & correct).sum() / n_c > budget:
                continue
            gain = (acc & inc).sum() - (new & inc).sum()
            if gain > best_gain:
                best, best_gain = cid, gain
        if best is None:
            return chosen
        chosen.append(best)
        acc &= V[best]


def groups_of(examples):
    """Instance index per example (instances are the independent units)."""
    ids = {}
    return np.array([ids.setdefault(e["instance_id"], len(ids)) for e in examples])


def gamma_counts(acc, correct, groups):
    """(k, n): k instances on which the verifier rejects ANY correct output,
    out of n instances that have at least one correct output. gamma = k/n
    bounds the instance-averaged false-rejection rate and is the coverage loss."""
    ng = groups.max() + 1
    has = np.bincount(groups, weights=correct, minlength=ng) > 0
    hit = np.bincount(groups, weights=(~acc & correct), minlength=ng) > 0
    return int(hit.sum()), int(has.sum())


def select_inst(V, correct, groups, budget):
    """Greedy on split A, constraint on instance-level gamma instead of delta."""
    inc = ~correct
    acc = np.ones(len(correct), dtype=bool)
    chosen = []
    while True:
        best, best_gain = None, 0
        for cid, v in V.items():
            if cid in chosen:
                continue
            new = acc & v
            k, n = gamma_counts(new, correct, groups)
            if k / n > budget:
                continue
            gain = (acc & inc).sum() - (new & inc).sum()
            if gain > best_gain:
                best, best_gain = cid, gain
        if best is None:
            return chosen
        chosen.append(best)
        acc &= V[best]


def _f1(acc, correct):
    tp = (acc & correct).sum(); fp = (acc & ~correct).sum(); fn = (~acc & correct).sum()
    return 2 * tp / max(1, 2 * tp + fp + fn)


def select_f1(V, correct):
    """AutoPyVerifier-style baseline: greedily add the check that most improves
    F1 of `accept` as a predictor of `correct` on split A. No soundness
    constraint; stops when no check improves F1."""
    acc = np.ones(len(correct), dtype=bool)
    chosen, cur = [], _f1(acc, correct)
    while True:
        best, best_f1 = None, cur
        for cid, v in V.items():
            if cid in chosen:
                continue
            f = _f1(acc & v, correct)
            if f > best_f1 + 1e-12:
                best, best_f1 = cid, f
        if best is None:
            return chosen
        chosen.append(best); acc &= V[best]; cur = best_f1


def _apv_stats(acc, correct, delta=0.05):
    """AutoPyVerifier's objective (megagonlabs/AutoPyVerifier, metrics.py):
    macro-F1 over accept/reject, feasible iff Hoeffding lower bounds of
    P(correct|accept) and P(incorrect|reject) are both >= 0.5."""
    import math
    tp = int((acc & correct).sum()); acc_n = int(acc.sum())
    tn = int((~acc & ~correct).sum()); rej_n = int((~acc).sum())
    fp, fn = acc_n - tp, rej_n - tn
    def f1(p, r): return 2 * p * r / (p + r) if p + r > 0 else 0.0
    pp = tp / acc_n if acc_n else 0.0; npv = tn / rej_n if rej_n else 0.0
    rp = tp / (tp + fn) if tp + fn else 0.0; rn = tn / (tn + fp) if tn + fp else 0.0
    score = 0.5 * (f1(pp, rp) + f1(npv, rn))
    lcb = lambda m, d: max(0.0, m - math.sqrt(math.log(2 / delta) / (2 * d))) if d > 0 else 0.0
    return score, lcb(pp, acc_n) >= 0.5 and lcb(npv, rej_n) >= 0.5


def select_apv(V, correct):
    """AutoPyVerifier-objective baseline on OUR candidate pool: greedy forward
    selection maximising macro-F1 among feasible bundles (their final rule:
    highest score, then smallest size). Their LLM critique/refine DAG search
    is not reproduced (it needs LLM calls)."""
    acc = np.ones(len(correct), dtype=bool)
    chosen, cur = [], -1.0
    while True:
        best, best_s = None, cur
        for cid, v in V.items():
            if cid in chosen:
                continue
            s, feas = _apv_stats(acc & v, correct)
            if feas and s > best_s + 1e-12:
                best, best_s = cid, s
        if best is None:
            return chosen
        chosen.append(best); acc &= V[best]; cur = best_s


def conj(V, ids, n):
    acc = np.ones(n, dtype=bool)
    for i in ids:
        acc &= V[i]
    return acc


def gated_bon(examples, acc, N, rng_seed=0):
    """Expected accuracy of reject-gated selection with N samples, computed
    exactly from the pool per instance: if base accepted -> base; else the
    first accepted among N samples drawn without replacement (expectation =
    precision of the accepted samples, conditioned on >=1 accepted); else base."""
    by = {}
    for e, a in zip(examples, acc):
        by.setdefault((e["model"], e["instance_id"]), []).append((e["cand_idx"], e["correct"], bool(a)))
    res = {}
    from math import comb
    for (m, iid), rows in by.items():
        base = [r for r in rows if r[0] == -1]
        samp = [r for r in rows if r[0] >= 0]
        if not base or not samp:
            continue
        b_cor, b_acc = base[0][1], base[0][2]
        if b_acc:
            val = float(b_cor)
        else:
            S, A = len(samp), sum(r[2] for r in samp)
            n = min(N, S)
            p_none = comb(S - A, n) / comb(S, n) if S - A >= n else 0.0
            prec = (sum(r[1] and r[2] for r in samp) / A) if A else 0.0
            val = (1 - p_none) * prec + p_none * float(b_cor)
        res.setdefault(m, []).append((val, float(b_cor)))
    return {m: (float(np.mean([v for v, _ in r])), float(np.mean([b for _, b in r])), len(r))
            for m, r in res.items()}


def rates(examples, acc):
    out = {}
    for m in sorted({e["model"] for e in examples}):
        idx = [i for i, e in enumerate(examples) if e["model"] == m]
        cor = np.array([examples[i]["correct"] for i in idx])
        a = acc[idx]
        base = np.array([examples[i]["cand_idx"] == -1 for i in idx])
        p0 = cor[base].mean(); p = cor[~base].mean()
        delta = (~a & cor).sum() / max(1, cor.sum())
        eps = (a & ~cor).sum() / max(1, (~cor).sum())
        q = p * (1 - delta) + (1 - p) * eps
        r = p * (1 - delta) / q if q > 0 else 0.0
        a_inf = p0 * (1 - delta) + (p0 * delta + (1 - p0) * (1 - eps)) * r if q > 0 else p0
        out[m] = {"p0": float(p0), "p": float(p), "delta": float(delta), "eps": float(eps),
                  "gain_inf_pts": float(100 * (a_inf - p0)),
                  "worst_case_loss_pts": float(100 * p0 * delta)}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", required=True)
    ap.add_argument("--candidates", nargs="+", required=True)
    ap.add_argument("--admit", required=True)
    ap.add_argument("--certify", required=True)
    ap.add_argument("--test", default=None)
    ap.add_argument("--taus", nargs="+", type=float, default=[0, 0.0025, 0.005, 0.01, 0.02, 0.05])
    ap.add_argument("--N", nargs="+", type=int, default=[8, 32])
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)

    exA = load_examples(a.task, a.admit)
    cands = load_candidates(a.task, a.candidates, exA)
    print(f"{len(cands)} candidates; computing verdicts on A ({len(exA)} examples)", flush=True)
    VA = verdict_matrix(a.task, cands, exA)
    corA = np.array([e["correct"] for e in exA])
    exB = load_examples(a.task, a.certify)
    exT = [e for e in load_examples(a.task, a.test) if e["model"] != "gold"] if a.test else None
    hw_ids = [c["id"] for c in cands if c["id"].startswith("hw:")]

    results = []
    selections = {"handwritten": hw_ids}
    for tau in a.taus:
        selections[f"tau={tau}"] = select(VA, corA, tau / 2)
    gA = groups_of(exA)
    for tau in a.taus:
        selections[f"itau={tau}"] = select_inst(VA, corA, gA, tau / 2)
    selections["f1_baseline"] = select_f1(VA, corA)
    selections["apv_baseline"] = select_apv(VA, corA)
    needed = {cid for ids in selections.values() for cid in ids}
    sub = [c for c in cands if c["id"] in needed]
    print(f"certifying {len(needed)} distinct checks on B ({len(exB)} examples)", flush=True)
    VB = verdict_matrix(a.task, sub, exB)
    corB = np.array([e["correct"] for e in exB])
    gB = groups_of(exB)
    VT = verdict_matrix(a.task, sub, exT) if exT else None

    for name, ids in selections.items():
        accA = conj(VA, ids, len(exA)); accB = conj(VB, ids, len(exB))
        kB = int((~accB & corB).sum()); nB = int(corB.sum())
        U = _upper_bound(kB, nB)
        tau = float(name.split("=")[1]) if "tau=" in name else None
        gkA, gnA = gamma_counts(accA, corA, gA)
        gkB, gnB = gamma_counts(accB, corB, gB)
        gU = _upper_bound(gkB, gnB)
        from scipy.stats import beta as _beta
        gUb = 1.0 if gkB >= gnB else float(_beta.ppf(1 - 0.05 / len(a.taus), gkB + 1, gnB - gkB))
        certified = None
        if name.startswith("tau="):
            certified = U <= tau          # output-level (treats outputs as independent)
        elif name.startswith("itau="):
            certified = gUb <= tau        # instance-level, Bonferroni over the budget grid
        row = {"selection": name, "n_checks": len(ids), "checks": ids,
               "A_gamma": gkA / gnA, "B_gamma_k": gkB, "B_gamma_n": gnB, "B_gamma_upper95": gU, "B_gamma_upper": gUb,
               "A_delta": float((~accA & corA).sum() / corA.sum()),
               "A_catch": float((~accA & ~corA).sum() / max(1, (~corA).sum())),
               "B_false_rejections": kB, "B_n_correct": nB, "B_delta_upper95": U,
               "B_catch": float((~accB & ~corB).sum() / max(1, (~corB).sum())),
               "certified": certified}
        if exT:
            accT = conj(VT, ids, len(exT))
            row["test_rates"] = rates(exT, accT)
            corT = np.array([e["correct"] for e in exT])
            row["test_gamma"] = {}
            for m in sorted({e["model"] for e in exT}):
                mi = np.array([e["model"] == m for e in exT])
                k, n = gamma_counts(accT[mi], corT[mi], groups_of([e for e in exT if e["model"] == m]))
                row["test_gamma"][m] = k / max(1, n)
            row["test_gated_bon"] = {f"N={N}": gated_bon(exT, accT, N) for N in a.N}
        results.append(row)
        print(f"{name:14s} checks={len(ids):2d} A: delta={row['A_delta']:.4f} catch={row['A_catch']:.3f} | "
              f"B: k={kB}/{nB} U95={U:.4f} gamma={gkB}/{gnB} gU95={gU:.4f} catch={row['B_catch']:.3f} "
              f"{'CERTIFIED' if row['certified'] else ('' if tau is None else 'not certified')}", flush=True)
        if exT:
            for m, r in row["test_rates"].items():
                g = row["test_gated_bon"][f"N={max(a.N)}"].get(m)
                print(f"    test {m.split('/')[-1][:24]:24s} delta={r['delta']:.4f} gamma={row['test_gamma'][m]:.3f} eps={r['eps']:.3f} "
                      f"gain_inf={r['gain_inf_pts']:+.2f}pts  gated@N{max(a.N)}={100*g[0]:.1f} vs base {100*g[1]:.1f}", flush=True)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w") as f:
        json.dump({"task": a.task, "taus": a.taus, "results": results}, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
