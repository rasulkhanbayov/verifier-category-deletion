#!/bin/bash
cd "$(dirname "$0")/../.."   # repo root
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p logs
for t in ie sql math morph; do
  python3 -u -m certver.robust --task $t --replicates 200 --out out/robust_$t.json > logs/robust_$t.log 2>&1
done
echo ALLDONE >> logs/robust_morph.log
