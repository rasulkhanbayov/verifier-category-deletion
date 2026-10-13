#!/usr/bin/env python3
"""Capture raw SQL text + checks + labels across all 4 models to find and
classify every correct-but-check-failed case (the delta>0 measured in the
E1/E2 pilot) as: extraction defect, normalisation defect, or a genuine gap
in the nominal-soundness argument. This is what BLOCKERS.txt's own
Experiment 2 design calls for and what the paper's Findings section
currently lacks."""
import json
import os
import random

import spider_task as st
import openrouter_client as orc

DB_ROOT = "../spider_data/spider_data/database"
TABLES_JSON = "../spider_data/spider_data/tables.json"
MODELS = ["gpt-4o-mini", "gpt-4o", "llama-3.1-8b", "llama-3.1-70b"]
N_INSTANCES = 100
N_SAMPLES = 4


def load_with_raw(model, n_instances, n_samples, temperature, seed):
    schemas = st.load_schemas(TABLES_JSON)
    with open("../spider_data/spider_data/dev.json") as f:
        ds = json.load(f)
    rng = random.Random(seed)
    idxs = list(range(len(ds)))
    rng.shuffle(idxs)
    idxs = idxs[:n_instances]

    records = []
    for i in idxs:
        ex = ds[i]
        db_id = ex["db_id"]
        db_path = os.path.join(DB_ROOT, db_id, f"{db_id}.sqlite")
        if not os.path.exists(db_path):
            continue
        schema = schemas.get(db_id, {})
        prompt = st._sql_prompt(ex["question"], schema)
        try:
            base_raw = orc.chat_completion(model, prompt, temperature=0.0, max_tokens=256)
            base_sql = st._extract_sql(base_raw)
            sample_raws = orc.sample_candidates(model, prompt, n_samples, temperature, max_tokens=256)
            sample_sqls = [st._extract_sql(r) for r in sample_raws]

            def label(pred_sql):
                try:
                    return st.test_suite_accuracy(pred_sql, ex["query"], db_path)
                except ValueError:
                    return None

            def checks(sql):
                parses = st.check_parses(sql)
                schema_valid = parses and st.check_schema_valid(sql, schema)
                executes = schema_valid and st.check_executes(sql, db_path)
                return {"parses": parses, "schema_valid": schema_valid, "executes": executes}

            records.append({
                "model": model, "db_id": db_id, "question": ex["question"], "gold": ex["query"],
                "base_raw": base_raw, "base_sql": base_sql,
                "base_correct": label(base_sql), "base_checks": checks(base_sql),
                "samples": [
                    {"raw": r, "sql": s, "correct": label(s), "checks": checks(s)}
                    for r, s in zip(sample_raws, sample_sqls)
                ],
            })
        except Exception as e:
            print(f"[{model}] skipped {db_id}: {e}")
    return records


def main():
    all_records = []
    for model in MODELS:
        print(f"[{model}] loading {N_INSTANCES} instances...", flush=True)
        records = load_with_raw(model, N_INSTANCES, N_SAMPLES, 0.7, seed=2)
        all_records.extend(records)
        print(f"[{model}] done, {len(records)} instances", flush=True)

    with open("violation_classification_data.json", "w") as f:
        json.dump(all_records, f, indent=2)

    print("\n" + "=" * 60)
    print("VIOLATIONS FOUND (correct output, at least one check failed)")
    for check_name in ("parses", "schema_valid", "executes"):
        print(f"\n--- {check_name} ---")
        for rec in all_records:
            if rec["base_correct"] and not rec["base_checks"][check_name]:
                print(f"[{rec['model']}] base ({rec['db_id']}): gold={rec['gold'][:80]}")
                print(f"  pred={rec['base_sql'][:120]}")
            for s in rec["samples"]:
                if s["correct"] and not s["checks"][check_name]:
                    print(f"[{rec['model']}] sample ({rec['db_id']}): gold={rec['gold'][:80]}")
                    print(f"  pred={s['sql'][:120]}")


if __name__ == "__main__":
    main()
