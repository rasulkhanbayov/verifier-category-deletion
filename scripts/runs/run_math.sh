#!/bin/bash
# GSM8K analysis driver. Detached; see PLAN.md.
cd "$(dirname "$0")/../.."   # repo root
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p logs
until grep -q "logged cost this run" logs/pool_math_admit.log && grep -q "logged cost this run" logs/pool_math_certify.log; do sleep 60; done
python3 -m certver.curve --task math --candidates "out/candidates/math_*.jsonl" \
    --admit data/pools/pool_math_admit_seed0.jsonl --certify data/pools/pool_math_certify_seed0.jsonl \
    --taus 0.01 0.02 0.05 --out out/curve_math_inst_multi.json > logs/curve_math.log 2>&1
python3 -m certver.curve --task math --candidates "out/candidates/math_*.jsonl" \
    --admit data/pools/pool_math_admit_seed0.jsonl --certify data/pools/pool_math_certify_seed0.jsonl \
    --taus 0 0.0025 0.005 0.01 0.02 0.03 0.05 0.1 --out out/curve_math_dense.json > logs/curve_math_dense.log 2>&1
echo CURVEDONE >> logs/curve_math.log
until [ "$(grep -l 'logged cost this run' logs/test_math_seed*.log | wc -l)" = "3" ]; do sleep 60; done
python3 -m certver.report --task math --curve out/curve_math_inst_multi.json --out out/report_math_multi.json > logs/report_math.log 2>&1
python3 -m certver.subgroup_acc --task math --out out/subgroup_math.json > logs/subgroup_math.log 2>&1
python3 -m certver.ablate --task math --out out/ablate_math_multi.json > logs/ablate_math.log 2>&1
echo ALLDONE >> logs/report_math.log
