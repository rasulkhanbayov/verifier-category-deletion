#!/usr/bin/env python3
"""
train_ie_reward_model.py
---------------------------
A genuine trained IE reward-model baseline, mirroring
train_reward_model.py's SQL design exactly: a lightweight classifier
(logistic regression) over interpretable features of (text, allowed
types, candidate JSON extraction), trained to predict exact-match
correctness. Training data comes from CoNLL2003's own TRAINING split
(train.json), kept strictly separate from the test split every IE
E1-E6 measurement in this paper evaluates on.

Usage:
    python3 train_ie_reward_model.py          # generate data + train + save
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

import ie_task as it
import openrouter_client as orc

IE_DATA_ROOT = os.environ.get("IE_DATA_ROOT", "") or "../ie_data"
MODEL = "gpt-4o-mini"
N_INSTANCES = 300
N_SAMPLES = 8
TRAINING_DATA_PATH = "ie_reward_model_training_data.json"
MODEL_PATH = "ie_reward_model.pkl"


# ----------------------------------------------------------------------
# feature extraction -- interpretable, cheap, no leakage of the label
# ----------------------------------------------------------------------
def extract_features(raw: str, text: str, allowed_types: list) -> dict:
    """Features of a (text, allowed_types, candidate JSON) triple. None
    of these consult the gold entity set or the correctness label --
    exactly what a deployed reward model would have access to at
    inference time."""
    entities = it.check_parses_json(raw)
    parses = entities is not None
    required_fields = parses and it.check_required_fields(entities)
    schema_valid = required_fields and it.check_schema_valid_ie(entities, allowed_types)
    no_overlap = schema_valid and it.check_no_overlap(entities, text)
    literal_substring = parses and required_fields and it.check_literal_substring(entities, text)

    n_entities = len(entities) if parses else 0
    text_tokens = set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", text.lower()))
    entity_texts = [e.get("entity", "") for e in entities] if parses else []
    entity_types_used = set(e.get("entity_type", "") for e in entities) if parses else set()

    return {
        "parses": int(parses),
        "required_fields": int(required_fields),
        "schema_valid": int(schema_valid),
        "no_overlap": int(no_overlap),
        "literal_substring": int(literal_substring),
        "n_entities": n_entities,
        "n_entity_types_used": len(entity_types_used),
        "mean_entity_len_chars": (sum(len(e) for e in entity_texts) / n_entities) if n_entities else 0.0,
        "text_len_chars": len(text),
        "text_len_tokens": len(text_tokens),
        "entity_density": n_entities / max(1, len(text_tokens)),
        "has_duplicate_entities": int(len(entity_texts) != len(set(entity_texts))) if parses else 0,
    }


# ----------------------------------------------------------------------
# training data generation
# ----------------------------------------------------------------------
def generate_training_data():
    data_root = IE_DATA_ROOT
    if not data_root:
        raise RuntimeError("IE_DATA_ROOT must be set to generate IE reward-model training data.")

    allowed_types = it.load_schema(os.path.join(data_root, "schema.json"))
    examples = it._load_examples(os.path.join(data_root, "train.json"))

    rng = random.Random(42)  # different seed from the test-split E1-E6 runs, deliberately
    idxs = list(range(len(examples)))
    rng.shuffle(idxs)
    idxs = idxs[:N_INSTANCES]

    records = []
    for n, i in enumerate(idxs):
        ex = examples[i]
        text = ex["text"]
        gold_entities = ex["entity"]
        prompt = it._ie_prompt(text, allowed_types)

        try:
            base_raw = orc.chat_completion(MODEL, prompt, temperature=0.0, max_tokens=512)
            base_json = it._extract_json(base_raw)
            sample_raws = orc.sample_candidates(MODEL, prompt, N_SAMPLES, 0.7, max_tokens=512)
            sample_jsons = [it._extract_json(r) for r in sample_raws]

            for raw in [base_json] + sample_jsons:
                correct = it.label_correct(raw, gold_entities)
                feats = extract_features(raw, text, allowed_types)
                records.append({"features": feats, "correct": correct, "text": text})
        except Exception as e:
            print(f"skipped train instance {i}: {e}")

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


def score_candidate(raw: str, text: str, allowed_types: list, clf, feature_names) -> float:
    """Score a candidate with the trained reward model. Returns P(correct)."""
    feats = extract_features(raw, text, allowed_types)
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
