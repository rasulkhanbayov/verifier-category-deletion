#!/usr/bin/env bash
# Reproduce every number in the paper from per-instance records.
#
#   ./run_all.sh                      # synthetic smoke test, runs today
#   ./run_all.sh data/records.jsonl   # the real thing, once B7 is closed
set -euo pipefail
REC="${1:-data/synthetic_records.jsonl}"
OUT="${2:-out}"
mkdir -p "$OUT"

if [ "$REC" = "data/synthetic_records.jsonl" ] && [ ! -f "$REC" ]; then
  echo "== generating synthetic smoke-test records =="
  python3 -c "
from soundver.records import synthesize, write
r=[]
for t,p0,p,e,d in [('sql',.72,.73,.99,0),('ie',.46,.47,.97,0),('morph',.445,.436,.74,.188)]:
    for m in ['openai/gpt-4o-2024-11-20','meta-llama/llama-3.1-70b-instruct']:
        for s in (0,1,2): r+=synthesize(task=t,model=m,n_instances=120,seed=s,p0=p0,p=p,eps=e,delta=d)
write(r,'data/synthetic_records.jsonl')"
fi

echo "== 0. reference check stacks (self-test) =="
python3 -m soundver.checks --selftest

echo
echo "== 1. reconcile: rates, ceiling, rules, exhaustive subsets, seeds =="
python3 -m soundver.reconcile --records "$REC" --out "$OUT" --all

echo
echo "== 2. prompt sweep (B8-V2) =="
python3 -m soundver.validity prompts --records "$REC" || true

echo
echo "== 3. label-audit sampling (B8-V1) =="
python3 -m soundver.validity sample --records "$REC" --out "$OUT"

echo
echo "== 4. theory checks (independent of any data) =="
python3 ../verify_theory.py  | tail -3
python3 ../verify_ceiling.py | tail -3

echo
echo "Outputs in $OUT/. Paste $OUT/tab_ceiling.tex into the paper; do not"
echo "hand-edit table numbers."
