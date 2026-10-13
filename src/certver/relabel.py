"""
certver.relabel -- apply certver.sqllabel to existing SQL pool files in place.

  python -m certver.relabel data/pools/pool_sql_admit_seed0.jsonl [...]

Keeps the old label as `correct_v2label` and reports how many flipped. Rows
whose instance's gold query fails on the original database are dropped
(logged), since they cannot be labelled.
"""
from __future__ import annotations
import concurrent.futures, json, os, sys
from collections import Counter

from soundver.checks import sql_extract
from .sqllabel import sql_correct, GoldError


def _label(args):
    raw, gold, db = args
    try:
        return sql_correct(sql_extract(raw), gold, db)
    except GoldError:
        return None


def relabel(path: str) -> None:
    items = {}
    with open(path.replace(".jsonl", ".items.jsonl")) as f:
        for line in f:
            if line.strip():
                d = json.loads(line)
                items[d["instance_id"]] = d
    rows = [json.loads(l) for l in open(path) if l.strip()]
    args = [(r["raw"], items[r["instance_id"]]["gold_sql"], items[r["instance_id"]]["db_path"])
            for r in rows]
    with concurrent.futures.ProcessPoolExecutor(max_workers=16) as ex:
        new = list(ex.map(_label, args, chunksize=32))
    flips, kept, dropped = Counter(), [], 0
    for r, n in zip(rows, new):
        if n is None:
            dropped += 1
            continue
        old = r.get("correct_v2label", r["correct"])
        r["correct_v2label"] = old
        r["correct"] = bool(n)
        flips[(old, r["correct"])] += 1
        kept.append(r)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        for r in kept:
            f.write(json.dumps(r) + "\n")
    os.replace(tmp, path)
    n = len(kept)
    print(f"{path}: {n} rows, {dropped} dropped (gold fails on original DB)")
    print(f"  old correct -> new correct   {flips[(True, True)]}")
    print(f"  old correct -> new INCORRECT {flips[(True, False)]}  ({flips[(True, False)] / max(1, flips[(True, True)] + flips[(True, False)]):.1%} of old-correct)")
    print(f"  old incorrect -> new correct {flips[(False, True)]}")
    print(f"  old incorrect -> new incorrect {flips[(False, False)]}")


if __name__ == "__main__":
    for p in sys.argv[1:]:
        relabel(p)
