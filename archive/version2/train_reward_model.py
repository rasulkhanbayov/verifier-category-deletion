#!/usr/bin/env python3
"""
train_reward_model.py
-----------------------
A genuine trained SQL reward-model baseline, matching the paper's own
description of GradeSQL-style "outcome reward models trained from
execution-labelled candidates" (Sec. 2, tab:main caption).

Not a neural reward model -- a lightweight classifier (logistic
regression / gradient boosting) over interpretable features of
(question, schema, candidate SQL), trained to predict test-suite-accuracy
correctness. Small, reproducible, fast, and a REAL trained model, not a
zero-shot prompt or a raw model signal like log-probability.

Training data: 300 instances x 8 samples from train_spider.json (the
official Spider TRAINING split), generated with GPT-4o-mini, kept
strictly separate from dev.json which every E1-E6 measurement in this
paper uses for evaluation. No leakage between train and test.

Usage:
    python3 train_reward_model.py          # generate data + train + save
"""
import json
import os
import pickle
import random
import re

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, accuracy_score

import spider_task as st
import openrouter_client as orc

DB_ROOT = "../spider_data/spider_data/database"
TABLES_JSON = "../spider_data/spider_data/tables.json"
MODEL = "gpt-4o-mini"
N_INSTANCES = 300
N_SAMPLES = 8
TRAINING_DATA_PATH = "reward_model_training_data.json"
MODEL_PATH = "reward_model.pkl"


# ----------------------------------------------------------------------
# feature extraction -- interpretable, cheap, no leakage of the label
# ----------------------------------------------------------------------
def extract_features(sql: str, question: str, schema: dict) -> dict:
    """Features of a (question, schema, candidate SQL) triple. None of
    these consult the gold query or the correctness label -- they are
    exactly what a deployed reward model would have access to at
    inference time."""
    sql_lower = sql.lower()
    all_cols = set()
    for cols in schema.values():
        all_cols |= cols
    all_tables = set(schema.keys())

    tokens = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", sql_lower)
    question_tokens = set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", question.lower()))

    return {
        "length_chars": len(sql),
        "length_tokens": len(tokens),
        "num_joins": sql_lower.count(" join "),
        "num_where": sql_lower.count(" where "),
        "num_group_by": sql_lower.count("group by"),
        "num_order_by": sql_lower.count("order by"),
        "num_subqueries": sql_lower.count("select") - 1,  # nested SELECTs beyond the outer one
        "has_aggregate": int(any(f in sql_lower for f in ("count(", "sum(", "avg(", "max(", "min("))),
        "has_distinct": int("distinct" in sql_lower),
        "has_limit": int(" limit " in sql_lower),
        "table_mentions": sum(1 for t in all_tables if t in sql_lower),
        "column_mentions": sum(1 for c in all_cols if c in tokens),
        "question_token_overlap": len(question_tokens & set(tokens)),
        "parses": int(st.check_parses(sql)),
        "schema_valid": int(st.check_schema_valid(sql, schema)) if st.check_parses(sql) else 0,
    }


def executes_feature(sql: str, db_path: str) -> int:
    return int(st.check_executes(sql, db_path))


# ----------------------------------------------------------------------
# training data generation
# ----------------------------------------------------------------------
def generate_training_data():
    schemas = st.load_schemas(TABLES_JSON)
    with open("../spider_data/spider_data/train_spider.json") as f:
        ds = json.load(f)

    rng = random.Random(42)  # different seed from all dev-split runs, deliberately
    idxs = list(range(len(ds)))
    rng.shuffle(idxs)
    idxs = idxs[:N_INSTANCES]

    records = []
    for n, i in enumerate(idxs):
        ex = ds[i]
        db_id = ex["db_id"]
        db_path = os.path.join(DB_ROOT, db_id, f"{db_id}.sqlite")
        if not os.path.exists(db_path):
            continue
        schema = schemas.get(db_id, {})
        prompt = st._sql_prompt(ex["question"], schema)

        try:
            base_raw = orc.chat_completion(MODEL, prompt, temperature=0.0, max_tokens=256)
            base_sql = st._extract_sql(base_raw)
            sample_raws = orc.sample_candidates(MODEL, prompt, N_SAMPLES, 0.7, max_tokens=256)
            sample_sqls = [st._extract_sql(r) for r in sample_raws]

            for sql in [base_sql] + sample_sqls:
                try:
                    correct = st.test_suite_accuracy(sql, ex["query"], db_path)
                except ValueError:
                    continue  # gold itself failed on this instance; skip, don't fabricate a label
                feats = extract_features(sql, ex["question"], schema)
                feats["executes"] = executes_feature(sql, db_path)
                records.append({"features": feats, "correct": correct,
                                 "db_id": db_id, "sql": sql})
        except Exception as e:
            print(f"skipped train instance {i} ({db_id}): {e}")

        if (n + 1) % 25 == 0:
            print(f"  {n + 1}/{len(idxs)} instances processed, {len(records)} labelled candidates so far",
                  flush=True)

    with open(TRAINING_DATA_PATH, "w") as f:
        json.dump(records, f, indent=2)
    print(f"Saved {len(records)} labelled candidates to {TRAINING_DATA_PATH}")
    return records


# ----------------------------------------------------------------------
# training
# ----------------------------------------------------------------------
def train(records):
    feature_names = sorted(records[0]["features"].keys())
    X = np.array([[r["features"][k] for k in feature_names] for r in records])
    y = np.array([int(r["correct"]) for r in records])

    print(f"Training set: {len(y)} candidates, {y.mean():.3f} positive rate")

    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y)

    clf = LogisticRegression(max_iter=2000, class_weight="balanced")
    clf.fit(X_train, y_train)

    val_pred = clf.predict(X_val)
    val_proba = clf.predict_proba(X_val)[:, 1]
    print(f"Validation accuracy: {accuracy_score(y_val, val_pred):.3f}")
    print(f"Validation AUROC: {roc_auc_score(y_val, val_proba):.3f}")

    print("\nFeature weights (standardised by feature std):")
    stds = X_train.std(axis=0)
    for name, coef, std in sorted(zip(feature_names, clf.coef_[0], stds),
                                   key=lambda t: -abs(t[1] * t[2])):
        print(f"  {name:24s} {coef * std:+.4f}")

    with open(MODEL_PATH, "wb") as f:
        pickle.dump({"model": clf, "feature_names": feature_names}, f)
    print(f"\nSaved trained model to {MODEL_PATH}")
    return clf, feature_names


def score_candidate(sql: str, question: str, schema: dict, db_path: str, clf, feature_names) -> float:
    """Score a candidate with the trained reward model. Returns P(correct)."""
    feats = extract_features(sql, question, schema)
    feats["executes"] = executes_feature(sql, db_path)
    x = np.array([[feats[k] for k in feature_names]])
    return float(clf.predict_proba(x)[0, 1])


if __name__ == "__main__":
    if os.path.exists(TRAINING_DATA_PATH):
        print(f"Loading existing training data from {TRAINING_DATA_PATH}")
        with open(TRAINING_DATA_PATH) as f:
            records = json.load(f)
    else:
        print("Generating training data from train_spider.json...")
        records = generate_training_data()

    train(records)
