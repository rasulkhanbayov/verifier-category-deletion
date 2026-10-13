#!/bin/bash
# Final, untouched evaluation on the fresh draws (frozen selections from the
# multi-model curves; pre-specified certified rule). No API calls.
cd "$(dirname "$0")/../.."   # repo root
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p logs
for t in ie sql morph math; do
  python3 -u -m certver.report --task $t --curve out/curve_${t}_inst_multi.json \
      --pools data/fresh/pool_${t}_fresh_seed0.jsonl --out out/report_${t}_fresh.json > logs/report_${t}_fresh.log 2>&1
done
for t in sql math; do   # transfer to weaker generators never seen in A/B
  python3 -u -m certver.report --task $t --curve out/curve_${t}_inst_multi.json \
      --pools data/fresh_weak/pool_${t}_fresh_seed0.jsonl --out out/report_${t}_fresh_weak.json > logs/report_${t}_fresh_weak.log 2>&1
done
echo ALLDONE >> logs/report_math_fresh_weak.log
