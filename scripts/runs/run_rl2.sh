#!/bin/bash
# RL design 2: start from the label-filtered (oracle) SFT student, which already
# produces correct "else" entities, so a verifier that rejects them can matter.
cd "$(dirname "$0")/../.."   # repo root
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p logs
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
PY="${TRAIN_PYTHON:-python3}"   # Python env from requirements-train.txt
if [ ! -f data/rl/sft_oracle_adapter/adapter_config.json ]; then
  $PY src/train_sft.py --train data/distill/sft_ie_oracle.jsonl --eval data/distill/eval_ie_prompts.jsonl \
      --out data/rl/gen_ie_sftinit.jsonl --batch 4 --accum 4 --save-adapter data/rl/sft_oracle_adapter \
      > logs/rl2_sft_oracle.log 2>&1
fi
for s in 0 1; do for v in f1 certified label; do
  [ -f data/rl/gen_ie_rl2_${v}_s$s.jsonl ] && continue
  $PY src/train_grpo.py --verifier $v --seed $s --steps 200 --lr 2e-5 --init-adapter data/rl/sft_oracle_adapter \
      --out data/rl/gen_ie_rl2_${v}_s$s.jsonl --log data/rl/log_ie_rl2_${v}_s$s.jsonl > logs/rl2_ie_${v}_s$s.log 2>&1
done; done
python3 -m certver.eval_distill --task ie --gens data/rl/gen_ie_base.jsonl data/rl/gen_ie_sftinit.jsonl "data/rl/gen_ie_rl2_*.jsonl" \
    --out out/rl2_ie.json > logs/eval_rl2_ie.log 2>&1
echo ALLDONE >> logs/eval_rl2_ie.log
