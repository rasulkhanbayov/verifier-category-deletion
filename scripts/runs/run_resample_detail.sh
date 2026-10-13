#!/bin/bash
cd "$(dirname "$0")/../.."   # repo root
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p logs
python3 -u -m certver.resample_detail --task ie --out out/resample_detail_ie.json > logs/resample_detail_ie.log 2>&1
python3 -u -m certver.resample_detail --task fewnerd --inject out/candidates_inject/fewnerd.jsonl --out out/resample_detail_fewnerd_inject.json > logs/resample_detail_fewnerd_inject.log 2>&1
for t in sql fc math morph fewnerd; do
  python3 -u -m certver.resample_detail --task $t --out out/resample_detail_$t.json > logs/resample_detail_$t.log 2>&1
done
echo ALLDONE > logs/run_resample_detail.done
