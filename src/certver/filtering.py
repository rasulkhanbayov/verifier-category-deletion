"""
certver.filtering -- the verifier as a training-data filter.

  python -m certver.filtering --task sql --curve out/curve_sql_inst.json \
      --candidates "out/candidates/sql_*.jsonl" --pool data/test/pool_sql_test_seed0.jsonl \
      --selections handwritten "itau=0.02" f1_baseline

Keep every pooled model output the verifier accepts, as a distillation /
synthetic-data filter would. Report, per selection:
  precision       fraction of kept outputs that are correct
  recall          fraction of correct outputs kept
  coverage        fraction of instances with >=1 correct output in the pool
                  that keep >=1 correct output after filtering
  lost            instances whose every correct output was filtered out
and the same coverage per SUBGROUP, defined from the gold answer only (never
from the checks), so a check that silently removes one kind of question shows
up as a subgroup with low coverage even when the averages look fine.
"""
from __future__ import annotations
import argparse, json, re, sys
import numpy as np

from .admit import load_examples
from .curve import verdict_matrix, load_candidates, conj


def subgroups(task: str, item: dict) -> list:
    if task == "sql":
        g = item["gold_sql"].lower()
        tags = []
        if re.search(r"\bhaving\b", g): tags.append("having")
        if re.search(r"\border\s+by\b", g): tags.append("order_by")
        if re.search(r"\bgroup\s+by\b", g): tags.append("group_by")
        if g.count("select") > 1: tags.append("nested_or_setop")
        if re.search(r"\bjoin\b", g): tags.append("join")
        if re.search(r"\blike\b", g): tags.append("like")
        if re.search(r"\b(count|avg|sum|min|max)\s*\(", g): tags.append("aggregate")
        if not re.search(r"\b(join|group|order|having)\b", g) and g.count("select") == 1:
            tags.append("simple")
        return tags or ["other"]
    if task == "ie":
        ents = [e for v in item["gold"].values() for e in v]
        tags = []
        if not ents: tags.append("no_entities")
        if any(re.search(r"\d", e) for e in ents): tags.append("entity_with_digit")
        if any(any(t[:1].islower() for t in e.split()) for e in ents): tags.append("entity_with_lowercase_token")
        if any(len(e.split()) >= 3 for e in ents): tags.append("entity_3plus_tokens")
        if item["gold"].get("else"): tags.append("has_else_type")
        if len(ents) >= 4: tags.append("4plus_entities")
        if ents and not tags: tags.append("plain")
        return tags or ["plain"]
    if task == "fewnerd":
        ents = {t: v for t, v in item["gold"].items() if v}
        tags = [f"has_{t}" for t in ents] or ["no_entities"]
        if sum(len(v) for v in ents.values()) >= 4:
            tags.append("4plus_entities")
        return tags
    if task == "fc":
        args = item["gold_call"]["arguments"]
        n = len(args)
        tags = ["0_args" if n == 0 else "1_arg" if n == 1 else "2_args" if n == 2 else "3plus_args"]
        if any(isinstance(v, bool) for v in args.values()): tags.append("bool_arg")
        if any(isinstance(v, (int, float)) and not isinstance(v, bool) for v in args.values()): tags.append("numeric_arg")
        if any(isinstance(v, (list, dict)) for v in args.values()): tags.append("structured_arg")
        props = {}
        for f in item["functions"]:
            if f.get("name") == item["gold_call"]["name"]:
                props = (f.get("parameters") or {}).get("properties") or {}
        if any("enum" in (p or {}) for p in props.values()): tags.append("enum_param")
        if len(item["functions"]) > 1: tags.append("multi_function_choice")
        return tags
    if task == "math":
        steps = item["gold_solution"].count("<<")
        tags = ["1-2_steps" if steps <= 2 else "3-4_steps" if steps <= 4 else "5plus_steps"]
        try:
            v = float(item["gold_answer"])
            if v != int(v): tags.append("non_integer_answer")
            if abs(v) >= 1000: tags.append("answer_ge_1000")
        except ValueError:
            pass
        return tags
    segs = item["gold_segments"]
    tags = [f"{min(len(segs), 4)}{'+' if len(segs) >= 4 else ''}_morphemes"]
    if "".join(segs) != item["surface"]: tags.append("canonical_differs_from_surface")
    return tags


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", required=True); ap.add_argument("--curve", required=True)
    ap.add_argument("--candidates", nargs="+", required=True); ap.add_argument("--pool", required=True)
    ap.add_argument("--selections", nargs="+", required=True)
    ap.add_argument("--min-group", type=int, default=15)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)

    sel = {r["selection"]: r["checks"] for r in json.load(open(a.curve))["results"]}
    items = {json.loads(l)["instance_id"]: json.loads(l)
             for l in open(a.pool.replace(".jsonl", ".items.jsonl")) if l.strip()}
    ex = [e for e in load_examples(a.task, a.pool) if e["model"] != "gold"]
    ids = {c for s in a.selections for c in sel[s]}
    V = verdict_matrix(a.task, [c for c in load_candidates(a.task, a.candidates, ex) if c["id"] in ids], ex)
    cor = np.array([e["correct"] for e in ex])
    groups = {iid: subgroups(a.task, items[iid]) for iid in items}

    out = {}
    for s in a.selections:
        acc = conj(V, sel[s], len(ex))
        kept = acc
        prec = (kept & cor).sum() / max(1, kept.sum())
        rec = (kept & cor).sum() / max(1, cor.sum())
        has, keep = {}, {}
        for e, k, c in zip(ex, kept, cor):
            key = (e["model"], e["instance_id"])
            if c:
                has[key] = True
                keep[key] = keep.get(key, False) or bool(k)
        n_has = len(has); lost = [k for k in has if not keep[k]]
        sub = {}
        for key in has:
            for g in groups[key[1]]:
                t = sub.setdefault(g, [0, 0]); t[0] += 1; t[1] += int(not keep[key])
        sub = {g: {"n": n, "lost": l, "coverage": 1 - l / n} for g, (n, l) in sub.items()}
        out[s] = {"precision": float(prec), "recall": float(rec), "kept": int(kept.sum()),
                  "coverage": 1 - len(lost) / max(1, n_has), "lost": len(lost), "n": n_has,
                  "subgroups": sub}
        worst = sorted((v["coverage"], g) for g, v in sub.items() if v["n"] >= a.min_group)[:3]
        print(f"{s:14s} precision={prec:.3f} recall={rec:.3f} coverage={out[s]['coverage']:.4f} "
              f"lost={len(lost)}/{n_has}  worst subgroups: "
              + ", ".join(f"{g}={c:.3f} (lost {sub[g]['lost']}/{sub[g]['n']})" for c, g in worst))
    if a.out:
        json.dump({"task": a.task, "pool": a.pool, "results": out}, open(a.out, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
