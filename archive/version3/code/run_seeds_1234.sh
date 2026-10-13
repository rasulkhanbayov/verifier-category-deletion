#!/bin/bash
set -e
MODELS="openai/gpt-4o-2024-11-20 openai/gpt-4o-mini-2024-07-18 meta-llama/llama-3.1-8b-instruct meta-llama/llama-3.1-70b-instruct"
mkdir -p logs
for task in sql ie morph; do
  for seed in 1 2 3 4; do
    echo "=== $task / seed=$seed ==="
    python3 -m soundver.generate --task "$task" --models $MODELS --seeds "$seed" \
      --instances 200 --candidates 32 --prompt-id base \
      --out "data/records_${task}_seed${seed}.jsonl"
  done
done
echo "ALL SEEDS DONE"
