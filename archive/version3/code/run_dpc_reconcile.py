#!/usr/bin/env python3
"""
run_dpc_reconcile.py -- B5: compute DPC's selection accuracy against the same
greedy baseline used elsewhere in tab:main (seed=1, GPT-4o, 200 instances),
with a paired bootstrap CI matching the paper's own statistical methodology.
"""
from __future__ import annotations
import sys, json, concurrent.futures
sys.path.insert(0, ".")
sys.path.insert(0, "../../version2")
from soundver.generate import _load_sql_items, _sql_prompt, _complete
from soundver.checks import sql_extract
from spider_task import test_suite_accuracy
from soundver.rates import paired_bootstrap
import numpy as np

items = _load_sql_items(200, seed=1)
dpc_sel = json.load(open("dpc_repo/artifacts/selected/dpc_gpt4o_full_results.json"))


def process_one(i, it):
    prompt = _sql_prompt(it["question"], it["schema"])
    text, _, _, _ = _complete("openai/gpt-4o-2024-11-20", prompt, temperature=0.0, max_tokens=256)
    sql = sql_extract(text)
    try:
        base_ok = test_suite_accuracy(sql, it["gold_sql"], it["db_path"])
    except ValueError:
        base_ok = False

    dsql = dpc_sel.get(str(i))
    try:
        dpc_ok = test_suite_accuracy(dsql, it["gold_sql"], it["db_path"]) if dsql else False
    except ValueError:
        dpc_ok = False
    return i, base_ok, dpc_ok


base_correct = [None] * len(items)
dpc_correct = [None] * len(items)
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
    futs = [pool.submit(process_one, i, it) for i, it in enumerate(items)]
    done = 0
    for fut in concurrent.futures.as_completed(futs):
        i, b, d = fut.result()
        base_correct[i] = b
        dpc_correct[i] = d
        done += 1
        if done % 25 == 0:
            print(f"  {done}/{len(items)}", flush=True)

base_arr = np.array(base_correct, dtype=float)
dpc_arr = np.array(dpc_correct, dtype=float)
print("base greedy (fresh):", base_arr.mean() * 100, "%")
print("dpc selection:", dpc_arr.mean() * 100, "%")
m, lo, hi = paired_bootstrap(dpc_arr, base_arr)
print(f"diff CI: {m:+.2f} [{lo:+.2f},{hi:+.2f}]")
print("floor holds:", bool(dpc_arr.mean() >= base_arr.mean() - 1e-9))

json.dump({"base_pct": float(base_arr.mean() * 100), "dpc_pct": float(dpc_arr.mean() * 100),
          "diff_ci": [m, lo, hi], "floor_holds": bool(dpc_arr.mean() >= base_arr.mean() - 1e-9),
          "n": 200}, open("out/dpc_baseline.json", "w"), indent=2)
print("wrote out/dpc_baseline.json")
