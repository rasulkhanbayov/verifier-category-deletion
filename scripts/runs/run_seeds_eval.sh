#!/bin/bash
cd "$(dirname "$0")/../.."   # repo root
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p logs
until grep -q ALLDONE logs/train_ie_f1_baseline_s2.log 2>/dev/null; do sleep 60; done
python3 -m certver.eval_distill --task ie --gens data/distill/gen_ie_certified.jsonl data/distill/gen_ie_f1_baseline.jsonl \
    "data/distill/seeds/gen_ie_*_s*.jsonl" --out out/distill_ie_seeds.json > logs/eval_distill_seeds.log 2>&1
echo ALLDONE >> logs/eval_distill_seeds.log
