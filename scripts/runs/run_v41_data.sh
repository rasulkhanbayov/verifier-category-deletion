#!/bin/bash
# v4.1 W5: launch new-task test draws and the fewnerd distill pool once the
# fresh draws of the original tasks have finished (keeps API concurrency sane).
cd "$(dirname "$0")/../.."   # repo root
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p logs
M3="openai/gpt-4o-mini-2024-07-18 meta-llama/llama-3.1-70b-instruct qwen/qwen-2.5-72b-instruct"
until [ "$(grep -l 'logged cost this run' logs/fresh_ie.log logs/fresh_sql.log logs/fresh_morph.log 2>/dev/null | wc -l)" = "3" ]; do sleep 60; done
for t in fewnerd fc; do for s in 0 1 2; do
  python3 -m certver.pool --task $t --split test --models $M3 --seeds $s --instances 200 --candidates 32 \
      --max-cost 5 --out-dir data/test > logs/test_${t}_seed$s.log 2>&1 &
done; done
python3 -m certver.pool --task fewnerd --split distill --models $M3 --candidates 3 --max-cost 5 \
    --out-dir data/distill > logs/pool_fewnerd_distill.log 2>&1 &
wait
echo ALLDONE > logs/run_v41_data.done
