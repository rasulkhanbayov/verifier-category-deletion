#!/usr/bin/env python3
"""
b17_checker_comparison.py -- B17: inter-implementer agreement.

Compares TWO independently-written implementations of the SQL sound
stack's schema-validity check on the SAME generated candidates:
  - soundver.checks.sql_schema_valid (this paper's own, sqlglot-based,
    rewritten and stress-tested this session across five real bugs)
  - version2's spider_task.check_schema_valid (a genuinely separate
    codebase, written independently, predates this session's sqlglot
    rewrite entirely)

Reports the delta each implementation measures on the SAME candidate
pool and the disagreement rate between them -- this IS the "second
independent implementation" comparison the paper's own B17 finding asks
for, run on a smaller sample than the main tables (proportionate to
"the cheapest robustness result available", not a second full 4-model
x 200-instance collection).

  python3 b17_checker_comparison.py --instances 50
"""
from __future__ import annotations
import argparse, os, sys, concurrent.futures

sys.path.insert(0, os.path.dirname(__file__))
from soundver.generate import _load_sql_items, _sql_prompt, _complete
from soundver.checks import sql_extract, sql_parses, sql_schema_valid, sql_executes

DATA_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, os.path.normpath(DATA_ROOT) + "/version2")
import spider_task as st_v2  # the independent second implementation
from spider_task import test_suite_accuracy


def score_one(model, item):
    prompt = _sql_prompt(item["question"], item["schema"])
    import sqlite3
    conn = sqlite3.connect(item["db_path"], timeout=5.0)
    conn.text_factory = lambda b: b.decode("utf-8", errors="replace")
    try:
        base_text, _, _, _ = _complete(model, prompt, temperature=0.0, max_tokens=256)
        cand_texts = [base_text]
        for _ in range(4):
            t, _, _, _ = _complete(model, prompt, temperature=0.7, max_tokens=256)
            cand_texts.append(t)

        rows = []
        for raw in cand_texts:
            q_v3 = sql_extract(raw)
            v3_parses = sql_parses(q_v3)
            v3_schema = v3_parses and sql_schema_valid(q_v3, item["schema"])
            v3_exec = v3_schema and sql_executes(q_v3, conn)
            v3_stack = bool(v3_parses and v3_schema and v3_exec)

            q_v2 = st_v2._extract_sql(raw)
            v2_parses = st_v2.check_parses(q_v2)
            v2_schema = v2_parses and st_v2.check_schema_valid(q_v2, item["schema"])
            v2_exec = v2_schema and st_v2.check_executes(q_v2, item["db_path"])
            v2_stack = bool(v2_parses and v2_schema and v2_exec)

            try:
                correct = test_suite_accuracy(q_v3, item["gold_sql"], item["db_path"])
            except ValueError:
                correct = False

            rows.append(dict(correct=correct, v3_stack=v3_stack, v2_stack=v2_stack))
        return rows
    except Exception as e:
        return [dict(error=str(e)[:200])]
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="openai/gpt-4o-2024-11-20")
    ap.add_argument("--instances", type=int, default=50)
    ap.add_argument("--seed", type=int, default=2)
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()

    items = _load_sql_items(a.instances, a.seed)
    print(f"{len(items)} instances, model={a.model}, 5 candidates each "
          f"(1 greedy + 4 sampled)", flush=True)

    all_rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
        futs = [pool.submit(score_one, a.model, it) for it in items]
        for i, fut in enumerate(concurrent.futures.as_completed(futs)):
            all_rows.extend(fut.result())
            if (i + 1) % 10 == 0:
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
    print(f"delta (soundver.checks, this paper's own):      {v3_delta:.4f}")
    print(f"delta (spider_task.py, independent 2nd impl.):  {v2_delta:.4f}")
    print(f"disagreement rate (any candidate, not just correct ones): "
          f"{disagree}/{len(ok)} = {disagree/len(ok):.4f}" if ok else "n/a")


if __name__ == "__main__":
    main()
