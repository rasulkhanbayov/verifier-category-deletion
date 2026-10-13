#!/bin/bash
# A1 (adversarial audit): distil on F1-selected data with ONLY the deleting check removed (3 seeds).
cd "$(dirname "$0")/../.."   # repo root
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p logs
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
PY="${TRAIN_PYTHON:-python3}"   # Python env from requirements-train.txt
for s in 0 1 2; do
  $PY src/train_sft.py --train data/distill/ablate/sft_ie_f1_minus_deleter.jsonl --eval data/distill/eval_ie_prompts.jsonl \
      --out data/distill/ablate/gen_ie_f1minusdel_s$s.jsonl --batch 4 --accum 4 --seed $s > logs/train_ie_f1minusdel_s$s.log 2>&1
done
python3 -m certver.eval_distill --task ie --gens "data/distill/ablate/gen_ie_f1minusdel_s*.jsonl" --out out/distill_ie_f1minusdel.json > logs/eval_distill_f1minusdel.log 2>&1
echo ALLDONE > logs/run_ablate_deleter.done
