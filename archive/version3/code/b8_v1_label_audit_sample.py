#!/usr/bin/env python3
"""
b8_v1_label_audit_sample.py -- B8-V1: draw a fresh epsilon-event sample WITH
raw text, for human label validation.

validity.py's sample_eps_events() draws epsilon events (outputs the sound
stack accepted but the automatic label called incorrect) from an existing
records.jsonl -- but records.jsonl never stores raw generated text (only
booleans, by this project's Record schema), so its annotation sheets cannot
actually be read by a human annotator. Exact candidates at a fixed cand_idx
also cannot be reproduced after the fact (temperature=0.7 sampling), so the
fix is a fresh, smaller generation pass that scores AND keeps the text,
stopping once enough epsilon events are found per task.

Usage:
    python3 b8_v1_label_audit_sample.py --n-per-task 150
"""
from __future__ import annotations
import argparse, csv, json, os, sys, random, concurrent.futures

sys.path.insert(0, os.path.dirname(__file__))
from soundver.generate import (LOADERS, PROMPTS, _complete, _label_correct,
                               score_checks, CHECKS)

TASKS = ["sql", "ie", "morph"]
MODELS = ["openai/gpt-4o-2024-11-20", "openai/gpt-4o-mini-2024-07-18",
         "meta-llama/llama-3.1-8b-instruct", "meta-llama/llama-3.1-70b-instruct"]


def find_eps_events(task, model, n_target, seed, candidates, workers):
    """Generate instances for (task, model), scoring each candidate, and keep
    every genuine epsilon event (accepted by the sound stack, labelled
    incorrect) with its raw text, until n_target found or instances exhausted."""
    items = LOADERS[task](200, seed)  # same pool E1 draws from
    stack = CHECKS[task]
    found = []

    def process_one(item):
        local_item = item
        conn = None
        try:
            if task == "sql":
                import sqlite3
                conn = sqlite3.connect(item["db_path"], timeout=5.0)
                conn.text_factory = lambda b: b.decode("utf-8", errors="replace")
                local_item = {**item, "conn": conn}
            prompt = PROMPTS[task](item, "base")
            hits = []
            texts = []
            for _ in range(candidates):
                text, _, _, _ = _complete(model, prompt, temperature=0.7, max_tokens=512)
                texts.append(text)
            for idx, text in enumerate(texts):
                checks, parsed = score_checks(task, text, local_item)
                correct = _label_correct(task, local_item, text, parsed)
                accepted = all(checks[c] for c in stack)
                if accepted and not correct:
                    hits.append(dict(task=task, model=model,
                                     instance_id=item["instance_id"], cand_idx=idx,
                                     raw_text=text, automatic_label="incorrect",
                                     human_label="", annotator=""))
            return hits
        finally:
            if conn is not None:
                conn.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futs = [pool.submit(process_one, it) for it in items]
        for fut in concurrent.futures.as_completed(futs):
            found.extend(fut.result())
            if len(found) >= n_target:
                break
    return found[:n_target]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-per-task", type=int, default=150)
    ap.add_argument("--candidates", type=int, default=8)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out", default="out/label_audit")
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    all_rows = []
    for task in TASKS:
        per_model = max(1, a.n_per_task // len(MODELS))
        task_rows = []
        for model in MODELS:
            print(f"{task} / {model}: searching for {per_model} epsilon events...",
                 flush=True)
            hits = find_eps_events(task, model, per_model, a.seed, a.candidates, a.workers)
            print(f"  found {len(hits)}", flush=True)
            task_rows.extend(hits)
        all_rows.extend(task_rows)

    rng = random.Random(0)
    order = list(range(len(all_rows)))
    rng.shuffle(order)
    rows = [all_rows[i] for i in order]

    for a_idx in range(2):
        path = os.path.join(a.out, f"annotation_sheet_{a_idx+1}.csv")
        with open(path, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["row_id", "task", "instance_id", "cand_idx", "raw_text",
                       "human_label(correct|incorrect|unsure)", "notes"])
            for i, r in enumerate(rows):
                w.writerow([i, r["task"], r["instance_id"], r["cand_idx"],
                           r["raw_text"], "", ""])
        print(f"wrote {path} ({len(rows)} items, shuffled, blind, WITH raw text)")

    with open(os.path.join(a.out, "annotation_key.jsonl"), "w") as fh:
        for i, r in enumerate(rows):
            fh.write(json.dumps({"row_id": i, **r}) + "\n")
    print(f"wrote {a.out}/annotation_key.jsonl (do NOT show to annotators)")


if __name__ == "__main__":
    main()
