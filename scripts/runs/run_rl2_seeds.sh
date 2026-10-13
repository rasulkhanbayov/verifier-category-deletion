#!/bin/bash
# E3 (claim-evidence audit 2026-10-13): RL design 2, seeds 2 and 3 for the F1 and certified gates.
cd "$(dirname "$0")/../.."   # repo root
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p logs
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
PY="${TRAIN_PYTHON:-python3}"   # Python env from requirements-train.txt
for s in 2 3; do for v in f1 certified; do
  [ -f data/rl/gen_ie_rl2_${v}_s$s.jsonl ] && continue
  $PY src/train_grpo.py --verifier $v --seed $s --steps 200 --lr 2e-5 --init-adapter data/rl/sft_oracle_adapter \
      --out data/rl/gen_ie_rl2_${v}_s$s.jsonl --log data/rl/log_ie_rl2_${v}_s$s.jsonl > logs/rl2_ie_${v}_s$s.log 2>&1
done; done
python3 -m certver.eval_distill --task ie --gens data/rl/gen_ie_sftinit.jsonl "data/rl/gen_ie_rl2_*.jsonl" \
    --out out/rl2_ie_seeds.json > logs/eval_rl2_ie_seeds.log 2>&1
echo ALLDONE > logs/run_rl2_seeds.done
