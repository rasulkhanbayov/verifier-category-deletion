#!/bin/bash
# Re-run the six selection curves with Bonferroni-corrected certification (method audit 2026-10-13).
cd "$(dirname "$0")/../.."   # repo root
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p logs
for t in ie sql morph math fewnerd fc; do
  python3 -u -m certver.curve --task $t --candidates "out/candidates/${t}_*.jsonl" \
      --admit data/pools/pool_${t}_admit_seed0.jsonl --certify data/pools/pool_${t}_certify_seed0.jsonl \
      --taus 0.01 0.02 0.05 --out out/curve_${t}_inst_multi.json > logs/curve_${t}_multi_bonf.log 2>&1
done
echo ALLDONE > logs/run_curve_bonf.done
