#!/bin/bash
# RL experiment (v4.1 W6 optional): GRPO with verifier-gated reward, IE.
cd "$(dirname "$0")/../.."   # repo root
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p logs
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
PY="${TRAIN_PYTHON:-python3}"   # Python env from requirements-train.txt
for s in 0 1; do for v in f1 certified label handwritten; do
  [ -f data/rl/gen_ie_${v}_s$s.jsonl ] && continue
  $PY src/train_grpo.py --verifier $v --seed $s --steps 300 \
      --out data/rl/gen_ie_${v}_s$s.jsonl --log data/rl/log_ie_${v}_s$s.jsonl > logs/rl_ie_${v}_s$s.log 2>&1
done; done
python3 -m certver.eval_distill --task ie --gens "data/rl/gen_ie_*.jsonl" --out out/rl_ie.json > logs/eval_rl_ie.log 2>&1
echo ALLDONE >> logs/eval_rl_ie.log
