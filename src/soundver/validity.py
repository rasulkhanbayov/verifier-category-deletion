"""
soundver.validity -- the two designed-but-unrun experiments (B8).

V1 label audit. delta and epsilon are conditional on a correctness label, and
every label is automatic. A correct output mislabelled incorrect joins the
incorrect pool, passes the structural checks because it is well formed, and is
counted as a false acceptance. Label false negatives therefore INFLATE epsilon
and UNDERSTATE the ceiling: the bias runs toward the paper's conclusion, which
is why it has to be measured rather than assumed.

V2 prompt sweep. epsilon is a property of an error distribution the prompt
shapes, so a bound computed under one prompt is a bound under one prompt.

  python -m soundver.validity sample  --records data/records.jsonl --out out/
  python -m soundver.validity score   --annotations out/annotations.jsonl \
                                      --records data/records.jsonl
  python -m soundver.validity prompts --records data/records.jsonl
"""
from __future__ import annotations
import argparse, csv, json, os, sys
import numpy as np
from collections import defaultdict
from .records import load, CHECKS
from .rates import estimate

ALPHA_FLOOR = 0.67


# ------------------------------------------------------------------- V1 sample
def sample_eps_events(recs, n_per_task=150, seed=0):
    """
    Draw the epsilon events: outputs the sound stack ACCEPTED and the automatic
    label called INCORRECT. Stratified by model so no cell dominates.
    """
    rng = np.random.default_rng(seed)
    pools = defaultdict(list)
    for r in recs:
        if r.correct:
            continue
        if r.accepted_by(CHECKS[r.task]):
            pools[(r.task, r.model)].append(r)

    out = []
    by_task = defaultdict(list)
    for (task, model), rs in pools.items():
        by_task[task].append((model, rs))
    for task, entries in by_task.items():
        per = max(1, n_per_task // max(len(entries), 1))
        for model, rs in entries:
            take = min(per, len(rs))
            for r in rng.choice(len(rs), size=take, replace=False):
                x = rs[int(r)]
                out.append(dict(task=task, model=model,
                                instance_id=x.instance_id, cand_idx=x.cand_idx,
                                automatic_label="incorrect",
                                human_label="", annotator=""))
    return out


def write_annotation_sheets(rows, out_dir, annotators=2):
    """
    One blind sheet per annotator. The automatic label is NOT written into the
    sheet: an annotator who can see it is not blind, and the whole point is to
    catch cases where the automatic label is wrong.
    """
    os.makedirs(out_dir, exist_ok=True)
    rng = np.random.default_rng(0)
    for a in range(annotators):
        order = rng.permutation(len(rows))
        path = os.path.join(out_dir, f"annotation_sheet_{a+1}.csv")
        with open(path, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["row_id", "task", "instance_id", "cand_idx",
                        "human_label(correct|incorrect|unsure)", "notes"])
            for i in order:
                r = rows[i]
                w.writerow([i, r["task"], r["instance_id"], r["cand_idx"], "", ""])
        print(f"  wrote {path}  ({len(rows)} items, shuffled, blind)")
    with open(os.path.join(out_dir, "annotation_key.jsonl"), "w") as fh:
        for i, r in enumerate(rows):
            fh.write(json.dumps({"row_id": i, **r}) + "\n")
    print(f"  wrote {out_dir}/annotation_key.jsonl  (do NOT show to annotators)")


# -------------------------------------------------------------------- V1 score
def krippendorff_alpha_nominal(m):
    """
    Nominal-scale Krippendorff's alpha. m is items x coders, None for missing.
    Implemented directly so the result does not depend on an unpinned package.
    """
    vals = sorted({v for row in m for v in row if v is not None})
    idx = {v: i for i, v in enumerate(vals)}
    k = len(vals)
    if k < 2:
        return 1.0
    coincidence = np.zeros((k, k))
    for row in m:
        obs = [v for v in row if v is not None]
        mu = len(obs)
        if mu < 2:
            continue
        for i in range(mu):
            for j in range(mu):
                if i != j:
                    coincidence[idx[obs[i]], idx[obs[j]]] += 1.0 / (mu - 1)
    n = coincidence.sum()
    if n == 0:
        return float("nan")
    nc = coincidence.sum(axis=1)
    Do = sum(coincidence[i, j] for i in range(k) for j in range(k) if i != j) / n
    De = sum(nc[i] * nc[j] for i in range(k) for j in range(k) if i != j) / (n * (n - 1))
    return 1.0 - Do / De if De else float("nan")


def _wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def _corrected_ceiling(R, lam):
    eps_c = R.eps * (1 - lam)
    q_c = R.p + (1 - R.p) * eps_c
    return 0.0 if q_c <= 0 else 100 * (1 - R.p0) * (1 - eps_c) * R.p / q_c


# Cells certified under 5-seed replication AND covered by the audit sample
# (drawn from the original four models; Qwen2.5-72B's IE cell is not in it).
REPLICATED_SOUND = {("ie", "openai/gpt-4o-2024-11-20"),
                    ("ie", "openai/gpt-4o-mini-2024-07-18")}


def score_audit(annotations_path, records_path, key_path=None,
                seed_records_fmt="data/records_{task}_seed{seed}.jsonl",
                seeds=(0, 1, 2, 3, 4)):
    """
    lambda = share of sampled epsilon events that BOTH annotators judge
    correct (no third adjudicator was used, so a split counts as not wrong).
    Estimated per task, as the design specifies ("on this stratum"); the
    cross-task pooled value is reported only as a robustness row, since SQL
    and morphology label errors say nothing about IE's label function.
    """
    key_path = key_path or os.path.join(os.path.dirname(annotations_path),
                                        "annotation_key.jsonl")
    key = {}
    with open(key_path) as fh:
        for line in fh:
            if line.strip():
                d = json.loads(line)
                key[d["row_id"]] = (d["task"], d["model"])

    ann = defaultdict(dict)
    with open(annotations_path) as fh:
        for line in fh:
            if not line.strip():
                continue
            d = json.loads(line)
            ann[d["row_id"]][d["annotator"]] = d["human_label"]
    coders = sorted({c for v in ann.values() for c in v})

    def stratum(ids):
        ids = list(ids)
        a = krippendorff_alpha_nominal([[ann[i].get(c) for c in coders] for i in ids])
        k = sum(1 for i in ids if all(v == "correct" for v in ann[i].values()))
        lo, hi = _wilson(k, len(ids))
        return dict(n=len(ids), alpha=a, k=k, lam=k / max(len(ids), 1), lo=lo, hi=hi)

    allst = stratum(ann)
    print(f"  Krippendorff's alpha = {allst['alpha']:.3f}  over {allst['n']} items, "
          f"{len(coders)} coders")
    if allst["alpha"] < ALPHA_FLOOR:
        print(f"  alpha < {ALPHA_FLOOR}: THE EXERCISE IS VOID. Do not report a")
        print("  corrected epsilon from it. Revise the guidelines and re-run.")
        return None
    agree = sum(1 for v in ann.values() if len(set(v.values())) == 1)
    print(f"  raw agreement {agree}/{len(ann)}")

    print(f"\n  {'stratum':34s} {'n':>4} {'alpha':>6} {'k':>4} {'lambda':>7}  95% Wilson")
    print("  " + "-" * 72)
    print(f"  {'pooled (all tasks)':34s} {allst['n']:4d} {allst['alpha']:6.3f} "
          f"{allst['k']:4d} {allst['lam']:7.3f}  [{allst['lo']:.3f},{allst['hi']:.3f}]")
    task_st, cell_st = {}, {}
    for t in sorted({key[i][0] for i in ann}):
        st = stratum(i for i in ann if key[i][0] == t)
        task_st[t] = st
        flag = "  (below floor on this stratum alone)" if st["alpha"] < ALPHA_FLOOR else ""
        print(f"  {'task=' + t:34s} {st['n']:4d} {st['alpha']:6.3f} {st['k']:4d} "
              f"{st['lam']:7.3f}  [{st['lo']:.3f},{st['hi']:.3f}]{flag}")
    for (t, m) in sorted({key[i] for i in ann}):
        st = stratum(i for i in ann if key[i] == (t, m))
        cell_st[(t, m)] = st
        print(f"  {(t + '/' + m.split('/')[-1])[:34]:34s} {st['n']:4d} {st['alpha']:6.3f} "
              f"{st['k']:4d} {st['lam']:7.3f}  [{st['lo']:.3f},{st['hi']:.3f}]")

    recs = load(records_path)
    g = defaultdict(list)
    for r in recs:
        g[(r.task, r.model)].append(r)
    print(f"\n  Seed-0 ceilings (pts), replicated-sound cells covered by the sample")
    print(f"  {'cell':30s} {'base':>6} {'task-lam [CI]':>22} {'pooled':>7} {'per-cell [CI]':>22}")
    for (task, model) in sorted(REPLICATED_SOUND):
        R = estimate(g[(task, model)])
        ts, cs = task_st[task], cell_st[(task, model)]
        print(f"  {(task + '/' + model.split('/')[-1])[:30]:30s} {R.ceiling_pts():6.2f} "
              f"{_corrected_ceiling(R, ts['lam']):6.2f} [{_corrected_ceiling(R, ts['lo']):5.2f},"
              f"{_corrected_ceiling(R, ts['hi']):5.2f}] {_corrected_ceiling(R, allst['lam']):7.2f} "
              f"{_corrected_ceiling(R, cs['lam']):6.2f} [{_corrected_ceiling(R, cs['lo']):5.2f},"
              f"{_corrected_ceiling(R, cs['hi']):5.2f}]")
        print(f"  {'':30s} eps {R.eps:.3f} -> task-lam {R.eps * (1 - ts['lam']):.3f} "
              f"[{R.eps * (1 - ts['hi']):.3f},{R.eps * (1 - ts['lo']):.3f}]")

    print(f"\n  5-seed mean ceilings (pts): lambda applied to each seed's eps, then averaged")
    print(f"  {'cell':30s} {'base mean+-SD':>14} {'task-lam mean+-SD [CI of mean]':>34} "
          f"{'pooled':>7} {'per-cell':>9}")
    for (task, model) in sorted(REPLICATED_SOUND):
        per_seed = []
        for s in seeds:
            rs = [r for r in load(seed_records_fmt.format(task=task, seed=s))
                  if r.model == model]
            per_seed.append(estimate(rs))
        if not all(R.sound for R in per_seed):
            print(f"  {task}/{model}: not sound at every seed -- skipped")
            continue
        ts, cs = task_st[task], cell_st[(task, model)]
        def ms(lam):
            v = np.array([_corrected_ceiling(R, lam) for R in per_seed])
            return v.mean(), v.std(ddof=1)
        b, bs = np.mean([R.ceiling_pts() for R in per_seed]), np.std([R.ceiling_pts() for R in per_seed], ddof=1)
        t, tsd = ms(ts["lam"])
        print(f"  {(task + '/' + model.split('/')[-1])[:30]:30s} {b:6.2f}+-{bs:4.2f}   "
              f"{t:6.2f}+-{tsd:4.2f} [{ms(ts['lo'])[0]:5.2f},{ms(ts['hi'])[0]:5.2f}]          "
              f"{ms(allst['lam'])[0]:7.2f} {ms(cs['lam'])[0]:9.2f}")
    return dict(pooled=allst, task=task_st, cell=cell_st)


# ------------------------------------------------------------------------- V2
def prompt_sweep(records_path):
    recs = load(records_path)
    variants = sorted({r.prompt_id for r in recs})
    if len(variants) < 2:
        print(f"  only prompt variant(s) {variants} present. B8-V2 STAYS OPEN.")
        print("  Generate under all five variants in config.yaml and re-run.")
        return None
    g = defaultdict(list)
    for r in recs:
        g[(r.task, r.model)].append(r)
    print(f"  {'task':6s} {'model':22s} " +
          " ".join(f"{v[:9]:>9}" for v in variants) + f" {'max ceil':>9}")
    worst = {}
    for (task, model), rs in sorted(g.items()):
        cs = []
        for v in variants:
            try:
                R = estimate(rs, prompt_id=v)
                cs.append(R.ceiling_pts())
            except ValueError:
                cs.append(float("nan"))
        mx = np.nanmax(cs)
        worst[(task, model)] = mx
        print(f"  {task:6s} {model[:22]:22s} " +
              " ".join(f"{c:9.2f}" for c in cs) + f" {mx:9.2f}")
    print()
    print("  PRE-REGISTERED READING: the headline survives if the MAXIMUM")
    print("  ceiling across prompts stays under one point for both OpenAI models.")
    bad = [k for k, v in worst.items() if "gpt-4o" in k[1] and v >= 1.0]
    print(f"  -> {'SURVIVES' if not bad else f'FAILS for {bad}'}")
    return worst


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample");  s.add_argument("--records", required=True)
    s.add_argument("--out", default="out"); s.add_argument("--n", type=int, default=150)
    c = sub.add_parser("score");   c.add_argument("--annotations", required=True)
    c.add_argument("--records", required=True)
    p = sub.add_parser("prompts"); p.add_argument("--records", required=True)
    a = ap.parse_args(argv)

    if a.cmd == "sample":
        rows = sample_eps_events(load(a.records), a.n)
        print(f"  sampled {len(rows)} epsilon events")
        write_annotation_sheets(rows, a.out)
    elif a.cmd == "score":
        score_audit(a.annotations, a.records)
    else:
        prompt_sweep(a.records)
    return 0


if __name__ == "__main__":
    sys.exit(main())
