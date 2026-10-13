#!/bin/bash
# Finish item D (Few-NERD distill pool): Qwen stopped at the $3.00 per-run cap
# with 1677/2000 inputs; ~323 remaining, est. $0.17. Within the user's $28 cap.
cd "$(dirname "$0")/../.."   # repo root
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p logs
python3 -m certver.pool --task fewnerd --split distill --models qwen/qwen-2.5-72b-instruct --candidates 3 --max-cost 0.6 \
    --global-cap 410.85 --out-dir data/distill > logs/paid_pool_fewnerd_distill2.log 2>&1
echo ALLDONE > logs/paid_fewnerd_distill2.done
