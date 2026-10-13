#!/bin/bash
# W6 remainder: size-matched distillation (certified subsampled to the F1
# set size, 3 subsamples/seeds) and a 1.7B student (certified vs F1).
cd "$(dirname "$0")/../.."   # repo root
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p logs
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
PY="${TRAIN_PYTHON:-python3}"   # Python env from requirements-train.txt
for s in 0 1 2; do
  $PY src/train_sft.py --train data/distill/matched/sft_ie_certified_matched_s$s.jsonl --eval data/distill/eval_ie_prompts.jsonl \
      --out data/distill/matched/gen_ie_certmatched_s$s.jsonl --batch 4 --accum 4 --seed $s > logs/train_ie_certmatched_s$s.log 2>&1
done
for c in certified f1_baseline; do
  $PY src/train_sft.py --model Qwen/Qwen3-1.7B --train data/distill/sft_ie_$c.jsonl --eval data/distill/eval_ie_prompts.jsonl \
      --out data/distill/big/gen_ie_${c}_1p7b.jsonl --batch 2 --accum 8 > logs/train_ie_${c}_1p7b.log 2>&1
done
python3 -m certver.eval_distill --task ie --gens data/distill/gen_ie_certified.jsonl data/distill/seeds/gen_ie_*_s*.jsonl \
    data/distill/gen_ie_f1_baseline.jsonl "data/distill/matched/gen_ie_certmatched_s*.jsonl" --out out/distill_ie_matched.json > logs/eval_distill_matched.log 2>&1
python3 -m certver.eval_distill --task ie --gens "data/distill/big/gen_ie_*_1p7b.jsonl" --out out/distill_ie_1p7b.json > logs/eval_distill_1p7b.log 2>&1
echo ALLDONE > logs/run_distill_v41.done
