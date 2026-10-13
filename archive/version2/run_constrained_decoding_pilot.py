#!/usr/bin/env python3
"""
run_constrained_decoding_pilot.py
------------------------------------
Constrained-decoding baseline for text-to-SQL: generates locally with
Qwen2.5-1.5B-Instruct under a regex constraint over a no-subquery SQL
subset (see constrained_decoding_task.py's module docstring for the
coverage numbers and the honest scope limit), then scores with the same
test-suite-accuracy label used for every other Table 3 row. ONE model
only (this is a single new baseline row, not a fifth model added to
every table), same 200-instance dev-split sample as the rest of the
paper.
"""
import json
import time

import numpy as np

import constrained_decoding_task as cdt
import soundver_analysis as sv

N_INSTANCES = 200
N_SAMPLES = 8
OUT_PATH = "pilot_constrained_decoding_results.json"


def main():
    t0 = time.time()
    print(f"loading {N_INSTANCES} instances via constrained local generation "
          f"({cdt.MODEL_NAME})...", flush=True)
    instances = cdt.load_constrained_decoding_instances(
        n_instances=N_INSTANCES, n_samples=N_SAMPLES, temperature=0.7, seed=0)
    dt = time.time() - t0
    print(f"loaded {len(instances)} instances in {dt:.0f}s", flush=True)

    base_acc = np.array([float(inst.correct_base) for inst in instances])
    parses = np.array([float(inst.checks_base["parses"]) for inst in instances])
    schema_valid = np.array([float(inst.checks_base["schema_valid"]) for inst in instances])
    executes = np.array([float(inst.checks_base["executes"]) for inst in instances])

    mean, lo, hi = sv.bootstrap_ci(base_acc)

    result = {
        "model": cdt.MODEL_NAME,
        "n_loaded": len(instances),
        "n_requested": N_INSTANCES,
        "base_accuracy": float(base_acc.mean()),
        "base_accuracy_ci": {"mean": mean, "ci_lo": lo, "ci_hi": hi},
        "parses_rate": float(parses.mean()),
        "schema_valid_rate": float(schema_valid.mean()),
        "executes_rate": float(executes.mean()),
    }
    with open(OUT_PATH, "w") as f:
        json.dump(result, f, indent=2)
    print(f"base_accuracy={result['base_accuracy']:.4f} "
          f"(95% CI [{lo:.4f}, {hi:.4f}])", flush=True)
    print(f"parses={result['parses_rate']:.4f} "
          f"schema_valid={result['schema_valid_rate']:.4f} "
          f"executes={result['executes_rate']:.4f}", flush=True)
    print(f"written to {OUT_PATH}", flush=True)


if __name__ == "__main__":
    main()
