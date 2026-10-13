#!/usr/bin/env python3
"""
run_ie_baselines.py -- self-consistency, LLM-as-judge, and the trained
reward model as IE scorers, both ungated best-of-N and gated behind the
sound stack, for tab:main-extra (IE, GPT-4o).

Mirrors run_sql_baselines.py exactly, adapted for IE: self-consistency
clusters by the predicted ENTITY SET (exact match of the four-field
dict's normalised values) rather than an execution result, since IE has
no execution semantics.

Usage:
    python3 run_ie_baselines.py --model openai/gpt-4o-2024-11-20
"""
from __future__ import annotations
import argparse, json, os, re, sys, pickle, concurrent.futures
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))
from soundver.checks import ie_parses, ie_required_fields, ie_schema_valid, ie_no_overlap
from soundver.generate import (_load_ie_items, _ie_prompt, _ie_extract_json,
                                _field_value_match, _complete,
                                IE_ENTITY_TYPES, IE_SCHEMA)
from soundver.rates import paired_bootstrap
import train_ie_reward_model as trm

N_INSTANCES = 200
N_SAMPLES = 8
SOUND_STACK = ["parses", "required_fields", "schema_valid", "no_overlap"]

_JUDGE_PROMPT = """You are judging a candidate named-entity extraction. Score how likely the candidate is a CORRECT and COMPLETE extraction of every named entity in the text, using only the allowed types. Respond with only a single integer 0-100, no explanation.

Allowed entity types: location, else (other named entities), organization, person

Text: {text}

Candidate JSON: {raw}

Score (0-100):"""


def judge_score(model, text, raw):
    prompt = _JUDGE_PROMPT.format(text=text, raw=raw)
    try:
        judge_raw, _, _, _ = _complete(model, prompt, temperature=0.0, max_tokens=10)
        m = re.search(r"\d+", judge_raw)
        if not m:
            return 0.5
        return max(0, min(100, int(m.group()))) / 100.0
    except Exception:
        return 0.5


def _entity_set(parsed):
    if not isinstance(parsed, dict):
        return frozenset()
    out = set()
    for t in IE_ENTITY_TYPES:
        v = parsed.get(t, [])
        v = v if isinstance(v, list) else [v]
        for x in v:
            if isinstance(x, str):
                out.add((t, x.strip().lower()))
    return frozenset(out)


def process_one(model, judge_model, item, clf, feature_names):
    prompt = _ie_prompt(item["text"])
    try:
        base_text, _, _, _ = _complete(model, prompt, temperature=0.0, max_tokens=512)
        cand_texts = []
        for _ in range(N_SAMPLES):
            t, _, _, _ = _complete(model, prompt, temperature=0.7, max_tokens=512)
            cand_texts.append(t)

        def label(raw):
            cleaned = _ie_extract_json(raw)
            parsed = ie_parses(cleaned)
            return _field_value_match(parsed if isinstance(parsed, dict) else None, item["gold"])

        def checks(raw):
            cleaned = _ie_extract_json(raw)
            parsed = ie_parses(cleaned)
            p = parsed is not None
            rf = p and ie_required_fields(parsed, IE_ENTITY_TYPES)
            sv = rf and ie_schema_valid(parsed, IE_SCHEMA)
            no = rf and ie_no_overlap(parsed, item["text"])
            return {"parses": p, "required_fields": bool(rf),
                   "schema_valid": bool(sv), "no_overlap": bool(no)}

        base_correct = label(base_text)
        base_checks = checks(base_text)
        cand_correct = [label(s) for s in cand_texts]
        cand_checks = [checks(s) for s in cand_texts]

        # self-consistency: cluster by the predicted ENTITY SET
        parsed_sets = [_entity_set(ie_parses(_ie_extract_json(s))) for s in cand_texts]
        counts = Counter(parsed_sets)
        total = len(parsed_sets) if parsed_sets else 1
        sc_scores = [counts[s] / total for s in parsed_sets]

        judge_scores = [judge_score(judge_model, item["text"], s) for s in cand_texts]

        rm_scores = [trm.score_candidate(s, item["text"], clf, feature_names)
                    for s in cand_texts]

        return dict(instance_id=item["instance_id"], base_correct=base_correct,
                   base_checks=base_checks, cand_correct=cand_correct,
                   cand_checks=cand_checks, sc_scores=sc_scores,
                   judge_scores=judge_scores, rm_scores=rm_scores)
    except Exception as e:
        return dict(instance_id=item["instance_id"], error=str(e)[:200])


def _accepted(checks, stack):
    return all(checks[c] for c in stack)


def simulate(results):
    out = {"base": []}
    for name in ("sc", "judge", "rm"):
        out[f"ungated_{name}"] = []
        out[f"gated_{name}"] = []

    for r in results:
        out["base"].append(r["base_correct"])
        pool_correct = [r["base_correct"]] + r["cand_correct"]
        pool_checks = [r["base_checks"]] + r["cand_checks"]

        for name, scores_key in (("sc", "sc_scores"), ("judge", "judge_scores"),
                                 ("rm", "rm_scores")):
            pool_scores = [float("-inf")] + r[scores_key]
            best_idx = max(range(len(pool_correct)), key=lambda i: pool_scores[i])
            out[f"ungated_{name}"].append(pool_correct[best_idx])

            if _accepted(r["base_checks"], SOUND_STACK):
                out[f"gated_{name}"].append(r["base_correct"])
            else:
                accepted_idxs = [i for i, c in enumerate(r["cand_checks"])
                                if _accepted(c, SOUND_STACK)]
                if accepted_idxs:
                    best = max(accepted_idxs, key=lambda i: r[scores_key][i])
                    out[f"gated_{name}"].append(r["cand_correct"][best])
                else:
                    out[f"gated_{name}"].append(r["base_correct"])

    import numpy as np
    return {k: np.array(v, dtype=float) for k, v in out.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="openai/gpt-4o-2024-11-20")
    ap.add_argument("--judge-model", default="openai/gpt-4o-2024-11-20")
    ap.add_argument("--instances", type=int, default=N_INSTANCES)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out", default="out/ie_baselines.json")
    a = ap.parse_args()

    with open(trm.MODEL_PATH, "rb") as f:
        saved = pickle.load(f)
    clf, feature_names = saved["model"], saved["feature_names"]

    items = _load_ie_items(a.instances, a.seed)
    print(f"{len(items)} instances, model={a.model}, judge={a.judge_model}", flush=True)

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
        futs = [pool.submit(process_one, a.model, a.judge_model, it, clf, feature_names)
               for it in items]
        for i, fut in enumerate(concurrent.futures.as_completed(futs)):
            results.append(fut.result())
            if (i + 1) % 25 == 0:
                print(f"  {i + 1}/{len(items)}", flush=True)

    errors = [r for r in results if "error" in r]
    ok = [r for r in results if "error" not in r]
    print(f"{len(errors)} errored, {len(ok)} scored", flush=True)

    sim = simulate(ok)
    base_acc = sim["base"].mean()
    print(f"\ngreedy baseline: {base_acc*100:.1f}%")

    payload = {"model": a.model, "judge_model": a.judge_model, "n": len(ok),
              "base_pct": float(base_acc * 100)}
    for name in ("sc", "judge", "rm"):
        ungated = sim[f"ungated_{name}"]
        gated = sim[f"gated_{name}"]
        m_u, lo_u, hi_u = paired_bootstrap(ungated, sim["base"])
        m_g, lo_g, hi_g = paired_bootstrap(gated, sim["base"])
        print(f"{name:8s} ungated={ungated.mean()*100:5.1f}% D={m_u:+.2f} "
              f"[{lo_u:+.2f},{hi_u:+.2f}]   gated={gated.mean()*100:5.1f}% "
              f"D={m_g:+.2f} [{lo_g:+.2f},{hi_g:+.2f}]")
        payload[name] = dict(ungated_pct=float(ungated.mean()*100),
                            gated_pct=float(gated.mean()*100),
                            ungated_diff_ci=[m_u, lo_u, hi_u],
                            gated_diff_ci=[m_g, lo_g, hi_g],
                            ungated_floor_holds=bool(ungated.mean() >= sim["base"].mean() - 1e-9),
                            gated_floor_holds=bool(gated.mean() >= sim["base"].mean() - 1e-9))

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
