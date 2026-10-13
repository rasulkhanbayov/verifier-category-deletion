#!/usr/bin/env python3
"""
ie_task.py
-----------
Schema-constrained information extraction task plug-in for
soundver_experiments.py's load_instances(), following Table 1
(soundver_main.tex) and the same X1-style circularity discipline as
spider_task.py.

Dataset: CoNLL2003 NER via the zjunlp/iepile (ACL 2024) release, a
standard, widely-cited NER benchmark with a clean flat schema
({location, organization, person, else}) and exact entity spans with
character positions. Not sourced from a community mirror -- iepile is
the paper's own official HF release.

Sound-column checks implemented here (Table 1): parses as JSON; validates
against schema; required fields present; no schema-forbidden overlap.
NOT sound (scorer-only): every span is a literal substring -- included
here for comparison since CoNLL2003 is purely extractive, so this check
is EXPECTED to behave soundly on this task, which is itself a finding
worth reporting (Table 1's own scope condition on this check).

Correctness label: exact match of the predicted (entity_type, normalised
span) set against gold, evaluated independently of whether the output
parsed as valid JSON -- a prediction that fails to parse is simply scored
as an empty extraction set, never as "correct because unparseable", which
is what avoids circularity here (the IE analogue of the X1 SQL fix).
"""
import json
import os
import random
import re
from pathlib import Path
from typing import List, Optional

import openrouter_client as orc
from soundver_experiments import Instance

IE_DATA_ROOT = os.environ.get("IE_DATA_ROOT", "")  # directory with train.json/dev.json/test.json/schema.json


def load_schema(schema_path: str) -> List[str]:
    """CoNLL2003's schema.json is JSONL; the first line is the flat list
    of allowed entity types, e.g. ['location', 'else', 'organization', 'person']."""
    with open(schema_path) as f:
        first_line = f.readline()
    return json.loads(first_line)


def _load_examples(split_path: str) -> List[dict]:
    with open(split_path) as f:
        return [json.loads(l) for l in f if l.strip()]


# ----------------------------------------------------------------------
# sound-column checks (Table 1: parses as JSON; validates against schema;
# required fields present; no schema-forbidden overlap)
# ----------------------------------------------------------------------
def check_parses_json(raw: str) -> Optional[list]:
    """Returns the parsed list of entity dicts, or None if it doesn't
    parse as a JSON list. Kept separate from a bool so downstream checks
    don't have to re-parse."""
    try:
        parsed = json.loads(raw)
    except Exception:
        return None
    return parsed if isinstance(parsed, list) else None


def check_required_fields(entities: list) -> bool:
    """Every extracted entity object has both 'entity' and 'entity_type'."""
    return all(isinstance(e, dict) and "entity" in e and "entity_type" in e for e in entities)


def check_schema_valid_ie(entities: list, allowed_types: List[str]) -> bool:
    """Every entity_type is one of the allowed schema types. Assumes
    check_required_fields already passed (a missing entity_type field
    is a required-fields violation, not a schema-validity one)."""
    return all(e["entity_type"] in allowed_types for e in entities)


def check_no_overlap(entities: list, text: str) -> bool:
    """No two extracted spans overlap in position. Positions are
    recomputed from the entity text via the first case-sensitive match in
    `text`, since a model is not asked to output character offsets
    (Sec. 5's extraction-leak discussion: asking for raw offsets invites
    a different, off-by-one class of error that has nothing to do with
    schema soundness). An entity whose text cannot be found in `text` at
    all contributes no interval and cannot overlap anything; that failure
    is what the NOT-sound "literal substring" check below is for."""
    spans = []
    for e in entities:
        span = _find_span(e.get("entity", ""), text)
        if span is not None:
            spans.append(span)
    spans.sort()
    for (s1, e1), (s2, e2) in zip(spans, spans[1:]):
        if s2 < e1:
            return False
    return True


def _find_span(entity_text: str, text: str):
    if not entity_text:
        return None
    idx = text.find(entity_text)
    if idx == -1:
        return None
    return (idx, idx + len(entity_text))


# ----------------------------------------------------------------------
# NOT-sound check (Table 1, right column): every span is a literal
# substring. Included for comparison, not for the gate.
# ----------------------------------------------------------------------
def check_literal_substring(entities: list, text: str) -> bool:
    return all(_find_span(e.get("entity", ""), text) is not None for e in entities)


def ie_checks(raw: str, text: str, allowed_types: List[str]) -> dict:
    entities = check_parses_json(raw)
    parses = entities is not None
    required_fields = parses and check_required_fields(entities)
    schema_valid = required_fields and check_schema_valid_ie(entities, allowed_types)
    no_overlap = schema_valid and check_no_overlap(entities, text)
    literal_substring = parses and required_fields and check_literal_substring(entities, text)
    return {
        "parses": parses,
        "required_fields": required_fields,
        "schema_valid": schema_valid,
        "no_overlap": no_overlap,
        "literal_substring": literal_substring,  # NOT sound; scorer-only per Table 1
    }


# ----------------------------------------------------------------------
# correctness label -- exact match, no circularity with any check above
# ----------------------------------------------------------------------
def _normalise_entity_set(entities: list) -> set:
    out = set()
    for e in entities:
        if isinstance(e, dict) and "entity" in e and "entity_type" in e:
            out.add((e["entity_type"].strip().lower(), e["entity"].strip().lower()))
    return out


def label_correct(raw: str, gold_entities: list) -> bool:
    """Exact set match of (entity_type, normalised text) pairs. A
    prediction that fails to parse as JSON contributes an empty set and
    is therefore always wrong unless gold is also empty -- it is never
    scored as correct merely because it didn't parse, which is what
    breaks any circularity with the parses/schema_valid checks above."""
    predicted = check_parses_json(raw)
    predicted_set = _normalise_entity_set(predicted) if predicted is not None else set()
    gold_set = _normalise_entity_set(gold_entities)
    return predicted_set == gold_set


# ----------------------------------------------------------------------
# prompt construction
# ----------------------------------------------------------------------
def _ie_prompt(text: str, allowed_types: List[str]) -> str:
    types_str = ", ".join(allowed_types)
    return (
        "Extract all named entities from the text below. Allowed entity "
        f"types: {types_str}.\n"
        'Output ONLY a JSON list of objects, each with fields "entity" '
        '(the exact substring from the text) and "entity_type" (one of '
        "the allowed types). If there are no entities, output an empty "
        "list. No explanation, no markdown fences.\n\n"
        f"Text: {text}\nJSON:"
    )


def _extract_json(raw: str) -> str:
    """Strip markdown fences the model may add despite instructions."""
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    return text


# ----------------------------------------------------------------------
# the load_instances() implementation
# ----------------------------------------------------------------------
def load_ie_instances(model: str, split: str = "test", n_instances: int = 50,
                       n_samples: int = 8, temperature: float = 0.7,
                       data_root: Optional[str] = None, seed: int = 0) -> List[Instance]:
    """Real E1/E2 data source for schema-constrained IE. Requires
    IE_DATA_ROOT (or data_root) pointing at the directory containing
    CoNLL2003's train.json/dev.json/test.json/schema.json (from
    zjunlp/iepile). Spends real OpenRouter credit: n_instances *
    (1 + n_samples) completions."""
    data_root = data_root or IE_DATA_ROOT
    if not data_root:
        raise RuntimeError(
            "load_ie_instances needs IE_DATA_ROOT set to the directory "
            "containing CoNLL2003's train/dev/test/schema json files "
            "(from zjunlp/iepile, IE-en/NER/CoNLL2003/).")

    allowed_types = load_schema(os.path.join(data_root, "schema.json"))
    split_file = {"train": "train.json", "dev": "dev.json", "test": "test.json"}[split]
    examples = _load_examples(os.path.join(data_root, split_file))

    rng = random.Random(seed)
    idxs = list(range(len(examples)))
    rng.shuffle(idxs)
    idxs = idxs[:n_instances]

    instances = []
    skipped = []
    for i in idxs:
        ex = examples[i]
        text = ex["text"]
        gold_entities = ex["entity"]
        prompt = _ie_prompt(text, allowed_types)

        try:
            base_raw = orc.chat_completion(model, prompt, temperature=0.0, max_tokens=512)
            base_json = _extract_json(base_raw)
            sample_raws = orc.sample_candidates(model, prompt, n_samples, temperature, max_tokens=512)
            sample_jsons = [_extract_json(r) for r in sample_raws]

            instances.append(Instance(
                correct_base=label_correct(base_json, gold_entities),
                correct_samples=[label_correct(s, gold_entities) for s in sample_jsons],
                checks_base=ie_checks(base_json, text, allowed_types),
                checks_samples=[ie_checks(s, text, allowed_types) for s in sample_jsons],
                scorer_scores=None,
            ))
        except Exception as e:
            skipped.append((i, str(e)[:150]))

    if skipped:
        print(f"load_ie_instances: skipped {len(skipped)}/{len(idxs)} instances: "
              f"{skipped[:5]}{'...' if len(skipped) > 5 else ''}")
    return instances


def load_ie_instances_with_scorer(model: str, split: str = "test", n_instances: int = 50,
                                   n_samples: int = 8, temperature: float = 0.7,
                                   data_root: Optional[str] = None, seed: int = 0,
                                   logprob_reject_percentile: float = 25.0) -> List[Instance]:
    """Like load_ie_instances, but additionally captures each candidate's
    mean log-probability for Experiments 5/6, mirroring
    spider_task.load_spider_instances_with_scorer exactly: scorer_scores
    ranks accepted candidates by confidence, and checks["confidence_gate"]
    is a deliberately unsound boolean gate (rejects the bottom
    logprob_reject_percentile of the instance's own pool), giving it a
    real measured delta > 0 for Cor. 3/Cor. 1 to be tested against.
    """
    import numpy as np

    data_root = data_root or IE_DATA_ROOT
    if not data_root:
        raise RuntimeError(
            "load_ie_instances_with_scorer needs IE_DATA_ROOT set to the "
            "directory containing CoNLL2003's train/dev/test/schema json "
            "files (from zjunlp/iepile, IE-en/NER/CoNLL2003/).")

    allowed_types = load_schema(os.path.join(data_root, "schema.json"))
    split_file = {"train": "train.json", "dev": "dev.json", "test": "test.json"}[split]
    examples = _load_examples(os.path.join(data_root, split_file))

    rng = random.Random(seed)
    idxs = list(range(len(examples)))
    rng.shuffle(idxs)
    idxs = idxs[:n_instances]

    instances = []
    skipped = []
    for i in idxs:
        ex = examples[i]
        text = ex["text"]
        gold_entities = ex["entity"]
        prompt = _ie_prompt(text, allowed_types)

        try:
            base_result = orc.chat_completion_with_logprobs(model, prompt, temperature=0.0, max_tokens=512)
            base_json = _extract_json(base_result["text"])
            base_logprob = base_result["mean_logprob"]

            sample_results = orc.sample_candidates_with_logprobs(model, prompt, n_samples, temperature, max_tokens=512)
            sample_jsons = [_extract_json(r["text"]) for r in sample_results]
            sample_logprobs = [r["mean_logprob"] for r in sample_results]

            all_logprobs = [lp for lp in [base_logprob] + sample_logprobs if lp is not None]
            if len(all_logprobs) < 2:
                skipped.append((i, "insufficient logprobs returned for this instance"))
                continue
            threshold = float(np.percentile(all_logprobs, logprob_reject_percentile))

            def checks_with_conf(raw, logprob):
                c = ie_checks(raw, text, allowed_types)
                c["confidence_gate"] = logprob is not None and logprob > threshold
                return c

            instances.append(Instance(
                correct_base=label_correct(base_json, gold_entities),
                correct_samples=[label_correct(s, gold_entities) for s in sample_jsons],
                checks_base=checks_with_conf(base_json, base_logprob),
                checks_samples=[checks_with_conf(s, lp) for s, lp in zip(sample_jsons, sample_logprobs)],
                scorer_scores=[lp if lp is not None else float("-inf") for lp in sample_logprobs],
            ))
        except Exception as e:
            skipped.append((i, str(e)[:150]))

    if skipped:
        print(f"load_ie_instances_with_scorer: skipped {len(skipped)}/{len(idxs)} instances: "
              f"{skipped[:5]}{'...' if len(skipped) > 5 else ''}")
    return instances


_JUDGE_PROMPT = """You are judging a candidate named-entity extraction. Score how likely the candidate is a CORRECT and COMPLETE extraction of every named entity in the text, using only the allowed types. Respond with only a single integer 0-100, no explanation.

Allowed entity types: {types_str}

Text: {text}

Candidate JSON: {raw}

Score (0-100):"""


def _judge_score_ie(text: str, allowed_types: List[str], raw: str, judge_model: str) -> float:
    """LLM-as-judge score in [0, 1], no gold access. Falls back to 0.5
    (uninformative) if the judge's output doesn't parse as a number,
    mirroring spider_task._judge_score exactly."""
    types_str = ", ".join(allowed_types)
    prompt = _JUDGE_PROMPT.format(types_str=types_str, text=text, raw=raw)
    try:
        judge_raw = orc.chat_completion(judge_model, prompt, temperature=0.0, max_tokens=10)
        match = re.search(r"\d+", judge_raw)
        if not match:
            return 0.5
        score = max(0, min(100, int(match.group())))
        return score / 100.0
    except Exception:
        return 0.5


def load_ie_instances_with_baselines(model: str, judge_model: str = "gpt-4o",
                                      split: str = "test", n_instances: int = 50,
                                      n_samples: int = 8, temperature: float = 0.7,
                                      data_root: Optional[str] = None, seed: int = 0,
                                      reward_model=None):
    """Like load_ie_instances, but additionally returns, per instance, a
    self-consistency cluster score and an LLM-as-judge score for every
    sample, mirroring spider_task.load_spider_instances_with_baselines.

    Returns (instances, self_consistency_scores, judge_scores), both
    List[List[float]] parallel to instances[i].correct_samples.

    Self-consistency score: since IE has no execution semantics, clusters
    are formed by the predicted (entity_type, normalised span) SET itself
    (exact match) rather than an execution result -- the natural IE
    analogue of "same answer" for a task whose output is a set, not a
    program. A candidate that fails to parse as JSON contributes an empty
    set to its own cluster (empty extractions can legitimately cluster
    with each other) but never with a non-empty set.

    LLM-as-judge score: an independent judge (default GPT-4o) scores each
    candidate given only the text and allowed types -- no gold access.

    reward_model: optional (clf, feature_names) tuple from
    train_ie_reward_model.py. When given, a third List[List[float]] of
    reward-model scores is returned as a fourth element, scored from the
    SAME candidate pool as self-consistency/judge (one loading pass,
    rather than a second, separately-drawn generation pass purely for
    reward-model scoring).
    """
    data_root = data_root or IE_DATA_ROOT
    if not data_root:
        raise RuntimeError(
            "load_ie_instances_with_baselines needs IE_DATA_ROOT set to the "
            "directory containing CoNLL2003's train/dev/test/schema json "
            "files (from zjunlp/iepile, IE-en/NER/CoNLL2003/).")

    allowed_types = load_schema(os.path.join(data_root, "schema.json"))
    split_file = {"train": "train.json", "dev": "dev.json", "test": "test.json"}[split]
    examples = _load_examples(os.path.join(data_root, split_file))

    rng = random.Random(seed)
    idxs = list(range(len(examples)))
    rng.shuffle(idxs)
    idxs = idxs[:n_instances]

    if reward_model is not None:
        import train_ie_reward_model as trm
        rm_clf, rm_feature_names = reward_model

    instances, sc_scores, judge_scores, rm_scores = [], [], [], []
    skipped = []
    for i in idxs:
        ex = examples[i]
        text = ex["text"]
        gold_entities = ex["entity"]
        prompt = _ie_prompt(text, allowed_types)

        try:
            base_raw = orc.chat_completion(model, prompt, temperature=0.0, max_tokens=512)
            base_json = _extract_json(base_raw)
            sample_raws = orc.sample_candidates(model, prompt, n_samples, temperature, max_tokens=512)
            sample_jsons = [_extract_json(r) for r in sample_raws]

            instances.append(Instance(
                correct_base=label_correct(base_json, gold_entities),
                correct_samples=[label_correct(s, gold_entities) for s in sample_jsons],
                checks_base=ie_checks(base_json, text, allowed_types),
                checks_samples=[ie_checks(s, text, allowed_types) for s in sample_jsons],
                scorer_scores=None,
            ))

            # self-consistency: cluster by the predicted entity set itself
            parsed = [check_parses_json(s) for s in sample_jsons]
            entity_sets = [_normalise_entity_set(p) if p is not None else frozenset() for p in parsed]
            frozen = [frozenset(s) for s in entity_sets]
            from collections import Counter
            counts = Counter(frozen)
            total = len(frozen) if frozen else 1
            sc_scores.append([counts[s] / total for s in frozen])

            # LLM-as-judge: independent score per sample, no gold access
            judge_scores.append([
                _judge_score_ie(text, allowed_types, s, judge_model) for s in sample_jsons
            ])

            if reward_model is not None:
                rm_scores.append([
                    trm.score_candidate(s, text, allowed_types, rm_clf, rm_feature_names)
                    for s in sample_jsons
                ])
        except Exception as e:
            skipped.append((i, str(e)[:150]))

    if skipped:
        print(f"load_ie_instances_with_baselines: skipped {len(skipped)}/{len(idxs)} "
              f"instances: {skipped[:5]}{'...' if len(skipped) > 5 else ''}")
    if reward_model is not None:
        return instances, sc_scores, judge_scores, rm_scores
    return instances, sc_scores, judge_scores
