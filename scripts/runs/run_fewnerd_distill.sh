#!/bin/bash
# Few-NERD downstream replication without API: training data = the
# certification split's outputs (B; never used to select checks). Waits for
# the GPU (RL design 2) and for the fewnerd selection curve.
cd "$(dirname "$0")/../.."   # repo root
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p logs
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
PY="${TRAIN_PYTHON:-python3}"   # Python env from requirements-train.txt
until [ -s out/curve_fewnerd_inst_multi.json ]; do sleep 60; done
until grep -q ALLDONE logs/eval_rl2_ie.log 2>/dev/null; do sleep 120; done
python3 -m certver.distill_sets --task fewnerd --pool data/pools/pool_fewnerd_certify_seed0.jsonl \
    --curve out/curve_fewnerd_inst_multi.json --out-dir data/distill_fewnerd > logs/distill_sets_fewnerd.log 2>&1
for c in certified f1_baseline handwritten oracle none; do
  $PY src/train_sft.py --train data/distill_fewnerd/sft_fewnerd_$c.jsonl --eval data/distill_fewnerd/eval_fewnerd_prompts.jsonl \
      --out data/distill_fewnerd/gen_fewnerd_$c.jsonl --batch 4 --accum 4 > logs/train_fewnerd_$c.log 2>&1
done
python3 -m certver.eval_distill --task fewnerd --gens "data/distill_fewnerd/gen_fewnerd_*.jsonl" \
    --out out/distill_fewnerd.json > logs/eval_distill_fewnerd.log 2>&1
echo ALLDONE >> logs/eval_distill_fewnerd.log
