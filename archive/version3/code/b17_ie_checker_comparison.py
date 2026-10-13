#!/usr/bin/env python3
"""
b17_ie_checker_comparison.py -- B17 (P11): inter-implementer agreement
for IE's no_overlap check, the same pattern already used for SQL
(b17_checker_comparison.py) but for the check that actually had a real,
found-and-fixed bug this session (the text.find() first-occurrence bug
in ie_no_overlap).

Compares TWO independently-written implementations on the SAME
generated candidates:
  - soundver.checks.ie_no_overlap (this paper's own, backtracking over
    all occurrences of each entity string, fixed this session)
  - version2's ie_task.check_no_overlap (a genuinely separate codebase,
    predates this session's fix, uses text.find() -- confirmed by
    direct inspection to have the identical first-occurrence bug)

version2's checker expects a list of {entity, entity_type} dicts;
version3's slot-filling format ({"location": [...], ...}) is converted
to that shape before scoring, so both checkers see the same extracted
spans, just in each implementation's own expected shape.

  python3 b17_ie_checker_comparison.py --instances 100
"""
from __future__ import annotations
import argparse, os, sys, concurrent.futures

sys.path.insert(0, os.path.dirname(__file__))
from soundver.generate import (_load_ie_items, _ie_prompt, _ie_extract_json, _complete,
                               IE_ENTITY_TYPES, _field_value_match)
from soundver.checks import ie_parses, ie_required_fields, ie_schema_valid, ie_no_overlap

DATA_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, os.path.normpath(DATA_ROOT) + "/version2")
import ie_task as it_v2  # the independent second implementation


def slotfill_to_entity_list(obj):
    """Convert version3's {"location": [...], "person": [...], ...} into
    version2's [{"entity": span, "entity_type": type}, ...]."""
    out = []
    if not isinstance(obj, dict):
        return out
    for t in IE_ENTITY_TYPES:
        v = obj.get(t, [])
        v = v if isinstance(v, list) else [v]
        for x in v:
            if isinstance(x, str) and x:
                out.append({"entity": x, "entity_type": t})
    return out


def score_one(model, item):
    prompt = _ie_prompt(item["text"])
    try:
        cand_texts = []
        base_text, _, _, _ = _complete(model, prompt, temperature=0.0, max_tokens=512)
        cand_texts.append(base_text)
        for _ in range(4):
            t, _, _, _ = _complete(model, prompt, temperature=0.7, max_tokens=512)
            cand_texts.append(t)

        rows = []
        for raw in cand_texts:
            cleaned = _ie_extract_json(raw)
            obj = ie_parses(cleaned)

            # v3 stack
            p = obj is not None
            rf = p and ie_required_fields(obj, IE_ENTITY_TYPES)
            sv = rf and ie_schema_valid(obj, {t: "list" for t in IE_ENTITY_TYPES})
            no = rf and ie_no_overlap(obj, item["text"])
            v3_stack = bool(p and rf and sv and no)

            # v2 stack, fed the SAME parsed object converted to its own shape
            entities = slotfill_to_entity_list(obj) if p else []
            v2_p = obj is not None
            v2_rf = it_v2.check_required_fields(entities) if entities or v2_p else False
            v2_sv = v2_rf and it_v2.check_schema_valid_ie(entities, IE_ENTITY_TYPES)
            v2_no = v2_rf and it_v2.check_no_overlap(entities, item["text"])
            v2_stack = bool(v2_p and v2_rf and v2_sv and v2_no)

            # NOTE: it_v2.label_correct(raw, ...) internally re-parses `raw`
            # expecting a JSON LIST ([{entity, entity_type}, ...]), but v3's
            # model output is always a JSON OBJECT (slot-filling format), so
            # calling it directly on `raw` would always return None -> wrong.
            # Use this paper's own canonical admissible label instead (Def.
            # 2: does not presuppose parses/schema_valid/no_overlap), the
            # same one every other IE delta in the paper is measured
            # against -- this is the correctness LABEL, independent of
            # which checker implementation's stack verdict is being
            # compared below.
            correct = _field_value_match(obj if p else None, item["gold"])

            rows.append(dict(correct=correct, v3_stack=v3_stack, v2_stack=v2_stack))
        return rows
    except Exception as e:
        return [dict(error=str(e)[:200])]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="openai/gpt-4o-2024-11-20")
    ap.add_argument("--instances", type=int, default=100)
    ap.add_argument("--seed", type=int, default=2)
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()

    items = _load_ie_items(a.instances, a.seed)
    print(f"{len(items)} instances, model={a.model}, 5 candidates each "
         f"(1 greedy + 4 sampled)", flush=True)

    all_rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
        futs = [pool.submit(score_one, a.model, it) for it in items]
        for i, fut in enumerate(concurrent.futures.as_completed(futs)):
            all_rows.extend(fut.result())
            if (i + 1) % 25 == 0:
                print(f"  {i + 1}/{len(items)}", flush=True)

    ok = [r for r in all_rows if "error" not in r]
    errors = [r for r in all_rows if "error" in r]
    print(f"{len(errors)} errored, {len(ok)} scored\n")

    correct = [r for r in ok if r["correct"]]
    v3_delta = (sum(1 for r in correct if not r["v3_stack"]) / len(correct)
               if correct else float("nan"))
    v2_delta = (sum(1 for r in correct if not r["v2_stack"]) / len(correct)
               if correct else float("nan"))
    disagree = sum(1 for r in ok if r["v3_stack"] != r["v2_stack"])

    print(f"n correct outputs tested: {len(correct)}")
    print(f"delta (soundver.checks, this paper's own, fixed):  {v3_delta:.4f}")
    print(f"delta (ie_task.py, independent 2nd impl., NOT fixed): {v2_delta:.4f}")
    print(f"disagreement rate (any candidate, not just correct ones): "
         f"{disagree}/{len(ok)} = {disagree/len(ok):.4f}" if ok else "n/a")


if __name__ == "__main__":
    main()
