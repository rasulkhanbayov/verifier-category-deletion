#!/usr/bin/env python3
"""
run_e456_pilot.py
-------------------
Experiments 4, 5, and 6 on text-to-SQL / Spider dev split, 200 instances
x 4 models, N=8. Uses load_spider_instances_with_scorer (captures mean
log-probability per candidate + a deliberately unsound "confidence_gate"
check) so all three experiments run from ONE instance-loading pass:

  E4  Stacking: parses -> +schema_valid -> +executes, eps non-increasing?
  E5  Degradation: does confidence_gate degrade ungated best-of-N below
      greedy (Cor. 3), and does gating it behind the sound stack restore
      the floor (Cor. 1)?
  E6a Negative control: a vacuous check ("parses" restricted to always-True
      would not be genuine; instead we use a literal always-true check).
  E6b Negative control: confidence_gate as the inflated-delta scorer,
      gated behind the sound stack (same mechanics as E5, Sec. 6's E6).
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
SOUND_STACK = ["parses", "schema_valid", "executes"]
UNSOUND_SCORER = "confidence_gate"
OUT_PATH = "pilot_e456_results.json"


def run_for_model(model, seed=0):
    print(f"[{model}] loading {N_INSTANCES} instances, {N_SAMPLES} samples each "
          f"(with logprob scorer)...", flush=True)
    t0 = time.time()
    instances = st.load_spider_instances_with_scorer(
        model=model, split="dev", n_instances=N_INSTANCES, n_samples=N_SAMPLES,
        temperature=0.7, tables_json_path=TABLES_JSON, db_root=DB_ROOT, seed=seed)
    dt = time.time() - t0
    print(f"[{model}] loaded {len(instances)} instances in {dt:.0f}s", flush=True)

    # add a literal always-true check for E6a's genuine vacuous-check test
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
