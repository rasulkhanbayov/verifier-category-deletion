#!/bin/bash
# Second targeted resume. Root cause of the persistent 72B failures found:
# NOT a rate-limit/hang bug (that fix was real and needed, but insufficient
# on its own) -- the 72B model is simply, legitimately ~10x slower per call
# than the 7B model (measured directly: 12-18s/call for 72B vs ~1-2s for
# 7B, via Novita/DeepInfra backends). process_one() makes its 33
# completions (1 base + 32 candidates) SERIALLY within one instance, so a
# single 72B instance genuinely needs ~33*15s =~ 8+ minutes end to end.
# SOUNDVER_INSTANCE_TIMEOUT=240 (4 min) was shorter than that real serial
# cost, so it was forcing near-100% timeouts on 72B regardless of retry
# logic quality -- a self-inflicted timeout-too-short problem, not a
# provider outage. Raised to 900s (15 min) with real margin.
set -e
export SOUNDVER_GEN_WORKERS=8
export SOUNDVER_INSTANCE_TIMEOUT=900
MODELS="qwen/qwen-2.5-7b-instruct qwen/qwen-2.5-72b-instruct"

run() {
  local task=$1 seed=$2
  echo "=== $task / seed=$seed / both models (safe overwrite) ==="
  python3 -m soundver.generate --task "$task" --models $MODELS --seeds "$seed" \
    --instances 200 --candidates 32 --prompt-id base \
    --out "data/records_${task}_qwen_seed${seed}.jsonl"
}

run sql 2
run sql 3
run sql 4
run ie 0
run ie 4
run morph 1
run morph 2
run morph 3
run morph 4

echo "RESUME2 DONE"
