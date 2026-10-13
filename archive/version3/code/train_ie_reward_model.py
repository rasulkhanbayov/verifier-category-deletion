#!/usr/bin/env python3
"""
train_ie_reward_model.py -- a genuine trained IE reward-model baseline
for tab:main-extra's "reward model" rows. Mirrors train_reward_model.py's
SQL design.

Training data: 300 instances x 8 samples from CoNLL2003's own TRAINING
split (train.json), kept strictly separate from the test split used for
every other IE measurement in this paper.

Usage:
    python3 train_ie_reward_model.py
"""
from __future__ import annotations
import json, os, pickle, random, sys

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, accuracy_score

sys.path.insert(0, os.path.dirname(__file__))
from soundver.checks import ie_parses, ie_required_fields, ie_schema_valid, ie_no_overlap
from soundver.generate import (_complete, _ie_prompt, _ie_extract_json,
                                _field_value_match, IE_ENTITY_TYPES, IE_SCHEMA, IE_ROOT)

MODEL = "openai/gpt-4o-mini-2024-07-18"
N_INSTANCES = 300
N_SAMPLES = 8
TRAINING_DATA_PATH = "ie_reward_model_training_data.json"
MODEL_PATH = "ie_reward_model.pkl"


def extract_features(parsed, raw: str, text: str) -> dict:
    """Features of a (text, candidate JSON) pair. None of these consult
    the gold entity set or the correctness label -- exactly what a
    deployed reward model would have access to at inference time."""
    parses = parsed is not None
    required = parses and ie_required_fields(parsed, IE_ENTITY_TYPES)
    schema_valid = required and ie_schema_valid(parsed, IE_SCHEMA)
    no_overlap = required and ie_no_overlap(parsed, text)

    n_entities = 0
    n_types_used = 0
    mean_span_len = 0.0
    has_dup = 0
    if parses and isinstance(parsed, dict):
        all_spans = []
        for t in IE_ENTITY_TYPES:
            v = parsed.get(t, [])
            v = v if isinstance(v, list) else [v]
            v = [x for x in v if isinstance(x, str)]
            if v:
                n_types_used += 1
            all_spans.extend(v)
        n_entities = len(all_spans)
        mean_span_len = (sum(len(s) for s in all_spans) / n_entities) if n_entities else 0.0
        has_dup = int(len(all_spans) != len(set(all_spans)))

    return {
        "parses": int(parses),
        "required_fields": int(required),
        "schema_valid": int(schema_valid),
        "no_overlap": int(no_overlap),
        "n_entities": n_entities,
        "n_types_used": n_types_used,
        "mean_span_len": mean_span_len,
        "has_duplicate_span": has_dup,
        "text_len_chars": len(text),
        "raw_len_chars": len(raw),
    }


def _load_train_examples():
    examples = []
    with open(os.path.join(IE_ROOT, "train.json")) as f:
        for line in f:
            line = line.strip()
            if line:
                examples.append(json.loads(line))
    return examples


def generate_training_data():
    examples = _load_train_examples()
    rng = random.Random(42)  # different seed from the test-split runs, deliberately
    idxs = list(range(len(examples)))
    rng.shuffle(idxs)
    idxs = idxs[:N_INSTANCES]

    records = []
    for n, i in enumerate(idxs):
        ex = examples[i]
        text = ex["text"]
        gold = {t: [] for t in IE_ENTITY_TYPES}
        for e in ex["entity"]:
            gold.setdefault(e["entity_type"], []).append(e["entity"])
        prompt = _ie_prompt(text)

        try:
            base_text, _, _, _ = _complete(MODEL, prompt, temperature=0.0, max_tokens=512)
            cand_raws = [base_text]
            for _ in range(N_SAMPLES):
                t, _, _, _ = _complete(MODEL, prompt, temperature=0.7, max_tokens=512)
                cand_raws.append(t)

            for raw in cand_raws:
                cleaned = _ie_extract_json(raw)
                parsed = ie_parses(cleaned)
                correct = _field_value_match(parsed if isinstance(parsed, dict) else None, gold)
                feats = extract_features(parsed, cleaned, text)
                records.append({"features": feats, "correct": correct, "text": text})
        except Exception as e:
            print(f"skipped train instance {i}: {e}")

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


def score_candidate(raw: str, text: str, clf, feature_names) -> float:
    cleaned = _ie_extract_json(raw)
    parsed = ie_parses(cleaned)
    feats = extract_features(parsed, cleaned, text)
    x = np.array([[feats[k] for k in feature_names]])
    return float(clf.predict_proba(x)[0, 1])


if __name__ == "__main__":
    if os.path.exists(TRAINING_DATA_PATH):
        print(f"Loading existing training data from {TRAINING_DATA_PATH}")
        with open(TRAINING_DATA_PATH) as f:
            records = json.load(f)
    else:
        print("Generating training data from CoNLL2003's train.json...")
        records = generate_training_data()
    train(records)
