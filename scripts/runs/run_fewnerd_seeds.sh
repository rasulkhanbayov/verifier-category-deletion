#!/bin/bash
# Few-NERD distillation: training seeds 1,2 for certified and F1 (seed 0 = main run).
cd "$(dirname "$0")/../.."   # repo root
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p logs
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
PY="${TRAIN_PYTHON:-python3}"   # Python env from requirements-train.txt
for s in 1 2; do for c in certified f1_baseline; do
  $PY src/train_sft.py --train data/distill_fewnerd/sft_fewnerd_$c.jsonl --eval data/distill_fewnerd/eval_fewnerd_prompts.jsonl \
      --out data/distill_fewnerd/seeds/gen_fewnerd_${c}_s$s.jsonl --batch 4 --accum 4 --seed $s > logs/train_fewnerd_${c}_s$s.log 2>&1
done; done
python3 -m certver.eval_distill --task fewnerd --gens data/distill_fewnerd/gen_fewnerd_certified.jsonl data/distill_fewnerd/gen_fewnerd_f1_baseline.jsonl \
    "data/distill_fewnerd/seeds/gen_fewnerd_*_s*.jsonl" --out out/distill_fewnerd_seeds.json > logs/eval_distill_fewnerd_seeds.log 2>&1
echo ALLDONE > logs/run_fewnerd_seeds.done
