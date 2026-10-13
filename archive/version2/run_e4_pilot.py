#!/usr/bin/env python3
"""
run_e4_pilot.py
-----------------
Experiment 4 (stacking): add the sound checks one at a time in Table 1's
order (parses -> schema_valid -> executes) and confirm Prop. 4's
prediction that eps is non-increasing and gain is non-decreasing at every
step. 200 instances x 4 models, N=16 per Sec. 6's default, matching E1/E2's
scope (8 samples/instance is enough to run the gated rule at N=8 or less;
using 8 samples here and evaluating the rule at N=8 to stay within budget).
"""
import json
import time

import spider_task as st
import soundver_experiments as se

DB_ROOT = "../spider_data/spider_data/database"
TABLES_JSON = "../spider_data/spider_data/tables.json"
N_INSTANCES = 200
N_SAMPLES = 8
MODELS = ["gpt-4o-mini", "gpt-4o", "llama-3.1-8b", "llama-3.1-70b"]
ORDERED_CHECKS = ["parses", "schema_valid", "executes"]
OUT_PATH = "pilot_e4_results.json"


def run_for_model(model, seed=0):
    print(f"[{model}] loading {N_INSTANCES} instances, {N_SAMPLES} samples each...", flush=True)
    t0 = time.time()
    instances = st.load_spider_instances(
        model=model, split="dev", n_instances=N_INSTANCES, n_samples=N_SAMPLES,
        temperature=0.7, tables_json_path=TABLES_JSON, db_root=DB_ROOT, seed=seed)
    dt = time.time() - t0
    print(f"[{model}] loaded {len(instances)} instances in {dt:.0f}s", flush=True)

    e4 = se.run_e4(instances, ORDERED_CHECKS, N=N_SAMPLES)
    print(f"[{model}] E4 (stacking):", flush=True)
    for row in e4["rows"]:
        print(f"    stack={row['stack']}  eps={row['eps']:.4f}  delta={row['delta']:.4f}  "
              f"accuracy={row['accuracy']:.4f}", flush=True)
    print(f"    eps_non_increasing={e4['eps_non_increasing']}  "
          f"gain_non_decreasing={e4['gain_non_decreasing']}", flush=True)

    return {"model": model, "n_loaded": len(instances), "e4": e4}


def main():
    results = []
    for model in MODELS:
        try:
            result = run_for_model(model)
        except Exception as e:
            print(f"[{model}] FAILED: {e}", flush=True)
            result = {"model": model, "error": str(e)}
        results.append(result)
        with open(OUT_PATH, "w") as f:
            json.dump(results, f, indent=2)
        print(f"[{model}] done, written to {OUT_PATH}\n", flush=True)

    print("=" * 60)
    print("ALL MODELS DONE")


if __name__ == "__main__":
    main()
