#!/usr/bin/env python3
"""
run_baselines_pilot.py
------------------------
Self-consistency (execution-clustered) and LLM-as-judge (GPT-4o) as
scorers, both ungated best-of-N and gated behind the sound stack, on
text-to-SQL / Spider dev split, 200 instances x 4 base models.
Completes Table 3's originally-listed baselines that were deferred:
self-consistency and LLM-as-judge (a trained reward-model scorer is
handled separately in train_reward_model.py / run_reward_model_pilot.py).
"""
import json
import time

import numpy as np

import spider_task as st
import soundver_experiments as se
import soundver_analysis as sv

DB_ROOT = "../spider_data/spider_data/database"
TABLES_JSON = "../spider_data/spider_data/tables.json"
JUDGE_MODEL = "gpt-4o"
N_INSTANCES = 200
N_SAMPLES = 8
MODELS = ["gpt-4o-mini", "gpt-4o", "llama-3.1-8b", "llama-3.1-70b"]
SOUND_STACK = ["parses", "schema_valid", "executes"]
OUT_PATH = "pilot_baselines_results.json"


def run_for_model(model, seed=0):
    print(f"[{model}] loading {N_INSTANCES} instances with self-consistency + "
          f"LLM-judge scores...", flush=True)
    t0 = time.time()
    instances, sc_scores, judge_scores = st.load_spider_instances_with_baselines(
        model=model, judge_model=JUDGE_MODEL, split="dev", n_instances=N_INSTANCES,
        n_samples=N_SAMPLES, temperature=0.7, tables_json_path=TABLES_JSON,
        db_root=DB_ROOT, seed=seed)
    dt = time.time() - t0
    print(f"[{model}] loaded {len(instances)} instances in {dt:.0f}s", flush=True)

    base_acc = np.array([float(inst.correct_base) for inst in instances])

    def make_score_fn(scores_list, j):
        # closes over the CURRENT j, not looked up by identity/equality --
        # Instance is a plain @dataclass with value-based __eq__, so
        # instances.index(inst) would silently return the wrong index for
        # any two instances that happen to compare equal (e.g. same
        # booleans/checks by coincidence at this sample size).
        def score_fn(inst, i):
            return scores_list[j][i]
        return score_fn

    # self-consistency: ungated best-of-N, and gated behind the sound stack
    sc_ungated = np.array([
        float(se.rule_ungated_bestofn(inst, SOUND_STACK, N_SAMPLES, make_score_fn(sc_scores, j)))
        for j, inst in enumerate(instances)])
    sc_gated = np.array([
        float(se.rule_reject_gated(inst, SOUND_STACK, N_SAMPLES, make_score_fn(sc_scores, j)))
        for j, inst in enumerate(instances)])

    # LLM-as-judge: ungated best-of-N, and gated behind the sound stack
    judge_ungated = np.array([
        float(se.rule_ungated_bestofn(inst, SOUND_STACK, N_SAMPLES, make_score_fn(judge_scores, j)))
        for j, inst in enumerate(instances)])
    judge_gated = np.array([
        float(se.rule_reject_gated(inst, SOUND_STACK, N_SAMPLES, make_score_fn(judge_scores, j)))
        for j, inst in enumerate(instances)])

    # Paired bootstrap CI on the per-instance DIFFERENCE from base, matching
    # Table 3's "Delta vs. greedy (pts, 95% CI)" column and the CI
    # convention used everywhere else in the paper (sv.bootstrap_ci). An
    # earlier version of this script reported only means and the CIs
    # written into the paper for these rows were fabricated by hand to
    # look plausible -- this computes them for real from the per-instance
    # arrays already available in this function.
    def diff_ci(arr):
        m, lo, hi = sv.bootstrap_ci(arr - base_acc)
        return {"mean_diff": m, "ci_lo": lo, "ci_hi": hi}

    result = {
        "model": model,
        "n_loaded": len(instances),
        "base_accuracy": float(base_acc.mean()),
        "self_consistency": {
            "ungated_accuracy": float(sc_ungated.mean()),
            "gated_accuracy": float(sc_gated.mean()),
            "ungated_below_base": bool(sc_ungated.mean() < base_acc.mean() - 1e-9),
            "floor_holds_when_gated": bool(sc_gated.mean() >= base_acc.mean() - 1e-9),
            "ungated_diff_ci": diff_ci(sc_ungated),
            "gated_diff_ci": diff_ci(sc_gated),
        },
        "llm_judge": {
            "ungated_accuracy": float(judge_ungated.mean()),
            "gated_accuracy": float(judge_gated.mean()),
            "ungated_below_base": bool(judge_ungated.mean() < base_acc.mean() - 1e-9),
            "floor_holds_when_gated": bool(judge_gated.mean() >= base_acc.mean() - 1e-9),
            "ungated_diff_ci": diff_ci(judge_ungated),
            "gated_diff_ci": diff_ci(judge_gated),
        },
    }
    print(f"[{model}] base={result['base_accuracy']:.4f}", flush=True)
    print(f"[{model}] self-consistency: ungated={result['self_consistency']['ungated_accuracy']:.4f} "
          f"gated={result['self_consistency']['gated_accuracy']:.4f} "
          f"floor_holds={result['self_consistency']['floor_holds_when_gated']}", flush=True)
    print(f"[{model}] LLM-judge: ungated={result['llm_judge']['ungated_accuracy']:.4f} "
          f"gated={result['llm_judge']['gated_accuracy']:.4f} "
          f"floor_holds={result['llm_judge']['floor_holds_when_gated']}", flush=True)
    return result


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
