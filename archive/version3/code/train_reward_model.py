#!/usr/bin/env python3
"""
train_reward_model.py -- a genuine trained SQL reward-model baseline for
tab:main's "BoN, reward model" / "+ reward model" rows.

Not a neural reward model -- a lightweight classifier (logistic regression)
over interpretable features of (question, schema, candidate SQL), trained
to predict test-suite-accuracy correctness. A real trained model, not a
zero-shot prompt or a raw model signal like log-probability.

Training data: 300 instances x 8 samples from Spider's TRAINING split
(train_spider.json), generated with GPT-4o-mini, kept strictly separate
from dev.json (used for every other measurement in this paper). Uses
this session's own checks.py (sqlglot-based, post-rewrite) rather than
version2's regex checker, since that is the checker every other number in
this paper's version3 draft is measured against.

Usage:
    python3 train_reward_model.py
"""
from __future__ import annotations
import json, os, pickle, random, re, sys

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, accuracy_score

sys.path.insert(0, os.path.dirname(__file__))
from soundver.checks import sql_extract, sql_parses, sql_schema_valid, sql_executes
from soundver.generate import _complete

DATA_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
SPIDER_TRAIN = os.path.join(os.path.normpath(DATA_ROOT), "spider_data", "spider_data", "train_spider.json")
SPIDER_TABLES = os.path.join(os.path.normpath(DATA_ROOT), "spider_data", "spider_data", "tables.json")
SPIDER_DB_ROOT = os.path.join(os.path.normpath(DATA_ROOT), "spider_data", "spider_data", "database")
sys.path.insert(0, os.path.normpath(DATA_ROOT) + "/version2")
from spider_task import test_suite_accuracy  # reused utility, not its data

MODEL = "openai/gpt-4o-mini-2024-07-18"
N_INSTANCES = 300
N_SAMPLES = 8
TRAINING_DATA_PATH = "reward_model_training_data.json"
MODEL_PATH = "reward_model.pkl"


def _load_schemas():
    with open(SPIDER_TABLES) as f:
        tables = json.load(f)
    schemas = {}
    for entry in tables:
        db_id = entry["db_id"]
        names = [t.lower() for t in entry["table_names_original"]]
        cols = {t: set() for t in names}
        for (ti, cn), _ in zip(entry["column_names_original"], entry["column_types"]):
            if ti == -1:
                continue
            cols[names[ti]].add(cn.lower())
        schemas[db_id] = cols
    return schemas


def _sql_prompt(question: str, schema: dict) -> str:
    schema_str = "\n".join(f"{t}({', '.join(sorted(cs))})" for t, cs in schema.items())
    return ("Given the database schema below, write a single SQLite query "
            "that answers the question. Output ONLY the SQL query, no "
            "explanation, no markdown fences.\n\n"
            f"Schema:\n{schema_str}\n\nQuestion: {question}\nSQL:")


def extract_features(sql: str, question: str, schema: dict) -> dict:
    """Features of a (question, schema, candidate SQL) triple. None of
    these consult the gold query or the correctness label -- exactly what
    a deployed reward model would have access to at inference time."""
    sql_lower = sql.lower()
    all_cols = set()
    for cols in schema.values():
        all_cols |= cols
    all_tables = set(schema.keys())

    tokens = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", sql_lower)
    question_tokens = set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", question.lower()))

    parses = sql_parses(sql)
    schema_valid = sql_parses(sql) and sql_schema_valid(sql, schema)

    return {
        "length_chars": len(sql),
        "length_tokens": len(tokens),
        "num_joins": sql_lower.count(" join "),
        "num_where": sql_lower.count(" where "),
        "num_group_by": sql_lower.count("group by"),
        "num_order_by": sql_lower.count("order by"),
        "num_subqueries": sql_lower.count("select") - 1,
        "has_aggregate": int(any(f in sql_lower for f in ("count(", "sum(", "avg(", "max(", "min("))),
        "has_distinct": int("distinct" in sql_lower),
        "has_limit": int(" limit " in sql_lower),
        "table_mentions": sum(1 for t in all_tables if t in sql_lower),
        "column_mentions": sum(1 for c in all_cols if c in tokens),
        "question_token_overlap": len(question_tokens & set(tokens)),
        "parses": int(parses),
        "schema_valid": int(schema_valid),
    }


def executes_feature(sql: str, conn) -> int:
    return int(sql_executes(sql, conn))


def generate_training_data():
    schemas = _load_schemas()
    with open(SPIDER_TRAIN) as f:
        ds = json.load(f)

    rng = random.Random(42)  # different seed from every dev-split run, deliberately
    idxs = list(range(len(ds)))
    rng.shuffle(idxs)
    idxs = idxs[:N_INSTANCES]

    records = []
    for n, i in enumerate(idxs):
        ex = ds[i]
        db_id = ex["db_id"]
        db_path = os.path.join(SPIDER_DB_ROOT, db_id, f"{db_id}.sqlite")
        if not os.path.exists(db_path):
            continue
        schema = schemas.get(db_id, {})
        prompt = _sql_prompt(ex["question"], schema)

        import sqlite3
        conn = sqlite3.connect(db_path, timeout=5.0)
        conn.text_factory = lambda b: b.decode("utf-8", errors="replace")
        try:
            base_text, _, _, _ = _complete(MODEL, prompt, temperature=0.0, max_tokens=256)
            base_sql = sql_extract(base_text)
            cand_sqls = [base_sql]
            for _ in range(N_SAMPLES):
                text, _, _, _ = _complete(MODEL, prompt, temperature=0.7, max_tokens=256)
                cand_sqls.append(sql_extract(text))

            for sql in cand_sqls:
                try:
                    correct = test_suite_accuracy(sql, ex["query"], db_path)
                except ValueError:
                    continue  # gold itself failed on this instance; skip, don't fabricate
                feats = extract_features(sql, ex["question"], schema)
                feats["executes"] = executes_feature(sql, conn)
                records.append({"features": feats, "correct": correct,
                                "db_id": db_id, "sql": sql})
        except Exception as e:
            print(f"skipped train instance {i} ({db_id}): {e}")
        finally:
            conn.close()

        if (n + 1) % 25 == 0:
            print(f"  {n + 1}/{len(idxs)} instances processed, "
                  f"{len(records)} labelled candidates so far", flush=True)

    with open(TRAINING_DATA_PATH, "w") as f:
        json.dump(records, f, indent=2)
    print(f"Saved {len(records)} labelled candidates to {TRAINING_DATA_PATH}")
    return records


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

    with open(MODEL_PATH, "wb") as f:
        pickle.dump({"model": clf, "feature_names": feature_names}, f)
    print(f"Saved trained model to {MODEL_PATH}")
    return clf, feature_names


def score_candidate(sql: str, question: str, schema: dict, conn, clf, feature_names) -> float:
    feats = extract_features(sql, question, schema)
    feats["executes"] = executes_feature(sql, conn)
    x = np.array([[feats[k] for k in feature_names]])
    return float(clf.predict_proba(x)[0, 1])


if __name__ == "__main__":
    if os.path.exists(TRAINING_DATA_PATH):
        print(f"Loading existing training data from {TRAINING_DATA_PATH}")
        with open(TRAINING_DATA_PATH) as f:
            records = json.load(f)
    else:
        print("Generating training data from Spider's train_spider.json...")
        records = generate_training_data()
    train(records)
