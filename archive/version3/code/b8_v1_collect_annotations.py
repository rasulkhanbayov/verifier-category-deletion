#!/usr/bin/env python3
"""
b8_v1_collect_annotations.py -- after both annotators have filled in the
human_label column of out/label_audit/annotation_sheet_{1,2}.csv, run this
to combine them into the annotations.jsonl format soundver.validity score
expects ({row_id, annotator, human_label} per line), then run the scoring
step automatically.

Usage (once both sheets are filled in):
    python3 b8_v1_collect_annotations.py
"""
from __future__ import annotations
import csv, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
from soundver.validity import score_audit

AUDIT_DIR = "out/label_audit"
VALID = {"correct", "incorrect", "unsure"}


def load_sheet(path, annotator):
    rows = []
    with open(path) as f:
        for row in csv.DictReader(f):
            label = row["human_label(correct|incorrect|unsure)"].strip().lower()
            if not label:
                raise SystemExit(f"{path} row_id={row['row_id']}: empty human_label -- "
                                 f"annotation is not complete yet")
            if label not in VALID:
                raise SystemExit(f"{path} row_id={row['row_id']}: label {label!r} not "
                                 f"one of {VALID}")
            rows.append({"row_id": int(row["row_id"]), "annotator": annotator,
                        "human_label": label})
    return rows


def main():
    all_rows = []
    all_rows += load_sheet(os.path.join(AUDIT_DIR, "annotation_sheet_1.csv"), "annotator_1")
    all_rows += load_sheet(os.path.join(AUDIT_DIR, "annotation_sheet_2.csv"), "annotator_2")

    out_path = os.path.join(AUDIT_DIR, "annotations.jsonl")
    with open(out_path, "w") as f:
        for r in all_rows:
            f.write(json.dumps(r) + "\n")
    print(f"wrote {out_path} ({len(all_rows)} annotations)")

    print("\nRunning soundver.validity score...\n")
    # score_audit needs a records path with per-instance Record data for the
    # ceiling recomputation half of the report -- use the combined seed-0
    # records file already built this session.
    records_path = "data/records_all_seed0.jsonl"
    score_audit(out_path, records_path)


if __name__ == "__main__":
    main()
