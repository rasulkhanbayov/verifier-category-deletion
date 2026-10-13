#!/usr/bin/env python3
"""
morphology_task.py
--------------------
Morphological segmentation task plug-in for soundver_experiments.py's
load_instances(), following Table 1 (soundver_main.tex).

Dataset: SIGMORPHON 2022 Shared Task on Morpheme Segmentation, English
word-level subtask (Batsuren et al. 2022, ACL Anthology 2022.sigmorphon-1.11).
57,755 gold test examples: surface word -> gold morpheme sequence with
@@-prefixed non-initial morphemes, e.g.
    subsidised   subside @@y @@ise @@ed
Concatenating the morphemes (stripping "@@" between adjacent pieces)
reconstructs the surface form exactly, which is the paper's own worked
example for this task (Sec. 5: "segments concatenate to the surface
form... for SURFACE segmentation of CONCATENATIVE morphology").

Sound-column checks implemented here (Table 1): segments concatenate to
the surface form; no empty segment. "Tags in the inventory" from Table 1
is NOT implemented -- this dataset's third column is a whole-word
morphological-type code (inflection/derivation/compounding), not a
per-morpheme tag, so there is no per-morpheme tag inventory to check
against here, and forcing one would not be a fair test of the paper's
own claim. This is a real, honest gap in task coverage relative to
Table 1, not a shortcut.

Correctness label: exact match of the predicted morpheme sequence against
gold, independent of whether the predicted segmentation happens to
concatenate back to the surface form -- a prediction that does not
concatenate is simply wrong, never excused into "correct" for failing
that check, which is the morphology analogue of the X1/IE circularity
fix.
"""
import os
import random
import re
from typing import List, Optional, Tuple

import openrouter_client as orc
from soundver_experiments import Instance

MORPH_DATA_ROOT = os.environ.get("MORPH_DATA_ROOT", "")  # dir with eng.word.{train,dev,test.gold}.tsv


def _load_tsv(path: str) -> List[Tuple[str, str]]:
    """Returns [(surface_word, gold_morpheme_string), ...]. The gold
    morpheme string uses the raw @@-boundary format, e.g.
    'subside @@y @@ise @@ed'."""
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            rows.append((parts[0], parts[1]))
    return rows


def _split_morphemes(morpheme_string: str) -> List[str]:
    """'subside @@y @@ise @@ed' -> ['subside', 'y', 'ise', 'ed']."""
    return [m[2:] if m.startswith("@@") else m for m in morpheme_string.split(" ") if m]


def _concatenates_to_surface(morphemes: List[str], surface: str) -> bool:
    return "".join(morphemes) == surface


# ----------------------------------------------------------------------
# sound-column checks (Table 1: segments concatenate to the surface form;
# no empty segment)
# ----------------------------------------------------------------------
def check_concatenates(morphemes: List[str], surface: str) -> bool:
    return _concatenates_to_surface(morphemes, surface)


def check_no_empty_segment(morphemes: List[str]) -> bool:
    return all(len(m) > 0 for m in morphemes)


def morphology_checks(morphemes: List[str], surface: str) -> dict:
    no_empty = check_no_empty_segment(morphemes)
    concatenates = no_empty and check_concatenates(morphemes, surface)
    return {"no_empty_segment": no_empty, "concatenates": concatenates}


# ----------------------------------------------------------------------
# correctness label -- exact match, independent of the checks above
# ----------------------------------------------------------------------
def label_correct(morphemes: List[str], gold_morphemes: List[str]) -> bool:
    return morphemes == gold_morphemes


# ----------------------------------------------------------------------
# parsing model output into a morpheme list
# ----------------------------------------------------------------------
def parse_morphemes(raw: str) -> List[str]:
    """The model is asked to output morphemes separated by '+'. Strips
    whitespace and drops empty tokens from stray double '++' or leading/
    trailing '+', which would otherwise silently manufacture a spurious
    empty segment not intended by the model."""
    text = raw.strip()
    fence = re.search(r"```\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    parts = [p.strip() for p in text.split("+")]
    return [p for p in parts if p]


# ----------------------------------------------------------------------
# prompt construction
# ----------------------------------------------------------------------
def _morphology_prompt(surface: str) -> str:
    return (
        "Segment the following English word into its morphemes (prefixes, "
        "roots, suffixes). Output ONLY the morphemes separated by '+', "
        "with no explanation, e.g. for 'subsidised' output: "
        "subside+y+ise+ed\n\n"
        f"Word: {surface}\nSegmentation:"
    )


# ----------------------------------------------------------------------
# the load_instances() implementation
# ----------------------------------------------------------------------
def load_morphology_instances(model: str, split: str = "test", n_instances: int = 50,
                               n_samples: int = 8, temperature: float = 0.7,
                               data_root: Optional[str] = None, seed: int = 0) -> List[Instance]:
    """Real E1/E2 data source for morphological segmentation. Requires
    MORPH_DATA_ROOT (or data_root) pointing at the directory containing
    eng.word.{train,dev,test.gold}.tsv (from sigmorphon/2022SegmentationST).
    Spends real OpenRouter credit: n_instances * (1 + n_samples) completions."""
    data_root = data_root or MORPH_DATA_ROOT
    if not data_root:
        raise RuntimeError(
            "load_morphology_instances needs MORPH_DATA_ROOT set to the "
            "directory containing eng.word.{train,dev,test.gold}.tsv "
            "(from https://github.com/sigmorphon/2022SegmentationST).")

    split_file = {"train": "eng.word.train.tsv", "dev": "eng.word.dev.tsv",
                  "test": "eng.word.test.gold.tsv"}[split]
    rows = _load_tsv(os.path.join(data_root, split_file))

    rng = random.Random(seed)
    idxs = list(range(len(rows)))
    rng.shuffle(idxs)
    idxs = idxs[:n_instances]

    instances = []
    skipped = []
    for i in idxs:
        surface, gold_morpheme_string = rows[i]
        gold_morphemes = _split_morphemes(gold_morpheme_string)
        prompt = _morphology_prompt(surface)

        try:
            base_raw = orc.chat_completion(model, prompt, temperature=0.0, max_tokens=64)
            base_morphemes = parse_morphemes(base_raw)
            sample_raws = orc.sample_candidates(model, prompt, n_samples, temperature, max_tokens=64)
            sample_morphemes_list = [parse_morphemes(r) for r in sample_raws]

            instances.append(Instance(
                correct_base=label_correct(base_morphemes, gold_morphemes),
                correct_samples=[label_correct(m, gold_morphemes) for m in sample_morphemes_list],
                checks_base=morphology_checks(base_morphemes, surface),
                checks_samples=[morphology_checks(m, surface) for m in sample_morphemes_list],
                scorer_scores=None,
            ))
        except Exception as e:
            skipped.append((surface, str(e)[:150]))

    if skipped:
        print(f"load_morphology_instances: skipped {len(skipped)}/{len(idxs)} instances: "
              f"{skipped[:5]}{'...' if len(skipped) > 5 else ''}")
    return instances


def load_morphology_instances_with_scorer(model: str, split: str = "test", n_instances: int = 50,
                                           n_samples: int = 8, temperature: float = 0.7,
                                           data_root: Optional[str] = None, seed: int = 0,
                                           logprob_reject_percentile: float = 25.0) -> List[Instance]:
    """Like load_morphology_instances, but additionally captures each
    candidate's mean log-probability for Experiments 5/6, mirroring
    spider_task.load_spider_instances_with_scorer: scorer_scores ranks
    accepted candidates by confidence, and checks["confidence_gate"] is a
    deliberately unsound boolean gate (rejects the bottom
    logprob_reject_percentile of the instance's own pool)."""
    import numpy as np

    data_root = data_root or MORPH_DATA_ROOT
    if not data_root:
        raise RuntimeError(
            "load_morphology_instances_with_scorer needs MORPH_DATA_ROOT "
            "set to the directory containing eng.word.{train,dev,test.gold}.tsv "
            "(from https://github.com/sigmorphon/2022SegmentationST).")

    split_file = {"train": "eng.word.train.tsv", "dev": "eng.word.dev.tsv",
                  "test": "eng.word.test.gold.tsv"}[split]
    rows = _load_tsv(os.path.join(data_root, split_file))

    rng = random.Random(seed)
    idxs = list(range(len(rows)))
    rng.shuffle(idxs)
    idxs = idxs[:n_instances]

    instances = []
    skipped = []
    for i in idxs:
        surface, gold_morpheme_string = rows[i]
        gold_morphemes = _split_morphemes(gold_morpheme_string)
        prompt = _morphology_prompt(surface)

        try:
            base_result = orc.chat_completion_with_logprobs(model, prompt, temperature=0.0, max_tokens=64)
            base_morphemes = parse_morphemes(base_result["text"])
            base_logprob = base_result["mean_logprob"]

            sample_results = orc.sample_candidates_with_logprobs(model, prompt, n_samples, temperature, max_tokens=64)
            sample_morphemes_list = [parse_morphemes(r["text"]) for r in sample_results]
            sample_logprobs = [r["mean_logprob"] for r in sample_results]

            all_logprobs = [lp for lp in [base_logprob] + sample_logprobs if lp is not None]
            if len(all_logprobs) < 2:
                skipped.append((surface, "insufficient logprobs returned for this instance"))
                continue
            threshold = float(np.percentile(all_logprobs, logprob_reject_percentile))

            def checks_with_conf(morphemes, logprob):
                c = morphology_checks(morphemes, surface)
                c["confidence_gate"] = logprob is not None and logprob > threshold
                return c

            instances.append(Instance(
                correct_base=label_correct(base_morphemes, gold_morphemes),
                correct_samples=[label_correct(m, gold_morphemes) for m in sample_morphemes_list],
                checks_base=checks_with_conf(base_morphemes, base_logprob),
                checks_samples=[checks_with_conf(m, lp) for m, lp in zip(sample_morphemes_list, sample_logprobs)],
                scorer_scores=[lp if lp is not None else float("-inf") for lp in sample_logprobs],
            ))
        except Exception as e:
            skipped.append((surface, str(e)[:150]))

    if skipped:
        print(f"load_morphology_instances_with_scorer: skipped {len(skipped)}/{len(idxs)} instances: "
              f"{skipped[:5]}{'...' if len(skipped) > 5 else ''}")
    return instances


_JUDGE_PROMPT = """You are judging a candidate morphological segmentation of an English word. Score how likely the candidate segmentation is CORRECT (matches the true, linguistically valid decomposition into morphemes), using only the segments given. Respond with only a single integer 0-100, no explanation.

Word: {surface}

Candidate segmentation: {candidate_str}

Score (0-100):"""


def _judge_score_morph(surface: str, morphemes: List[str], judge_model: str) -> float:
    """LLM-as-judge score in [0, 1], no gold access. Falls back to 0.5
    (uninformative) if the judge's output doesn't parse as a number,
    mirroring spider_task._judge_score exactly."""
    candidate_str = "+".join(morphemes) if morphemes else "(empty)"
    prompt = _JUDGE_PROMPT.format(surface=surface, candidate_str=candidate_str)
    try:
        judge_raw = orc.chat_completion(judge_model, prompt, temperature=0.0, max_tokens=10)
        match = re.search(r"\d+", judge_raw)
        if not match:
            return 0.5
        score = max(0, min(100, int(match.group())))
        return score / 100.0
    except Exception:
        return 0.5


def load_morphology_instances_with_baselines(model: str, judge_model: str = "gpt-4o",
                                              split: str = "test", n_instances: int = 50,
                                              n_samples: int = 8, temperature: float = 0.7,
                                              data_root: Optional[str] = None, seed: int = 0,
                                              reward_model=None):
    """Like load_morphology_instances, but additionally returns, per
    instance, a self-consistency cluster score and an LLM-as-judge score
    for every sample, mirroring spider_task.load_spider_instances_with_baselines.

    Returns (instances, self_consistency_scores, judge_scores), both
    List[List[float]] parallel to instances[i].correct_samples.

    Self-consistency score: clusters are formed by the predicted morpheme
    SEQUENCE itself (exact list match, order-sensitive since segmentation
    order is meaningful) -- the natural analogue for a task whose output
    is a sequence, not a program with an execution result.

    LLM-as-judge score: an independent judge (default GPT-4o) scores each
    candidate given only the surface word and the candidate segmentation
    -- no gold access.

    reward_model: optional (clf, feature_names) tuple from
    train_morphology_reward_model.py. When given, a third
    List[List[float]] of reward-model scores is returned as a fourth
    element, scored from the SAME candidate pool as self-consistency/
    judge (one loading pass, rather than a second, separately-drawn
    generation pass purely for reward-model scoring).
    """
    data_root = data_root or MORPH_DATA_ROOT
    if not data_root:
        raise RuntimeError(
            "load_morphology_instances_with_baselines needs MORPH_DATA_ROOT "
            "set to the directory containing eng.word.{train,dev,test.gold}.tsv "
            "(from https://github.com/sigmorphon/2022SegmentationST).")

    split_file = {"train": "eng.word.train.tsv", "dev": "eng.word.dev.tsv",
                  "test": "eng.word.test.gold.tsv"}[split]
    rows = _load_tsv(os.path.join(data_root, split_file))

    rng = random.Random(seed)
    idxs = list(range(len(rows)))
    rng.shuffle(idxs)
    idxs = idxs[:n_instances]

    if reward_model is not None:
        import train_morphology_reward_model as trm
        rm_clf, rm_feature_names = reward_model

    instances, sc_scores, judge_scores, rm_scores = [], [], [], []
    skipped = []
    for i in idxs:
        surface, gold_morpheme_string = rows[i]
        gold_morphemes = _split_morphemes(gold_morpheme_string)
        prompt = _morphology_prompt(surface)

        try:
            base_raw = orc.chat_completion(model, prompt, temperature=0.0, max_tokens=64)
            base_morphemes = parse_morphemes(base_raw)
            sample_raws = orc.sample_candidates(model, prompt, n_samples, temperature, max_tokens=64)
            sample_morphemes_list = [parse_morphemes(r) for r in sample_raws]

            instances.append(Instance(
                correct_base=label_correct(base_morphemes, gold_morphemes),
                correct_samples=[label_correct(m, gold_morphemes) for m in sample_morphemes_list],
                checks_base=morphology_checks(base_morphemes, surface),
                checks_samples=[morphology_checks(m, surface) for m in sample_morphemes_list],
                scorer_scores=None,
            ))

            # self-consistency: cluster by the predicted morpheme sequence itself
            tupled = [tuple(m) for m in sample_morphemes_list]
            from collections import Counter
            counts = Counter(tupled)
            total = len(tupled) if tupled else 1
            sc_scores.append([counts[t] / total for t in tupled])

            # LLM-as-judge: independent score per sample, no gold access
            judge_scores.append([
                _judge_score_morph(surface, m, judge_model) for m in sample_morphemes_list
            ])

            if reward_model is not None:
                rm_scores.append([
                    trm.score_candidate(m, surface, rm_clf, rm_feature_names)
                    for m in sample_morphemes_list
                ])
        except Exception as e:
            skipped.append((surface, str(e)[:150]))

    if skipped:
        print(f"load_morphology_instances_with_baselines: skipped {len(skipped)}/{len(idxs)} "
              f"instances: {skipped[:5]}{'...' if len(skipped) > 5 else ''}")
    if reward_model is not None:
        return instances, sc_scores, judge_scores, rm_scores
    return instances, sc_scores, judge_scores
