#!/bin/bash
# Adversarial audit #2: deletion at tau = 1% and 5% (A-budget 0.005 / 0.025).
cd "$(dirname "$0")/../.."   # repo root
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p logs
for b in 0.025 0.005; do for t in ie fewnerd fc sql math morph; do
  python3 -u -m certver.resample_detail --task $t --budget $b --out out/resample_detail_${t}_b$b.json > logs/resample_detail_${t}_b$b.log 2>&1
done; done
echo ALLDONE > logs/run_budget_sens.done
