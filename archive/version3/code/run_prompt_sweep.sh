#!/bin/bash
set -e
MODELS="openai/gpt-4o-2024-11-20 openai/gpt-4o-mini-2024-07-18 meta-llama/llama-3.1-8b-instruct meta-llama/llama-3.1-70b-instruct"
mkdir -p data/prompt_sweep logs
for task in sql ie morph; do
  for variant in paraphrase_a paraphrase_b no_fewshot format_reminder; do
    echo "=== $task / $variant ==="
    python3 -m soundver.generate --task "$task" --models $MODELS --seeds 0 \
      --instances 60 --candidates 8 --prompt-id "$variant" \
      --out "data/prompt_sweep/records_${task}_${variant}.jsonl"
  done
done
echo "ALL DONE"
