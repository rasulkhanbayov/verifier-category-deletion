#!/bin/bash
# Re-run of the IE students, one at a time (parallel run hit CUDA OOM on the shared P100).
cd "$(dirname "$0")/../.."   # repo root
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p logs
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
PY="${TRAIN_PYTHON:-python3}"   # Python env from requirements-train.txt
for c in certified f1_baseline handwritten oracle none; do
  $PY src/train_sft.py --train data/distill/sft_ie_$c.jsonl --eval data/distill/eval_ie_prompts.jsonl \
      --out data/distill/gen_ie_$c.jsonl --batch 4 --accum 4 > logs/train_ie_$c.log 2>&1
done
python3 -m certver.eval_distill --task ie --gens "data/distill/gen_ie_*.jsonl" \
    --out out/distill_ie.json > logs/eval_distill_ie.log 2>&1
echo ALLDONE >> logs/eval_distill_ie.log
