"""
certver.robust -- v4.1 analysis: group-conditional selection, corrected
certification, like-with-like validity, resampling study.

  python -m certver.robust --task ie --out out/robust_ie.json [--replicates 200]

Groups (fixed before any v4.1 result was seen):
  * pre-registered gold-defined subgroups (certver.filtering.subgroups, fixed
    2026-10-08);
  * k-means clusters (k=8) of character n-gram TF-IDF vectors of the INPUT
    (no gold), fit on split A, so categories nobody anticipated are covered.
A group counts only where it has >= MIN_N instances.

Selectors on split A, budget tau (selection constraint tau/2):
  handwritten, strong_handwritten (IE/morph), f1, f1_constrained,
  budgeted (overall gamma), group (gamma in every group AND overall).
Certification on B: Clopper-Pearson upper bounds with Bonferroni over the
three budgets {1,2,5}% (alpha = 0.05/3), and additionally over groups for the
group certificate (alpha = 0.05/(3 G)).
Like-with-like: on test pools restructured like B (data/test_bstruct: gold
plus greedy + 3 samples per model), test gamma overall and per group vs U_B.
Resampling: bootstrap A's instances and draw a random 70% of synthesised
candidates; per selector, rate of "some group (n >= MIN_N) loses >= 50% of
its instances entirely on B" (every correct output, gold included,
rejected), worst-group wiped fraction, catch on B, and coverage of U_B on
test_bstruct.
"""
from __future__ import annotations
import argparse, glob, json, os, sys
import numpy as np
from scipy.stats import beta

from .admit import load_examples
from .curve import verdict_matrix, load_candidates
from .filtering import subgroups

BUDGETS = (0.01, 0.02, 0.05)
TAU_G = 0.20   # per-group certified budget: no group may lose more than this (two-level guarantee)
MIN_N = 50
K = 8


def cp_upper(k, n, alpha):
    if n == 0:
        return 1.0
    if k >= n:
        return 1.0
    return float(beta.ppf(1 - alpha, k + 1, n - k))


def _input_text(task, ctx):
    return ctx.get("question") or ctx.get("text") or ctx.get("surface") or ctx.get("request") or ""


class Pool:
    """One split: examples, per-instance structure and group memberships."""

    def __init__(self, task, path, km=None, vec=None, gnames=None):
        self.ex = load_examples(task, path)
        items = {json.loads(l)["instance_id"]: json.loads(l)
                 for l in open(path.replace(".jsonl", ".items.jsonl")) if l.strip()}
        ids = {}
        self.inst = np.array([ids.setdefault(e["instance_id"], len(ids)) for e in self.ex])
        self.iids = list(ids)
        self.cor = np.array([e["correct"] for e in self.ex])
        self.gold = np.array([e["model"] == "gold" for e in self.ex])
        self.n_inst = len(ids)
        texts = [_input_text(task, items[i]) for i in self.iids]
        if km is None:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.cluster import KMeans
            vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=2, max_features=20000)
            X = vec.fit_transform(texts)
            km = KMeans(n_clusters=K, random_state=0, n_init=10).fit(X)
        clus = km.predict(vec.transform(texts))
        self.km, self.vec = km, vec
        labels = [set(subgroups(task, items[i])) | {f"cluster_{c}"} for i, c in zip(self.iids, clus)]
        self.gnames = gnames or sorted({g for s in labels for g in s})
        self.M = np.array([[g in s for g in self.gnames] for s in labels], dtype=bool)
        self.has = np.bincount(self.inst, weights=self.cor, minlength=self.n_inst) > 0
        self.n_g = (self.M & self.has[:, None]).sum(0)

    def hit(self, acc, rows=None):
        """per-instance: some correct output rejected"""
        bad = (~acc) & self.cor
        return np.bincount(self.inst, weights=bad, minlength=self.n_inst) > 0

    def wiped(self, acc):
        """per-instance: every correct output rejected (gold included)"""
        kept = acc & self.cor
        k = np.bincount(self.inst, weights=kept, minlength=self.n_inst) > 0
        return self.has & ~k

    def gamma(self, acc):
        h = self.hit(acc)
        return int(h.sum()), int(self.has.sum()), (self.M & h[:, None]).sum(0), self.n_g


def conj(V, ids, n):
    a = np.ones(n, dtype=bool)
    for i in ids:
        a &= V[i]
    return a


def _f1(acc, cor):
    tp = (acc & cor).sum(); fp = (acc & ~cor).sum(); fn = (~acc & cor).sum()
    return 2 * tp / max(1, 2 * tp + fp + fn)


def greedy(V, P, cands, objective, budget=None, group=False):
    """Greedy selection on pool P. objective: 'catch' or 'f1'. budget: tau/2
    constraint on overall gamma (and per group if group=True)."""
    acc = np.ones(len(P.cor), dtype=bool)
    chosen = []
    big = P.n_g >= MIN_N
    cur = _f1(acc, P.cor) if objective == "f1" else 0
    while True:
        best, best_val = None, None
        for c in cands:
            if c in chosen:
                continue
            new = acc & V[c]
            if budget is not None:
                k, n, kg, ng = P.gamma(new)
                if k / max(1, n) > budget:
                    continue
                if group and np.any((kg[big] / np.maximum(1, ng[big])) > budget):
                    continue
            if objective == "f1":
                val = _f1(new, P.cor)
                if val <= cur + 1e-12:
                    continue
            else:
                val = int(((acc & ~new) & ~P.cor).sum())
                if val <= 0:
                    continue
            if best_val is None or val > best_val:
                best, best_val = c, val
        if best is None:
            return chosen
        chosen.append(best); acc &= V[best]
        if objective == "f1":
            cur = best_val


def certify(P, acc, alpha, group_alpha=None):
    k, n, kg, ng = P.gamma(acc)
    out = {"k": k, "n": n, "U": cp_upper(k, n, alpha)}
    big = ng >= MIN_N
    if group_alpha is not None:
        Ug = [cp_upper(int(a), int(b), group_alpha) for a, b in zip(kg[big], ng[big])]
        out["U_group_max"] = max(Ug) if Ug else 0.0
        out["worst_group"] = [g for g, b in zip(P.gnames, big) if b][int(np.argmax(Ug))] if Ug else None
    w = P.wiped(acc)
    wg = (P.M & w[:, None]).sum(0)
    frac = np.where(big, wg / np.maximum(1, ng), 0)
    out["worst_group_wiped_frac"] = float(frac.max()) if big.any() else 0.0
    out["worst_group_wiped"] = P.gnames[int(np.argmax(frac))] if big.any() else None
    out["catch"] = float(((~acc) & ~P.cor).sum() / max(1, (~P.cor).sum()))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", required=True)
    ap.add_argument("--pools", default="data/pools")
    ap.add_argument("--replicates", type=int, default=200)
    ap.add_argument("--inject", default=None,
                    help="stress test: extra candidate file(s) added to the synthesised pool")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    t = a.task
    A = Pool(t, f"{a.pools}/pool_{t}_admit_seed0.jsonl")
    B = Pool(t, f"{a.pools}/pool_{t}_certify_seed0.jsonl", A.km, A.vec, A.gnames)
    tpaths = [f"data/test_bstruct/pool_{t}_test_seed{s}.jsonl" for s in (0, 1, 2)]
    Ts = [Pool(t, p, A.km, A.vec, A.gnames) for p in tpaths
          if os.path.exists(p) and os.path.getsize(p) > 0]
    if not Ts:
        print("  no test pools: test-side analyses skipped (B-only)", flush=True)
    pats = [f"out/candidates/{t}_*.jsonl"] + ([a.inject] if a.inject else [])
    cands = load_candidates(t, pats, A.ex)
    strong = []
    sp = f"out/candidates_strong/{t}.jsonl"
    if os.path.exists(sp):
        strong = [json.loads(l) for l in open(sp) if l.strip()]
    allc = cands + strong
    print(f"{t}: {len(cands)} candidates (+{len(strong)} strong hw); groups {len(A.gnames)}; "
          f"B groups with n>={MIN_N}: {int((B.n_g >= MIN_N).sum())}", flush=True)
    import time as _time
    t0 = _time.time()
    VA = verdict_matrix(t, allc, A.ex)
    print(f"  verdicts A done ({len(A.ex)} rows) {_time.time() - t0:.0f}s", flush=True)
    VB = verdict_matrix(t, allc, B.ex)
    print(f"  verdicts B done ({len(B.ex)} rows) {_time.time() - t0:.0f}s", flush=True)
    VT = [verdict_matrix(t, allc, T.ex) for T in Ts]
    print(f"  verdicts test_bstruct done {_time.time() - t0:.0f}s", flush=True)
    hw = [c["id"] for c in cands if c["id"].startswith("hw:")]
    hw_sound = [c for c in hw if not c.endswith("concatenates")] if t == "morph" else hw
    synth = [c["id"] for c in cands if not c["id"].startswith("hw:")]
    pool_ids = synth + hw
    G = int((B.n_g >= MIN_N).sum())
    alpha = 0.05 / len(BUDGETS)
    galpha = 0.05 / (len(BUDGETS) * max(1, G))

    def evaluate(ids, label, budget=None):
        accB = conj(VB, ids, len(B.cor))
        cert = certify(B, accB, alpha, galpha)
        row = {"selection": label, "budget": budget, "n_checks": len(ids), "checks": ids, "B": cert}
        tg, tgg = [], []
        for T, V in zip(Ts, VT):
            accT = conj(V, ids, len(T.cor))
            k, n, kg, ng = T.gamma(accT)
            tg.append(k / max(1, n))
            big = ng >= MIN_N
            tgg.append(float((kg[big] / np.maximum(1, ng[big])).max()) if big.any() else 0.0)
            row.setdefault("test_wiped_worst", []).append(certify(T, accT, alpha)["worst_group_wiped_frac"])
        row["test_gamma"] = tg
        row["test_gamma_worst_group"] = tgg
        row["holds_overall"] = bool(max(tg) <= cert["U"]) if tg else None
        row["holds_group"] = bool(max(tgg) <= cert["U_group_max"]) if tgg else None
        return row

    rows = [evaluate(hw, "handwritten")]
    if t == "morph":
        rows.append(evaluate(hw_sound, "handwritten_sound"))
    if strong:
        rows.append(evaluate(hw_sound + [c["id"] for c in strong], "strong_handwritten"))
    rows.append(evaluate(greedy(VA, A, pool_ids, "f1"), "f1"))
    from .curve import select_apv
    rows.append(evaluate(select_apv({k: VA[k] for k in pool_ids}, A.cor), "apv"))
    for b in BUDGETS:
        rows.append(evaluate(greedy(VA, A, pool_ids, "f1", budget=b / 2), "f1_constrained", b))
        rows.append(evaluate(greedy(VA, A, pool_ids, "catch", budget=b / 2), "budgeted", b))
        rows.append(evaluate(greedy(VA, A, pool_ids, "catch", budget=b / 2, group=True), "group", b))
    for r in rows:
        r["certified_overall"] = r["budget"] is not None and r["B"]["U"] <= r["budget"]
        r["certified_group"] = r["budget"] is not None and r["B"]["U"] <= r["budget"] and r["B"]["U_group_max"] <= TAU_G
        print(f"  {r['selection']:18s} tau={r['budget']} checks={r['n_checks']:2d} "
              f"B: k={r['B']['k']}/{r['B']['n']} U={100*r['B']['U']:.2f}% Ug={100*r['B']['U_group_max']:.2f}% "
              f"catch={100*r['B']['catch']:.1f}% worst-wiped={100*r['B']['worst_group_wiped_frac']:.1f}% "
              f"({r['B']['worst_group_wiped']}) | test gamma max={100*max(r['test_gamma'] or [0]):.2f}% "
              f"worst-group={100*max(r['test_gamma_worst_group'] or [0]):.2f}% "
              f"holds={r['holds_overall']}/{r['holds_group']}", flush=True)

    # ------------------------------------------------------------ resampling
    rng = np.random.default_rng(0)
    res = {k: {"deletion": 0, "worst": [], "catch": [], "cover": 0, "cover_group": 0}
           for k in ("f1", "apv", "f1_constrained", "budgeted", "group")}
    inst_rows = {}
    for i, ii in enumerate(A.inst):
        inst_rows.setdefault(ii, []).append(i)
    for rep in range(a.replicates):
        pick = rng.integers(0, A.n_inst, A.n_inst)
        rows_idx = np.concatenate([inst_rows[p] for p in pick])
        sub = Pool.__new__(Pool)
        sub.cor = A.cor[rows_idx]
        new_inst = np.repeat(np.arange(len(pick)), [len(inst_rows[p]) for p in pick])
        sub.inst = new_inst; sub.n_inst = len(pick)
        sub.M = A.M[pick]; sub.gnames = A.gnames
        sub.has = np.bincount(sub.inst, weights=sub.cor, minlength=sub.n_inst) > 0
        sub.n_g = (sub.M & sub.has[:, None]).sum(0)
        Vs = {c: VA[c][rows_idx] for c in pool_ids}
        cs = list(rng.choice(synth, size=max(1, int(0.7 * len(synth))), replace=False)) + hw
        from .curve import select_apv
        sels = {"f1": greedy(Vs, sub, cs, "f1"),
                "apv": select_apv({k: Vs[k] for k in cs}, sub.cor),
                "f1_constrained": greedy(Vs, sub, cs, "f1", budget=0.01),
                "budgeted": greedy(Vs, sub, cs, "catch", budget=0.01),
                "group": greedy(Vs, sub, cs, "catch", budget=0.01, group=True)}
        for k, ids in sels.items():
            accB = conj(VB, ids, len(B.cor))
            c = certify(B, accB, 0.05, 0.05 / max(1, G))
            res[k]["deletion"] += int(c["worst_group_wiped_frac"] >= 0.5)
            res[k]["worst"].append(c["worst_group_wiped_frac"]); res[k]["catch"].append(c["catch"])
            tgs, tggs = [], []
            for T, V in zip(Ts, VT):
                kk, nn, kg, ng = T.gamma(conj(V, ids, len(T.cor)))
                tgs.append(kk / max(1, nn)); big = ng >= MIN_N
                tggs.append(float((kg[big] / np.maximum(1, ng[big])).max()) if big.any() else 0.0)
            if tgs:
                res[k]["cover"] += int(np.mean(tgs) <= c["U"])
                res[k]["cover_group"] += int(np.mean(tggs) <= c["U_group_max"])
        if (rep + 1) % 25 == 0:
            print(f"  resampling {rep + 1}/{a.replicates}", flush=True)
    summ = {k: {"deletion_rate": v["deletion"] / a.replicates,
                "worst_wiped_mean": float(np.mean(v["worst"])),
                "worst_wiped_p90": float(np.percentile(v["worst"], 90)),
                "catch_mean": float(np.mean(v["catch"])),
                "coverage": v["cover"] / a.replicates,
                "coverage_group": v["cover_group"] / a.replicates} for k, v in res.items()}
    for k, v in summ.items():
        print(f"  RESAMPLE {k:15s} deletion rate={v['deletion_rate']:.3f} worst-wiped mean={100*v['worst_wiped_mean']:.1f}% "
              f"p90={100*v['worst_wiped_p90']:.1f}% catch={100*v['catch_mean']:.1f}% "
              f"coverage={v['coverage']:.3f} group-coverage={v['coverage_group']:.3f}")
    json.dump({"task": t, "groups": A.gnames, "B_group_sizes": B.n_g.tolist(), "rows": rows,
               "resampling": summ, "replicates": a.replicates}, open(a.out, "w"), indent=1, default=float)
    return 0


if __name__ == "__main__":
    sys.exit(main())
