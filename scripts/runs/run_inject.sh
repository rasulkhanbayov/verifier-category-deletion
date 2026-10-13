#!/bin/bash
# Stress test (no API): add group-isolating checks to the candidate pool.
cd "$(dirname "$0")/../.."   # repo root
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p logs
for t in fewnerd morph sql; do
  python3 -u -m certver.robust --task $t --replicates 200 --inject out/candidates_inject/$t.jsonl \
      --out out/robust_${t}_inject.json > logs/robust_${t}_inject.log 2>&1
done
echo ALLDONE > logs/run_inject.done
