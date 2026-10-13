#!/bin/bash
set -e
MODELS="qwen/qwen-2.5-7b-instruct qwen/qwen-2.5-72b-instruct"
for task in sql ie morph; do
  for seed in 0 1 2 3 4; do
    echo "=== $task / seed=$seed / qwen ==="
    python3 -m soundver.generate --task "$task" --models $MODELS --seeds "$seed" \
      --instances 200 --candidates 32 --prompt-id base \
      --out "data/records_${task}_qwen_seed${seed}.jsonl"
  done
done
echo "QWEN COLLECTION DONE"
