#!/bin/bash
# Extra training seeds for the two key conditions (certified vs F1-selected).
cd "$(dirname "$0")/../.."   # repo root
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p logs
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
PY="${TRAIN_PYTHON:-python3}"   # Python env from requirements-train.txt
for s in 1 2; do for c in certified f1_baseline; do
  $PY src/train_sft.py --train data/distill/sft_ie_$c.jsonl --eval data/distill/eval_ie_prompts.jsonl \
      --out data/distill/seeds/gen_ie_${c}_s$s.jsonl --batch 4 --accum 4 --seed $s > logs/train_ie_${c}_s$s.log 2>&1
done; done
echo ALLDONE >> logs/train_ie_f1_baseline_s2.log
