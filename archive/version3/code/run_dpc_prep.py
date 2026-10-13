#!/usr/bin/env python3
"""
run_dpc_prep.py -- B5: prepare inputs for the official DPC repo
(github.com/HKUSTDial/DPC), reusing the SAME 200-instance, seed=1 SQL sample
tab:main's baseline sweep (run_sql_baselines.py) already uses, for a genuine
apples-to-apples DPC row in that table.

Writes:
  dpc_repo/data/spider_sample/dev.json         (200-item sub-dev.json, index
                                                 order = candidate JSON keys,
                                                 since Spider items have no
                                                 native question_id)
  dpc_repo/data/spider_sample/tables.json       (copied verbatim)
  dpc_repo/artifacts/candidates/gpt4o_sample.json  (8 sampled candidates per
                                                     instance, GPT-4o, same
                                                     greedy+temp=0.7 protocol
                                                     as every other baseline)

Usage:
    python3 run_dpc_prep.py
"""
from __future__ import annotations
import json, os, sys, concurrent.futures

sys.path.insert(0, os.path.dirname(__file__))
from soundver.generate import _load_sql_items, _sql_prompt, _complete, SPIDER_TABLES

MODEL = "openai/gpt-4o-2024-11-20"
N_INSTANCES = 200
N_CANDIDATES = 8
SEED = 1  # matches run_sql_baselines.py's own sample

OUT_DATA_DIR = "dpc_repo/data/spider_sample"
OUT_CAND_DIR = "dpc_repo/artifacts/candidates"


def gen_candidates(item):
    prompt = _sql_prompt(item["question"], item["schema"])
    texts = []
    base, _, _, _ = _complete(MODEL, prompt, temperature=0.0, max_tokens=256)
    texts.append(base)
    for _ in range(N_CANDIDATES - 1):
        t, _, _, _ = _complete(MODEL, prompt, temperature=0.7, max_tokens=256)
        texts.append(t)
    return texts


def main():
    items = _load_sql_items(N_INSTANCES, seed=SEED)
    print(f"{len(items)} instances loaded (seed={SEED}, matches tab:main's sample)")

    os.makedirs(OUT_DATA_DIR, exist_ok=True)
    os.makedirs(OUT_CAND_DIR, exist_ok=True)

    # sub-dev.json: index order IS the question_id DPC's Spider loader assigns
    dev_rows = [{"question": it["question"], "db_id": it["db_id"],
                "query": it["gold_sql"]} for it in items]
    with open(os.path.join(OUT_DATA_DIR, "dev.json"), "w") as f:
        json.dump(dev_rows, f, indent=2)
    print(f"wrote {OUT_DATA_DIR}/dev.json ({len(dev_rows)} rows)")

    with open(SPIDER_TABLES) as f:
        tables = json.load(f)
    with open(os.path.join(OUT_DATA_DIR, "tables.json"), "w") as f:
        json.dump(tables, f)
    print(f"wrote {OUT_DATA_DIR}/tables.json")

    candidates = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futs = {pool.submit(gen_candidates, it): i for i, it in enumerate(items)}
        done = 0
        for fut in concurrent.futures.as_completed(futs):
            i = futs[fut]
            candidates[str(i)] = fut.result()
            done += 1
            if done % 25 == 0:
                print(f"  {done}/{len(items)} instances", flush=True)

    out_path = os.path.join(OUT_CAND_DIR, "gpt4o_sample.json")
    with open(out_path, "w") as f:
        json.dump(candidates, f, indent=2)
    print(f"wrote {out_path} ({len(candidates)} question_ids, "
         f"{N_CANDIDATES} candidates each)")

    # map DPC's dev.json db_root_path expectation: DPC wants
    # db_root_path/db_id/db_id.sqlite, which is exactly Spider's own layout --
    # just point it at the existing spider_data database directory directly,
    # no copy needed.
    print("\nNext: point --db_root_path at the existing spider_data/spider_data/database dir.")


if __name__ == "__main__":
    main()
