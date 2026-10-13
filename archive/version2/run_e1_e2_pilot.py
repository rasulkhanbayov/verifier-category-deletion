#!/usr/bin/env python3
"""
run_e1_e2_pilot.py
--------------------
The B1 minimum-viable pilot: E1 (headroom) + E2 (soundness audit) on
text-to-SQL / Spider dev split, 200 instances x 4 models
(gpt-4o-mini, gpt-4o, llama-3.1-8b, llama-3.1-70b), 8 samples per instance.

Writes results incrementally to pilot_results.json so a partial run is
still usable if interrupted, and prints progress to stdout.
"""
import json
import time
import sys

import spider_task as st
import soundver_experiments as se
import soundver_analysis as sv

DB_ROOT = "../spider_data/spider_data/database"
TABLES_JSON = "../spider_data/spider_data/tables.json"
N_INSTANCES = 200
N_SAMPLES = 8
MODELS = ["gpt-4o-mini", "gpt-4o", "llama-3.1-8b", "llama-3.1-70b"]
OUT_PATH = "pilot_results.json"


def run_for_model(model, seed=0):
    print(f"[{model}] loading {N_INSTANCES} instances, {N_SAMPLES} samples each...", flush=True)
    t0 = time.time()
    instances = st.load_spider_instances(
        model=model, split="dev", n_instances=N_INSTANCES, n_samples=N_SAMPLES,
        temperature=0.7, tables_json_path=TABLES_JSON, db_root=DB_ROOT, seed=seed)
    dt = time.time() - t0
    print(f"[{model}] loaded {len(instances)} instances in {dt:.0f}s", flush=True)

    base, oracle, headroom = se.run_e1(instances)
    m, lo, hi = sv.bootstrap_ci(headroom)
    e1 = {"base_accuracy": float(base.mean()), "oracle_accuracy": float(oracle.mean()),
          "headroom_mean": m, "headroom_ci_lo": lo, "headroom_ci_hi": hi, "n": len(instances)}
    print(f"[{model}] E1: base={e1['base_accuracy']:.4f} oracle={e1['oracle_accuracy']:.4f} "
          f"headroom={m:.4f} [{lo:.4f},{hi:.4f}]", flush=True)

    rates = se.run_e2(instances, ["parses", "schema_valid", "executes"])
    print(f"[{model}] E2:", flush=True)
    for name, r in rates.items():
        print(f"    {name:14s} p0={r['p0']:.3f} p={r['p']:.3f} "
              f"delta_pooled={r['delta_pooled']:.3f} eps_pooled={r['eps_pooled']:.3f} "
              f"soundness_violated={r['soundness_violated']}", flush=True)

    return {"model": model, "n_loaded": len(instances), "e1": e1, "e2": rates}


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
