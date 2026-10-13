#!/bin/bash
cd "$(dirname "$0")/../.."   # repo root
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p logs
for t in ie sql; do
  until grep -q "logged cost this run" logs/pool_${t}_certify_multi.log; do sleep 30; done
  python3 -m certver.curve --task $t --candidates "out/candidates/${t}_*.jsonl" \
    --admit data/pools/pool_${t}_admit_seed0.jsonl --certify data/pools/pool_${t}_certify_seed0.jsonl \
    --taus 0.01 0.02 0.05 --out out/curve_${t}_inst_multi.json > logs/curve_${t}_multi.log 2>&1
  python3 -m certver.report --task $t --curve out/curve_${t}_inst_multi.json \
    --out out/report_${t}_multi.json > logs/report_${t}_multi.log 2>&1
done
echo ALLDONE >> logs/report_sql_multi.log
