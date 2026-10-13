#!/bin/bash
# Resume the Qwen collection (P9) after a real, now-understood bug: a
# pathological model-generated SQL query executed against SQLite with no
# progress handler can run unbounded (sqlite3.connect(timeout=...) only
# bounds LOCK-WAIT time, not query execution time), and
# as_completed()/ThreadPoolExecutor's default shutdown(wait=True) has no
# way to skip past one hung future -- confirmed via /proc thread counts
# (~99-106 threads vs 8 expected) and reproduced twice at the same point
# in sql/seed1's instance order. Fixed generate.py with a real
# per-instance hard timeout (concurrent.futures.wait with
# FIRST_COMPLETED + shutdown(wait=False) + os._exit at the very end to
# bypass Python's non-daemon-thread-blocks-process-exit behavior).
# sql/seed0 already completed cleanly and is NOT re-run.
set -e
MODELS="qwen/qwen-2.5-7b-instruct qwen/qwen-2.5-72b-instruct"
export SOUNDVER_GEN_WORKERS=4

for task in sql ie morph; do
  for seed in 0 1 2 3 4; do
    if [ "$task" = "sql" ] && [ "$seed" = "0" ]; then
      echo "=== sql / seed=0 / qwen -- ALREADY DONE, skipping ==="
      continue
    fi
    echo "=== $task / seed=$seed / qwen ==="
    python3 -m soundver.generate --task "$task" --models $MODELS --seeds "$seed" \
      --instances 200 --candidates 32 --prompt-id base \
      --out "data/records_${task}_qwen_seed${seed}.jsonl"
  done
done
echo "QWEN COLLECTION DONE"
