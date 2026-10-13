#!/usr/bin/env python3
"""
run_morphology_baselines_pilot.py
-------------------------------------
Self-consistency, LLM-as-judge (GPT-4o), and a trained reward model as
scorers, both ungated best-of-N and gated behind morphology's check
stack, on SIGMORPHON 2022 English test split, 200 instances x 4 base
models. Mirrors run_baselines_pilot.py's and run_reward_model_pilot.py's
SQL design, combined into one pass since all three scorers share the
same instance-loading loop.

NOTE ON THE GATE: morphology's "sound stack" (no_empty_segment +
concatenates) is measured substantially UNSOUND (delta = 0.12-0.19,
soundver_main.tex Table 2 footnote n and Sec. 5 findings). Results here
are reported for completeness, matching the same caveat already applied
to this task's E5/E6 numbers: floor_holds_when_gated is not a test of
Cor. 1 for this task, since the gate does not satisfy Cor. 1's own
soundness precondition.
"""
import json
import pickle
import time

import numpy as np

import morphology_task as mt
import soundver_experiments as se
import soundver_analysis as sv
import train_morphology_reward_model as trm

DATA_ROOT = "../morph_data"
JUDGE_MODEL = "gpt-4o"
N_INSTANCES = 200
N_SAMPLES = 8
MODELS = ["gpt-4o-mini", "gpt-4o", "llama-3.1-8b", "llama-3.1-70b"]
SOUND_STACK = ["no_empty_segment", "concatenates"]
OUT_PATH = "pilot_morphology_baselines_results.json"


def run_for_model(model, clf, feature_names, seed=0):
    print(f"[{model}] loading {N_INSTANCES} instances with self-consistency + "
          f"LLM-judge + reward-model scores...", flush=True)
    t0 = time.time()
    instances, sc_scores, judge_scores, rm_scores = mt.load_morphology_instances_with_baselines(
        model=model, judge_model=JUDGE_MODEL, split="test", n_instances=N_INSTANCES,
        n_samples=N_SAMPLES, temperature=0.7, data_root=DATA_ROOT, seed=seed,
        reward_model=(clf, feature_names))
    dt = time.time() - t0
    print(f"[{model}] loaded {len(instances)} instances in {dt:.0f}s", flush=True)

    base_acc = np.array([float(inst.correct_base) for inst in instances])

    def make_score_fn(scores_list, j):
        def score_fn(inst, i):
            return scores_list[j][i]
        return score_fn

    def scored(scores_list):
        ungated = np.array([
            float(se.rule_ungated_bestofn(inst, SOUND_STACK, N_SAMPLES, make_score_fn(scores_list, j)))
            for j, inst in enumerate(instances)])
        gated = np.array([
            float(se.rule_reject_gated(inst, SOUND_STACK, N_SAMPLES, make_score_fn(scores_list, j)))
            for j, inst in enumerate(instances)])
        return ungated, gated

    sc_ungated, sc_gated = scored(sc_scores)
    judge_ungated, judge_gated = scored(judge_scores)
    rm_ungated, rm_gated = scored(rm_scores)

    def diff_ci(arr):
        m, lo, hi = sv.bootstrap_ci(arr - base_acc)
        return {"mean_diff": m, "ci_lo": lo, "ci_hi": hi}

    def block(ungated, gated):
        return {
            "ungated_accuracy": float(ungated.mean()),
            "gated_accuracy": float(gated.mean()),
            "ungated_below_base": bool(ungated.mean() < base_acc.mean() - 1e-9),
            "floor_holds_when_gated": bool(gated.mean() >= base_acc.mean() - 1e-9),
            "ungated_diff_ci": diff_ci(ungated),
            "gated_diff_ci": diff_ci(gated),
        }

    result = {
        "model": model,
        "n_loaded": len(instances),
        "base_accuracy": float(base_acc.mean()),
        "self_consistency": block(sc_ungated, sc_gated),
        "llm_judge": block(judge_ungated, judge_gated),
        "reward_model": block(rm_ungated, rm_gated),
    }
    print(f"[{model}] base={result['base_accuracy']:.4f}", flush=True)
    for name in ("self_consistency", "llm_judge", "reward_model"):
        b = result[name]
        print(f"[{model}] {name}: ungated={b['ungated_accuracy']:.4f} "
              f"gated={b['gated_accuracy']:.4f} floor_holds={b['floor_holds_when_gated']}", flush=True)
    return result


def main():
    with open(trm.MODEL_PATH, "rb") as f:
        saved = pickle.load(f)
    clf, feature_names = saved["model"], saved["feature_names"]

    results = []
    for model in MODELS:
        try:
            result = run_for_model(model, clf, feature_names)
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
