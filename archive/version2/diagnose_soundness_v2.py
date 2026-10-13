#!/usr/bin/env python3
"""Third-pass diagnostic: find remaining correct-but-check-failed cases
after the alias fix and the quoted-literal fix, across a fresh sample."""
import json
import os
import random

import spider_task as st
import openrouter_client as orc

DB_ROOT = "../spider_data/spider_data/database"
TABLES_JSON = "../spider_data/spider_data/tables.json"


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
            "db_id": db_id, "question": ex["question"], "gold": ex["query"],
            "base_raw": base_raw, "base_sql": base_sql,
            "base_correct": label(base_sql), "base_checks": checks(base_sql),
            "samples": [
                {"raw": r, "sql": s, "correct": label(s), "checks": checks(s)}
                for r, s in zip(sample_raws, sample_sqls)
            ],
        })
    return records


if __name__ == "__main__":
    records = load_with_raw("gpt-4o-mini", n_instances=60, n_samples=2, temperature=0.7, seed=7)
    with open("soundness_diagnosis_v2.json", "w") as f:
        json.dump(records, f, indent=2)

    for check_name in ("parses", "schema_valid", "executes"):
        violations = []
        for rec in records:
            if rec["base_correct"] and not rec["base_checks"][check_name]:
                violations.append(("base", rec["db_id"], rec["gold"], rec["base_sql"]))
            for s in rec["samples"]:
                if s["correct"] and not s["checks"][check_name]:
                    violations.append(("sample", rec["db_id"], rec["gold"], s["sql"]))
        print(f"{check_name}: {len(violations)} violations out of {len(records)*3} outputs")
        for kind, db_id, gold, sql in violations[:5]:
            print(f"  --- {kind} ({db_id}) ---")
            print("  gold:", gold)
            print("  pred:", sql)
