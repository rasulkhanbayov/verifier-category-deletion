#!/usr/bin/env python3
"""
train_morphology_reward_model.py
-----------------------------------
A genuine trained morphological-segmentation reward-model baseline,
mirroring train_reward_model.py's SQL design exactly: a lightweight
classifier (logistic regression) over interpretable features of
(surface word, candidate segmentation), trained to predict exact-match
correctness. Training data comes from SIGMORPHON's own TRAINING split
(eng.word.train.tsv), kept strictly separate from the test split every
morphology E1-E6 measurement in this paper evaluates on.

Usage:
    python3 train_morphology_reward_model.py   # generate data + train + save
"""
import json
import os
import pickle
import random

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, accuracy_score

import morphology_task as mt
import openrouter_client as orc

MORPH_DATA_ROOT = os.environ.get("MORPH_DATA_ROOT", "") or "../morph_data"
MODEL = "gpt-4o-mini"
N_INSTANCES = 300
N_SAMPLES = 8
TRAINING_DATA_PATH = "morphology_reward_model_training_data.json"
MODEL_PATH = "morphology_reward_model.pkl"


# ----------------------------------------------------------------------
# feature extraction -- interpretable, cheap, no leakage of the label
# ----------------------------------------------------------------------
def extract_features(morphemes: list, surface: str) -> dict:
    """Features of a (surface, candidate morpheme sequence) pair. None
    of these consult the gold segmentation or the correctness label --
    exactly what a deployed reward model would have access to at
    inference time."""
    no_empty = mt.check_no_empty_segment(morphemes)
    concatenates = no_empty and mt.check_concatenates(morphemes, surface)
    n_segments = len(morphemes)
    seg_lens = [len(m) for m in morphemes]
    reconstructed = "".join(morphemes)

    return {
        "no_empty_segment": int(no_empty),
        "concatenates": int(concatenates),
        "n_segments": n_segments,
        "surface_len_chars": len(surface),
        "mean_segment_len": (sum(seg_lens) / n_segments) if n_segments else 0.0,
        "min_segment_len": min(seg_lens) if seg_lens else 0,
        "max_segment_len": max(seg_lens) if seg_lens else 0,
        "len_ratio": (len(reconstructed) / len(surface)) if surface else 0.0,
        "has_duplicate_segment": int(len(morphemes) != len(set(morphemes))),
        "first_segment_is_surface": int(n_segments == 1 and morphemes[0] == surface),
    }


# ----------------------------------------------------------------------
# training data generation
# ----------------------------------------------------------------------
def generate_training_data():
    data_root = MORPH_DATA_ROOT
    if not data_root:
        raise RuntimeError("MORPH_DATA_ROOT must be set to generate morphology reward-model training data.")

    rows = mt._load_tsv(os.path.join(data_root, "eng.word.train.tsv"))

    rng = random.Random(42)  # different seed from the test-split E1-E6 runs, deliberately
    idxs = list(range(len(rows)))
    rng.shuffle(idxs)
    idxs = idxs[:N_INSTANCES]

    records = []
    for n, i in enumerate(idxs):
        surface, gold_morpheme_string = rows[i]
        gold_morphemes = mt._split_morphemes(gold_morpheme_string)
        prompt = mt._morphology_prompt(surface)

        try:
            base_raw = orc.chat_completion(MODEL, prompt, temperature=0.0, max_tokens=64)
            base_morphemes = mt.parse_morphemes(base_raw)
            sample_raws = orc.sample_candidates(MODEL, prompt, N_SAMPLES, 0.7, max_tokens=64)
            sample_morphemes_list = [mt.parse_morphemes(r) for r in sample_raws]

            for morphemes in [base_morphemes] + sample_morphemes_list:
                correct = mt.label_correct(morphemes, gold_morphemes)
                feats = extract_features(morphemes, surface)
                records.append({"features": feats, "correct": correct, "surface": surface})
        except Exception as e:
            print(f"skipped train instance {i} ({surface}): {e}")

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


def score_candidate(morphemes: list, surface: str, clf, feature_names) -> float:
    """Score a candidate with the trained reward model. Returns P(correct)."""
    feats = extract_features(morphemes, surface)
    x = np.array([[feats[k] for k in feature_names]])
    return float(clf.predict_proba(x)[0, 1])


if __name__ == "__main__":
    if os.path.exists(TRAINING_DATA_PATH):
        print(f"Loading existing training data from {TRAINING_DATA_PATH}")
        with open(TRAINING_DATA_PATH) as f:
            records = json.load(f)
    else:
        print("Generating training data from SIGMORPHON's eng.word.train.tsv...")
        records = generate_training_data()

    train(records)
