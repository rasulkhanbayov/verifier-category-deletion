#!/bin/bash
# Resume the Qwen collection (P9) after the first attempt stalled on
# sql/seed1 (4+ hours with zero progress-log advancement past 175/200,
# 106 threads where 8 were expected -- looked like an NFS/SQLite
# contention deadlock, not a slow-but-live process; confirmed dead via
# py-spy unavailability + no log growth, killed and restarting).
# sql/seed0 already completed cleanly and is NOT re-run.
set -e
MODELS="qwen/qwen-2.5-7b-instruct qwen/qwen-2.5-72b-instruct"
export SOUNDVER_GEN_WORKERS=4  # reduced from 8 to lower NFS/SQLite contention

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
