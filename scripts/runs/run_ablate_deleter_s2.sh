#!/bin/bash
# Retry seed 2 of the deleter ablation (OOM on a shared GPU); same settings. Waits for >= 10 GB free.
cd "$(dirname "$0")/../.."   # repo root
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p logs
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
PY="${TRAIN_PYTHON:-python3}"   # Python env from requirements-train.txt
for attempt in 1 2 3 4 5 6; do
  until [ "$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1)" -ge 10000 ]; do sleep 60; done
  $PY src/train_sft.py --train data/distill/ablate/sft_ie_f1_minus_deleter.jsonl --eval data/distill/eval_ie_prompts.jsonl \
      --out data/distill/ablate/gen_ie_f1minusdel_s2.jsonl --batch 4 --accum 4 --seed 2 > logs/train_ie_f1minusdel_s2.log 2>&1 && break
  sleep 300
done
python3 -m certver.eval_distill --task ie --gens "data/distill/ablate/gen_ie_f1minusdel_s*.jsonl" --out out/distill_ie_f1minusdel.json > logs/eval_distill_f1minusdel.log 2>&1
echo ALLDONE > logs/run_ablate_deleter.done
