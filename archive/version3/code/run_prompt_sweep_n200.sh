#!/bin/bash
set -e
mkdir -p data/prompt_sweep_n200 logs
# SQL/GPT-4o-mini flagged; IE/GPT-4o and IE/GPT-4o-mini flagged.
python3 -m soundver.generate --task sql --models openai/gpt-4o-mini-2024-07-18 --seeds 0 \
  --instances 200 --candidates 8 --prompt-id paraphrase_a \
  --out data/prompt_sweep_n200/records_sql_gpt4omini_paraphrase_a.jsonl
python3 -m soundver.generate --task sql --models openai/gpt-4o-mini-2024-07-18 --seeds 0 \
  --instances 200 --candidates 8 --prompt-id paraphrase_b \
  --out data/prompt_sweep_n200/records_sql_gpt4omini_paraphrase_b.jsonl
python3 -m soundver.generate --task sql --models openai/gpt-4o-mini-2024-07-18 --seeds 0 \
  --instances 200 --candidates 8 --prompt-id no_fewshot \
  --out data/prompt_sweep_n200/records_sql_gpt4omini_no_fewshot.jsonl
python3 -m soundver.generate --task sql --models openai/gpt-4o-mini-2024-07-18 --seeds 0 \
  --instances 200 --candidates 8 --prompt-id format_reminder \
  --out data/prompt_sweep_n200/records_sql_gpt4omini_format_reminder.jsonl

python3 -m soundver.generate --task ie --models openai/gpt-4o-2024-11-20 openai/gpt-4o-mini-2024-07-18 --seeds 0 \
  --instances 200 --candidates 8 --prompt-id paraphrase_a \
  --out data/prompt_sweep_n200/records_ie_gpt4o_paraphrase_a.jsonl
python3 -m soundver.generate --task ie --models openai/gpt-4o-2024-11-20 openai/gpt-4o-mini-2024-07-18 --seeds 0 \
  --instances 200 --candidates 8 --prompt-id paraphrase_b \
  --out data/prompt_sweep_n200/records_ie_gpt4o_paraphrase_b.jsonl
python3 -m soundver.generate --task ie --models openai/gpt-4o-2024-11-20 openai/gpt-4o-mini-2024-07-18 --seeds 0 \
  --instances 200 --candidates 8 --prompt-id no_fewshot \
  --out data/prompt_sweep_n200/records_ie_gpt4o_no_fewshot.jsonl
python3 -m soundver.generate --task ie --models openai/gpt-4o-2024-11-20 openai/gpt-4o-mini-2024-07-18 --seeds 0 \
  --instances 200 --candidates 8 --prompt-id format_reminder \
  --out data/prompt_sweep_n200/records_ie_gpt4o_format_reminder.jsonl
echo "ALL DONE"
