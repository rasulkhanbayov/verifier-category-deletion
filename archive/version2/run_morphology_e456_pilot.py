#!/usr/bin/env python3
"""
run_morphology_e456_pilot.py
--------------------------------
Experiments 4, 5, and 6 on morphological segmentation / SIGMORPHON 2022
English test split, 200 instances x 4 models, N=8. Mirrors
run_e456_pilot.py's structure exactly.

E4 stacking order: no_empty_segment -> +concatenates (only 2 checks --
this is a much shorter stack than SQL/IE, per Table 1's morphology row).
"""
import json
import time

import morphology_task as mt
import soundver_experiments as se

DATA_ROOT = "../morph_data"
N_INSTANCES = 200
N_SAMPLES = 8
MODELS = ["gpt-4o-mini", "gpt-4o", "llama-3.1-8b", "llama-3.1-70b"]
ORDERED_CHECKS = ["no_empty_segment", "concatenates"]
SOUND_STACK = ["no_empty_segment", "concatenates"]
UNSOUND_SCORER = "confidence_gate"
OUT_PATH = "pilot_morphology_e456_results.json"


def run_for_model(model, seed=0):
    print(f"[{model}] loading {N_INSTANCES} instances, {N_SAMPLES} samples each "
          f"(with logprob scorer)...", flush=True)
    t0 = time.time()
    instances = mt.load_morphology_instances_with_scorer(
        model=model, split="test", n_instances=N_INSTANCES, n_samples=N_SAMPLES,
        temperature=0.7, data_root=DATA_ROOT, seed=seed)
    dt = time.time() - t0
    print(f"[{model}] loaded {len(instances)} instances in {dt:.0f}s", flush=True)

    for inst in instances:
        inst.checks_base["always_true"] = True
        for s in inst.checks_samples:
            s["always_true"] = True

    print(f"[{model}] E4 (stacking)...", flush=True)
    e4 = se.run_e4(instances, ORDERED_CHECKS, N=N_SAMPLES)
    for row in e4["rows"]:
        print(f"    stack={row['stack']}  eps={row['eps']:.4f}  delta={row['delta']:.4f}  "
              f"accuracy={row['accuracy']:.4f}", flush=True)
    print(f"    eps_non_increasing={e4['eps_non_increasing']}  "
          f"gain_non_decreasing={e4['gain_non_decreasing']}", flush=True)

    print(f"[{model}] E5 (degradation and safe composition)...", flush=True)
    e5 = se.run_e5(instances, SOUND_STACK, UNSOUND_SCORER, N=N_SAMPLES)
    for k, v in e5.items():
        print(f"    {k}: {v}", flush=True)

    print(f"[{model}] E6a (vacuous check negative control)...", flush=True)
    e6a = se.run_e6_vacuous_check(instances, "always_true", N=N_SAMPLES)
    for k, v in e6a.items():
        print(f"    {k}: {v}", flush=True)

    print(f"[{model}] E6b (inflated-delta scorer negative control)...", flush=True)
    e6b = se.run_e6_inflated_delta(instances, SOUND_STACK, UNSOUND_SCORER, N=N_SAMPLES)
    for k, v in e6b.items():
        print(f"    {k}: {v}", flush=True)

    return {"model": model, "n_loaded": len(instances), "e4": e4, "e5": e5,
            "e6a": e6a, "e6b": e6b}


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
