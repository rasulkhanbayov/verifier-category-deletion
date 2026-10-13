#!/usr/bin/env python3
"""
run_morphology_e3_pilot.py
------------------------------
Experiment 3 (predicted vs observed gain) and Experiment 3b (is it the
gate?) on morphological segmentation / SIGMORPHON 2022 English test
split, 200 instances x 4 models. Mirrors run_e3_pilot.py's structure
exactly.

The sound stack used is the full conjunction from Table 1:
no_empty_segment + concatenates.
"""
import json
import time

import morphology_task as mt
import soundver_experiments as se
import soundver_analysis as sv

DATA_ROOT = "../morph_data"
N_INSTANCES = 200
N_SAMPLES = 32
MODELS = ["gpt-4o-mini", "gpt-4o", "llama-3.1-8b", "llama-3.1-70b"]
STACK = ["no_empty_segment", "concatenates"]
BUDGETS = (1, 2, 4, 8, 16, 32)
OUT_PATH = "pilot_morphology_e3_results.json"


def run_for_model(model, seed=0):
    print(f"[{model}] loading {N_INSTANCES} instances, {N_SAMPLES} samples each...", flush=True)
    t0 = time.time()
    instances = mt.load_morphology_instances(
        model=model, split="test", n_instances=N_INSTANCES, n_samples=N_SAMPLES,
        temperature=0.7, data_root=DATA_ROOT, seed=seed)
    dt = time.time() - t0
    print(f"[{model}] loaded {len(instances)} instances in {dt:.0f}s", flush=True)

    print(f"[{model}] running E3 (predicted vs observed gain)...", flush=True)
    e3 = se.run_e3(instances, STACK, budgets=BUDGETS)
    print(f"[{model}] E3 rates: p0={e3['rates']['p0']:.3f} p={e3['rates']['p']:.3f} "
          f"eps={e3['rates']['eps_pooled']:.3f} delta={e3['rates']['delta_pooled']:.3f}", flush=True)
    for N in BUDGETS:
        pred = e3["predicted"][N]
        obs_m, obs_lo, obs_hi = e3["observed"][N]
        print(f"    N={N:3d}  predicted={pred:.4f}  observed={obs_m:.4f} [{obs_lo:.4f},{obs_hi:.4f}]",
              flush=True)

    print(f"[{model}] running E3b (is it the gate?)...", flush=True)
    e3b = se.run_e3b(instances, STACK, N=16)
    for k, v in e3b.items():
        if isinstance(v, tuple):
            print(f"    {k:24s}: mean={v[0]:.4f} CI=[{v[1]:.4f},{v[2]:.4f}]", flush=True)
        else:
            print(f"    {k:24s}: {v:.4f}", flush=True)

    return {
        "model": model, "n_loaded": len(instances),
        "e3": {
            "rates": e3["rates"],
            "predicted": {str(k): v for k, v in e3["predicted"].items()},
            "observed": {str(k): list(v) for k, v in e3["observed"].items()},
        },
        "e3b": e3b,
    }


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
