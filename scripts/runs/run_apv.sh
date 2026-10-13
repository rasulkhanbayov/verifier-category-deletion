#!/bin/bash
# Add the AutoPyVerifier-objective baseline everywhere (no API).
cd "$(dirname "$0")/../.."   # repo root
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p logs
for t in ie sql morph math fewnerd fc; do
  python3 -u -m certver.curve --task $t --candidates "out/candidates/${t}_*.jsonl" \
      --admit data/pools/pool_${t}_admit_seed0.jsonl --certify data/pools/pool_${t}_certify_seed0.jsonl \
      --taus 0.01 0.02 0.05 --out out/curve_${t}_inst_multi.json > logs/curve_${t}_multi.log 2>&1
done
for t in ie sql morph math; do
  python3 -u -m certver.report --task $t --curve out/curve_${t}_inst_multi.json \
      --pools data/fresh/pool_${t}_fresh_seed0.jsonl --out out/report_${t}_fresh.json > logs/report_${t}_fresh.log 2>&1
  python3 -u -m certver.report --task $t --curve out/curve_${t}_inst_multi.json \
      --out out/report_${t}_multi.json > logs/report_${t}_multi.log 2>&1
done
for t in ie sql morph math fewnerd fc; do
  python3 -u -m certver.robust --task $t --replicates 200 --out out/robust_$t.json > logs/robust_$t.log 2>&1
done
echo ALLDONE > logs/run_apv.done
