#!/bin/bash
# Local (no API) analyses on the data bought 2026-10-12. Waits for run_paid_oct12.
cd "$(dirname "$0")/../.."   # repo root
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p logs
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
PY="${TRAIN_PYTHON:-python3}"   # Python env from requirements-train.txt
until [ -f logs/run_paid_oct12.done ]; do sleep 60; done
until [ -f logs/paid_fewnerd_distill2.done ]; do sleep 60; done
# like-with-like pools for the new tasks: greedy + first 3 samples per model
python3 - <<'PYEOF'
import json, shutil
for t in ("fewnerd", "fc"):
    for s in (0, 1, 2):
        src = f"data/test/pool_{t}_test_seed{s}"
        dst = f"data/test_bstruct/pool_{t}_test_seed{s}"
        shutil.copy(src + ".items.jsonl", dst + ".items.jsonl")
        with open(dst + ".jsonl", "w") as f:
            for l in open(src + ".jsonl"):
                if l.strip() and json.loads(l)["cand_idx"] in (-1, 0, 1, 2):
                    f.write(l)
PYEOF
# final evaluation for the new tasks = the three untouched test draws, pooled
for t in fewnerd fc; do
  python3 -u -m certver.report --task $t --curve out/curve_${t}_inst_multi.json \
      --pools data/test/pool_${t}_test_seed0.jsonl data/test/pool_${t}_test_seed1.jsonl data/test/pool_${t}_test_seed2.jsonl \
      --out out/report_${t}_fresh.json > logs/report_${t}_fresh.log 2>&1
done
# completed fresh draws
for t in sql math; do
  python3 -u -m certver.report --task $t --curve out/curve_${t}_inst_multi.json \
      --pools data/fresh/pool_${t}_fresh_seed0.jsonl --out out/report_${t}_fresh.json > logs/report_${t}_fresh.log 2>&1
done
python3 -u -m certver.report --task math --curve out/curve_math_inst_multi.json \
    --pools data/fresh_weak/pool_math_fresh_seed0.jsonl --out out/report_math_fresh_weak.json > logs/report_math_fresh_weak.log 2>&1
for t in fewnerd fc; do
  python3 -u -m certver.robust --task $t --replicates 200 --out out/robust_$t.json > logs/robust_$t.log 2>&1
done
# Few-NERD distillation from the proper distill pool (old B-based run archived as *_fromB)
[ -d data/distill_fewnerd_fromB ] || cp -r data/distill_fewnerd data/distill_fewnerd_fromB
[ -f out/distill_fewnerd_fromB.json ] || cp out/distill_fewnerd.json out/distill_fewnerd_fromB.json
python3 -m certver.distill_sets --task fewnerd --pool data/distill/pool_fewnerd_distill_seed0.jsonl \
    --curve out/curve_fewnerd_inst_multi.json --out-dir data/distill_fewnerd > logs/distill_sets_fewnerd.log 2>&1
for c in certified f1_baseline handwritten oracle none; do
  $PY src/train_sft.py --train data/distill_fewnerd/sft_fewnerd_$c.jsonl --eval data/distill_fewnerd/eval_fewnerd_prompts.jsonl \
      --out data/distill_fewnerd/gen_fewnerd_$c.jsonl --batch 4 --accum 4 > logs/train_fewnerd_$c.log 2>&1
done
python3 -m certver.eval_distill --task fewnerd --gens "data/distill_fewnerd/gen_fewnerd_*.jsonl" \
    --out out/distill_fewnerd.json > logs/eval_distill_fewnerd.log 2>&1
echo ALLDONE > logs/run_paid_post.done
