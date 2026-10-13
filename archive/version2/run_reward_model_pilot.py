#!/usr/bin/env python3
"""
run_reward_model_pilot.py
----------------------------
Apply the trained reward model (train_reward_model.py) as a scorer on
the same Spider dev-split instances used everywhere else, ungated
best-of-N and gated behind the sound stack, 200 instances x 4 models.
Training data was drawn from train_spider.json (disjoint from dev.json,
which every other SQL experiment in this paper evaluates on).
"""
import json
import pickle
import time

import numpy as np

import spider_task as st
import soundver_experiments as se
import soundver_analysis as sv
import train_reward_model as trm

DB_ROOT = "../spider_data/spider_data/database"
TABLES_JSON = "../spider_data/spider_data/tables.json"
N_INSTANCES = 200
N_SAMPLES = 8
MODELS = ["gpt-4o-mini", "gpt-4o", "llama-3.1-8b", "llama-3.1-70b"]
SOUND_STACK = ["parses", "schema_valid", "executes"]
OUT_PATH = "pilot_reward_model_results.json"


def run_for_model(model, clf, feature_names, seed=0):
    print(f"[{model}] loading {N_INSTANCES} instances...", flush=True)
    t0 = time.time()
    schemas = st.load_schemas(TABLES_JSON)
    with open("../spider_data/spider_data/dev.json") as f:
        ds = json.load(f)
    import random, os
    rng = random.Random(seed)
    idxs = list(range(len(ds)))
    rng.shuffle(idxs)
    idxs = idxs[:N_INSTANCES]

    instances, rm_scores = [], []
    for i in idxs:
        ex = ds[i]
        db_id = ex["db_id"]
        db_path = os.path.join(DB_ROOT, db_id, f"{db_id}.sqlite")
        if not os.path.exists(db_path):
            continue
        schema = schemas.get(db_id, {})
        prompt = st._sql_prompt(ex["question"], schema)
        import openrouter_client as orc
        try:
            base_raw = orc.chat_completion(model, prompt, temperature=0.0, max_tokens=256)
            base_sql = st._extract_sql(base_raw)
            sample_raws = orc.sample_candidates(model, prompt, N_SAMPLES, 0.7, max_tokens=256)
            sample_sqls = [st._extract_sql(r) for r in sample_raws]

            def label(sql):
                try:
                    return st.test_suite_accuracy(sql, ex["query"], db_path)
                except ValueError:
                    return False

            def checks(sql):
                parses = st.check_parses(sql)
                schema_valid = parses and st.check_schema_valid(sql, schema)
                executes = schema_valid and st.check_executes(sql, db_path)
                return {"parses": parses, "schema_valid": schema_valid, "executes": executes}

            instances.append(se.Instance(
                correct_base=label(base_sql),
                correct_samples=[label(s) for s in sample_sqls],
                checks_base=checks(base_sql),
                checks_samples=[checks(s) for s in sample_sqls],
                scorer_scores=None,
            ))
            rm_scores.append([
                trm.score_candidate(s, ex["question"], schema, db_path, clf, feature_names)
                for s in sample_sqls
            ])
        except Exception as e:
            print(f"skipped {db_id}: {e}")

    dt = time.time() - t0
    print(f"[{model}] loaded {len(instances)} instances in {dt:.0f}s", flush=True)

    base_acc = np.array([float(inst.correct_base) for inst in instances])

    def make_score_fn(j):
        def score_fn(inst, i):
            return rm_scores[j][i]
        return score_fn

    rm_ungated = np.array([
        float(se.rule_ungated_bestofn(inst, SOUND_STACK, N_SAMPLES, make_score_fn(j)))
        for j, inst in enumerate(instances)])
    rm_gated = np.array([
        float(se.rule_reject_gated(inst, SOUND_STACK, N_SAMPLES, make_score_fn(j)))
        for j, inst in enumerate(instances)])

    # Paired bootstrap CI on the per-instance difference from base -- see
    # run_baselines_pilot.py's diff_ci for why this was added after an
    # earlier pass reported means only and the CIs in the paper for these
    # rows were fabricated by hand.
    def diff_ci(arr):
        m, lo, hi = sv.bootstrap_ci(arr - base_acc)
        return {"mean_diff": m, "ci_lo": lo, "ci_hi": hi}

    result = {
        "model": model,
        "n_loaded": len(instances),
        "base_accuracy": float(base_acc.mean()),
        "reward_model": {
            "ungated_accuracy": float(rm_ungated.mean()),
            "gated_accuracy": float(rm_gated.mean()),
            "ungated_below_base": bool(rm_ungated.mean() < base_acc.mean() - 1e-9),
            "floor_holds_when_gated": bool(rm_gated.mean() >= base_acc.mean() - 1e-9),
            "ungated_diff_ci": diff_ci(rm_ungated),
            "gated_diff_ci": diff_ci(rm_gated),
        },
    }
    print(f"[{model}] base={result['base_accuracy']:.4f} "
          f"RM ungated={result['reward_model']['ungated_accuracy']:.4f} "
          f"gated={result['reward_model']['gated_accuracy']:.4f} "
          f"floor_holds={result['reward_model']['floor_holds_when_gated']}", flush=True)
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
