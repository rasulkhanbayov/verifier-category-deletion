#!/usr/bin/env python3
"""
b8_v1_enrich_sheets.py -- fix a real gap in the B8-V1 label-audit sheets:
they showed a human annotator only the model's raw output, never the task
input (the word being segmented, the question being answered, the text
being extracted from) or the gold answer. A human cannot judge correctness
without the input -- this was missed when the sheets were first built.

No new API calls needed: LOADERS[task](200, seed) is a deterministic,
purely-local function of (task, seed), so the exact same item for a given
instance_id can be reconstructed offline and joined onto the existing
annotation_key.jsonl (which already has instance_id/task/raw_text/seed
implicitly fixed at seed=0, the default used when the sheets were built).

Usage:
    python3 b8_v1_enrich_sheets.py
"""
from __future__ import annotations
import csv, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
from soundver.generate import LOADERS

SEED = 0  # matches b8_v1_label_audit_sample.py's default
AUDIT_DIR = "out/label_audit"


def item_display(task, item):
    if task == "sql":
        return item["question"], item["gold_sql"]
    if task == "ie":
        gold_str = json.dumps(item["gold"])
        return item["text"], gold_str
    # morph
    gold_str = "+".join(item["gold_segments"])
    return item["surface"], gold_str


def main():
    items_by_task = {t: {it["instance_id"]: it for it in LOADERS[t](200, SEED)}
                     for t in ("sql", "ie", "morph")}

    key_path = os.path.join(AUDIT_DIR, "annotation_key.jsonl")
    rows = []
    with open(key_path) as f:
        for line in f:
            rows.append(json.loads(line))

    for r in rows:
        item = items_by_task[r["task"]].get(r["instance_id"])
        if item is None:
            raise SystemExit(f"instance {r['instance_id']} not found in seed={SEED} "
                             f"pool for task={r['task']} -- sheets were built with a "
                             f"different seed than assumed")
        task_input, gold = item_display(r["task"], item)
        r["task_input"] = task_input
        r["gold"] = gold

    with open(key_path, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(f"rewrote {key_path} with task_input/gold added")

    for a_idx in range(2):
        path = os.path.join(AUDIT_DIR, f"annotation_sheet_{a_idx + 1}.csv")
        with open(path, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["row_id", "task", "task_input", "candidate_output",
                       "human_label(correct|incorrect|unsure)", "notes"])
            for r in rows:
                w.writerow([r["row_id"], r["task"], r["task_input"],
                           r["raw_text"], "", ""])
        print(f"rewrote {path} ({len(rows)} items) -- input included, "
             f"gold and automatic_label withheld (blind)")

    print("\nNote: gold answers and the automatic label are kept ONLY in "
         "annotation_key.jsonl, not in the sheets -- an annotator who can "
         "see gold or the automatic label is not blind.")


if __name__ == "__main__":
    main()
