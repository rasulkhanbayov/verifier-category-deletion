#!/bin/bash
# Downstream data-filtering experiment (IE). Detached driver; see PLAN.md.
cd "$(dirname "$0")/../.."   # repo root
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p logs
PY="${TRAIN_PYTHON:-python3}"   # Python env from requirements-train.txt
until grep -q "logged cost this run" logs/pool_ie_distill.log; do sleep 60; done
python3 -m certver.distill_sets --task ie --pool data/distill/pool_ie_distill_seed0.jsonl \
    --curve out/curve_ie_inst_multi.json --out-dir data/distill > logs/distill_sets_ie.log 2>&1
run() {  # $1 = condition
  $PY src/train_sft.py --train data/distill/sft_ie_$1.jsonl --eval data/distill/eval_ie_prompts.jsonl \
      --out data/distill/gen_ie_$1.jsonl > logs/train_ie_$1.log 2>&1
}
run certified & run f1_baseline & wait
run handwritten & run oracle & wait
run none
python3 -m certver.eval_distill --task ie --gens "data/distill/gen_ie_*.jsonl" \
    --out out/distill_ie.json > logs/eval_distill_ie.log 2>&1
echo ALLDONE >> logs/eval_distill_ie.log
