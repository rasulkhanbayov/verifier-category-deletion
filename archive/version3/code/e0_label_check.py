#!/usr/bin/env python3
"""
e0_label_check.py -- E0: does the correctness label matter? (B13)

Def. admissible (Def. 2 in the paper) requires a correctness label that does
not presuppose the check being audited. For SQL, execution match DOES
presuppose the "executes" check (and, on the ORIGINAL buggy schema
validator below, the "parses"/"schema_valid" checks too, since a query
that fails those also fails to execute) -- so under execution match,
delta should measure EXACTLY 0.000 by construction, on any checker,
buggy or not. Test-suite accuracy does not presuppose any check, which
is exactly why it was able to expose this session's four real SQL
checker defects (see soundver/checks.py's docstrings and
progress_notes/session_status.md) where execution match could not have.

E0 tests this directly: run BOTH labels against the ORIGINAL, most
naively buggy schema validator this session encountered at its very
start -- i.e. deliberately with NONE of the four fixes applied (not even
the alias fix), reconstructed here rather than reverting the live,
now-correct soundver/checks.py. If Def. admissible is right, delta under
execution match must be exactly 0.000 regardless of how buggy
sql_schema_valid is; delta under test-suite accuracy is free to be
nonzero, and on this exact buggy validator it reproduces the alias-
related false rejections this session already found and fixed.

  python3 e0_label_check.py --instances 50
"""
from __future__ import annotations
import argparse, os, sys, concurrent.futures

sys.path.insert(0, os.path.dirname(__file__))
from soundver.generate import _load_sql_items, _sql_prompt, _complete
from soundver.checks import sql_extract, sql_parses, sql_executes, _sql_identifiers

DATA_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, os.path.normpath(DATA_ROOT) + "/version2")
from spider_task import test_suite_accuracy  # reused utility, not its data


# ---------------------------------------------------------------------
# THE ORIGINAL, PRE-FIX SCHEMA VALIDATOR. Deliberately reconstructed here,
# not imported, so this file is a self-contained, inspectable record of
# exactly what E0 ran against -- no table alias, no SELECT-list alias, no
# function-name/keyword handling, no sqlglot. This IS the buggy function
# that produced the false rejections this session found in checks.py.
# ---------------------------------------------------------------------
def buggy_sql_schema_valid(q: str, schema: dict) -> bool:
    known = {t.lower() for t in schema} | {
        c.lower() for cols in schema.values() for c in cols}
    known |= {"*"}
    return _sql_identifiers(q) <= known


def score_one(model, item):
    prompt = _sql_prompt(item["question"], item["schema"])
    import sqlite3
    conn = sqlite3.connect(item["db_path"], timeout=5.0)
    conn.text_factory = lambda b: b.decode("utf-8", errors="replace")
    try:
        text, _, _, _ = _complete(model, prompt, temperature=0.0, max_tokens=256)
        q = sql_extract(text)
        p = sql_parses(q)
        sv = p and buggy_sql_schema_valid(q, item["schema"])
        ex = sv and sql_executes(q, conn)

        # execution-match label: correct iff it executes without error,
        # regardless of whether the RESULT matches gold
        exec_match_correct = bool(ex)

        # admissible label: test-suite accuracy (Def. admissible)
        try:
            tsa_correct = test_suite_accuracy(q, item["gold_sql"], item["db_path"])
        except ValueError:
            tsa_correct = False

        return dict(instance_id=item["instance_id"], parses=p,
                    schema_valid=bool(sv), executes=bool(ex),
                    exec_match_correct=exec_match_correct,
                    tsa_correct=tsa_correct)
    except Exception as e:
        return dict(instance_id=item["instance_id"], error=str(e)[:200])
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="openai/gpt-4o-mini-2024-07-18")
    ap.add_argument("--instances", type=int, default=200)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()

    items = _load_sql_items(a.instances, a.seed)
    print(f"E0: {len(items)} instances, model={a.model}, "
          f"validator=ORIGINAL PRE-FIX (no alias/function/keyword handling)")

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
        futs = [pool.submit(score_one, a.model, it) for it in items]
        for i, fut in enumerate(concurrent.futures.as_completed(futs)):
            results.append(fut.result())
            if (i + 1) % 25 == 0:
                print(f"  {i + 1}/{len(items)}", flush=True)

    errors = [r for r in results if "error" in r]
    ok = [r for r in results if "error" not in r]
    print(f"\n{len(errors)} errored, {len(ok)} scored")

    def stack_accepts(r):
        return r["parses"] and r["schema_valid"] and r["executes"]

    # delta under EXECUTION MATCH: P[stack rejects | exec_match_correct]
    exec_correct = [r for r in ok if r["exec_match_correct"]]
    exec_delta = (sum(1 for r in exec_correct if not stack_accepts(r))
                 / len(exec_correct)) if exec_correct else float("nan")

    # delta under TEST-SUITE ACCURACY (the admissible label)
    tsa_correct = [r for r in ok if r["tsa_correct"]]
    tsa_delta = (sum(1 for r in tsa_correct if not stack_accepts(r))
                / len(tsa_correct)) if tsa_correct else float("nan")

    print(f"\ndelta under execution match     (n={len(exec_correct)}): {exec_delta:.4f}")
    print(f"delta under test-suite accuracy (n={len(tsa_correct)}): {tsa_delta:.4f}")
    print()
    if exec_delta == 0.0:
        print("CONFIRMS Def. admissible's prediction: execution match, which "
              "presupposes the stack, certifies delta=0 by construction --")
        print("even against this deliberately buggy validator.")
    else:
        print(f"REFUTES Def. admissible's prediction: delta={exec_delta:.4f} "
              f"under execution match is nonzero. This would mean the "
              f"definition itself is wrong and needs revision.")
    if tsa_delta > 0:
        print(f"\ntest-suite accuracy DOES expose the buggy validator's false "
              f"rejections (delta={tsa_delta:.4f} > 0), which execution "
              f"match structurally cannot -- this is the sharpness the "
              f"paper's Def. admissible argues for.")


if __name__ == "__main__":
    main()
