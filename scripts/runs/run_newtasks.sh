#!/bin/bash
# New tasks (fewnerd, fc): A/B-only analyses (no test draws: no API credit).
cd "$(dirname "$0")/../.."   # repo root
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p logs
for t in fewnerd fc; do
  python3 -u -m certver.curve --task $t --candidates "out/candidates/${t}_*.jsonl" \
      --admit data/pools/pool_${t}_admit_seed0.jsonl --certify data/pools/pool_${t}_certify_seed0.jsonl \
      --taus 0 0.0025 0.005 0.01 0.02 0.03 0.05 0.1 --out out/curve_${t}_dense.json > logs/curve_${t}_dense.log 2>&1
  python3 -u -m certver.curve --task $t --candidates "out/candidates/${t}_*.jsonl" \
      --admit data/pools/pool_${t}_admit_seed0.jsonl --certify data/pools/pool_${t}_certify_seed0.jsonl \
      --taus 0.01 0.02 0.05 --out out/curve_${t}_inst_multi.json > logs/curve_${t}_multi.log 2>&1
  python3 -u -m certver.robust --task $t --replicates 200 --out out/robust_$t.json > logs/robust_$t.log 2>&1
done
echo ALLDONE >> logs/robust_fc.log
