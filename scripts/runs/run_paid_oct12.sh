#!/bin/bash
# User-approved spend 2026-10-12: A+B+C+D, hard cap $28 (sum of per-run
# --max-cost = $26.10; --global-cap aborts any run starting above $410.85).
cd "$(dirname "$0")/../.."   # repo root
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p logs
M3="openai/gpt-4o-mini-2024-07-18 meta-llama/llama-3.1-70b-instruct qwen/qwen-2.5-72b-instruct"
GC=410.85
# A: Few-NERD and FC test draws (3 x 200 inputs, 33 outputs per model)
for s in 0 1 2; do
  python3 -m certver.pool --task fewnerd --split test --models $M3 --seeds $s --instances 200 --candidates 32 \
      --max-cost 3.5 --global-cap $GC --out-dir data/test > logs/paid_test_fewnerd_seed$s.log 2>&1 &
  python3 -m certver.pool --task fc --split test --models $M3 --seeds $s --instances 200 --candidates 32 \
      --max-cost 2.7 --global-cap $GC --out-dir data/test > logs/paid_test_fc_seed$s.log 2>&1 &
done
wait
# B: finish the GSM8K fresh draw (Llama, Qwen)
python3 -m certver.pool --task math --split fresh --models meta-llama/llama-3.1-70b-instruct qwen/qwen-2.5-72b-instruct \
    --seeds 0 --instances 300 --candidates 32 --max-cost 3.5 --global-cap $GC --out-dir data/fresh > logs/paid_fresh_math.log 2>&1 &
# C: small fills
python3 -m certver.pool --task sql --split fresh --models qwen/qwen-2.5-72b-instruct \
    --seeds 0 --instances 300 --candidates 32 --max-cost 0.2 --global-cap $GC --out-dir data/fresh > logs/paid_fresh_sql.log 2>&1 &
python3 -m certver.pool --task math --split fresh --models meta-llama/llama-3.1-8b-instruct qwen/qwen-2.5-7b-instruct \
    --seeds 0 --instances 300 --candidates 32 --max-cost 0.8 --global-cap $GC --out-dir data/fresh_weak > logs/paid_fresh_weak_math.log 2>&1 &
# D: Few-NERD distillation pool
python3 -m certver.pool --task fewnerd --split distill --models $M3 --candidates 3 --max-cost 3.0 \
    --global-cap $GC --out-dir data/distill > logs/paid_pool_fewnerd_distill.log 2>&1 &
wait
echo ALLDONE > logs/run_paid_oct12.done
