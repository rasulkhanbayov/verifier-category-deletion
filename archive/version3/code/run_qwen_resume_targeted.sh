#!/bin/bash
# Targeted resume after discovering the rate-limit bug (fixed in generate.py:
# 429/504 now get a much longer, Retry-After-respecting backoff instead of
# the generic 1-2-4s retry, which let entire (task, model, seed) cells fail
# outright under sustained provider-side throttling on the two Qwen models).
#
# IMPORTANT: generate.py's write() OVERWRITES the whole output file per
# invocation (not append, not per-model-file) -- a call with only one model
# would silently wipe out an already-good OTHER model's data already in
# that seed's file. So every seed listed below re-runs BOTH models
# together, even where one of them already succeeded -- wasteful (re-fetches
# a few thousand already-good completions) but eliminates any data-loss
# risk from the overwrite semantics.
set -e
export SOUNDVER_GEN_WORKERS=3   # further reduced: less concurrent pressure
                                 # on the specific overloaded provider
export SOUNDVER_INSTANCE_TIMEOUT=240
MODELS="qwen/qwen-2.5-7b-instruct qwen/qwen-2.5-72b-instruct"

run() {
  local task=$1 seed=$2
  echo "=== $task / seed=$seed / both models (safe overwrite) ==="
  python3 -m soundver.generate --task "$task" --models $MODELS --seeds "$seed" \
    --instances 200 --candidates 32 --prompt-id base \
    --out "data/records_${task}_qwen_seed${seed}.jsonl"
}

# SQL: seeds 2,3,4 have an incomplete/missing 72B model
run sql 2
run sql 3
run sql 4

# IE: seeds 0-4 all need at least the 72B model redone
run ie 0
run ie 1
run ie 2
run ie 3
run ie 4

# morph: nothing done yet at all
run morph 0
run morph 1
run morph 2
run morph 3
run morph 4

echo "TARGETED RESUME DONE"
