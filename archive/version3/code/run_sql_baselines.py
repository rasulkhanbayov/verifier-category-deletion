#!/usr/bin/env python3
"""
run_sql_baselines.py -- self-consistency, LLM-as-judge, and the trained
reward model as SQL scorers, both ungated best-of-N and gated behind the
sound stack, for tab:main (SQL, GPT-4o).

Mirrors E5's design (rates.degradation) but with THREE scorers instead of
one, each collected from the SAME 200-instance x 8-candidate pool per
model so the comparison is apples-to-apples within a model. A separate,
freshly-drawn sample from the one used for the ceiling/E3/E4 tables and
from E5's own confidence-scorer sample, matching this paper's own stated
practice (tab:main's notes h/i/k/m: rows come from separately-drawn
samples with their own greedy baselines).

Usage:
    python3 run_sql_baselines.py --model openai/gpt-4o-2024-11-20
"""
from __future__ import annotations
import argparse, json, os, re, sys, pickle, sqlite3, concurrent.futures

sys.path.insert(0, os.path.dirname(__file__))
from soundver.checks import sql_extract, sql_parses, sql_schema_valid, sql_executes
from soundver.generate import _load_sql_items, _sql_prompt, _complete
from soundver.rates import paired_bootstrap, permutation_test
import train_reward_model as trm

N_INSTANCES = 200
N_SAMPLES = 8
SOUND_STACK = ["parses", "schema_valid", "executes"]

_JUDGE_PROMPT = """You are judging a candidate SQL query written against the schema below. Score how likely it is to be a CORRECT answer to the question, from 0 (definitely wrong) to 100 (definitely correct). Respond with only the number, no explanation.

Schema:
{schema_str}

Question: {question}

Candidate SQL: {sql}

Score (0-100):"""


def judge_score(model, question, schema, sql):
    schema_str = "\n".join(f"{t}({', '.join(sorted(cs))})" for t, cs in schema.items())
    prompt = _JUDGE_PROMPT.format(schema_str=schema_str, question=question, sql=sql)
    try:
        raw, _, _, _ = _complete(model, prompt, temperature=0.0, max_tokens=10)
        m = re.search(r"\d+", raw)
        if not m:
            return 0.5
        return max(0, min(100, int(m.group()))) / 100.0
    except Exception:
        return 0.5


def execution_result(sql, conn):
    try:
        rows = conn.execute(sql).fetchall()
        return frozenset(tuple(r) for r in rows)
    except Exception:
        return None


def process_one(model, judge_model, item, clf, feature_names):
    prompt = _sql_prompt(item["question"], item["schema"])
    conn = sqlite3.connect(item["db_path"], timeout=5.0)
    conn.text_factory = lambda b: b.decode("utf-8", errors="replace")
    try:
        base_text, _, _, _ = _complete(model, prompt, temperature=0.0, max_tokens=256)
        base_sql = sql_extract(base_text)
        cand_texts = []
        for _ in range(N_SAMPLES):
            t, _, _, _ = _complete(model, prompt, temperature=0.7, max_tokens=256)
            cand_texts.append(sql_extract(t))

        def label(sql):
            try:
                from spider_task import test_suite_accuracy
                return test_suite_accuracy(sql, item["gold_sql"], item["db_path"])
            except ValueError:
                return False

        def checks(sql):
            p = sql_parses(sql)
            sv = p and sql_schema_valid(sql, item["schema"])
            ex = sv and sql_executes(sql, conn)
            return {"parses": p, "schema_valid": bool(sv), "executes": bool(ex)}

        base_correct = label(base_sql)
        base_checks = checks(base_sql)
        cand_correct = [label(s) for s in cand_texts]
        cand_checks = [checks(s) for s in cand_texts]

        # self-consistency: cluster by execution result over the candidate pool
        results = [execution_result(s, conn) for s in cand_texts]
        executing = [r for r in results if r is not None]
        from collections import Counter
        counts = Counter(executing)
        total = len(executing) if executing else 1
        sc_scores = [(counts[r] / total) if r is not None else 0.0 for r in results]

        # LLM-as-judge
        judge_scores = [judge_score(judge_model, item["question"], item["schema"], s)
                        for s in cand_texts]

        # trained reward model
        rm_scores = [trm.score_candidate(s, item["question"], item["schema"], conn,
                                         clf, feature_names) for s in cand_texts]

        return dict(instance_id=item["instance_id"], base_correct=base_correct,
                   base_checks=base_checks, cand_correct=cand_correct,
                   cand_checks=cand_checks, sc_scores=sc_scores,
                   judge_scores=judge_scores, rm_scores=rm_scores)
    except Exception as e:
        return dict(instance_id=item["instance_id"], error=str(e)[:200])
    finally:
        conn.close()


def _accepted(checks, stack):
    return all(checks[c] for c in stack)


def simulate(results):
    """Base, ungated-BoN, and gated rules for EACH of the three scorers."""
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
            scores = [None] + r[scores_key]  # base has no scorer score
            # ungated best-of-N over the WHOLE pool including base; base's
            # own score is -inf so it only wins via a tie-break-free max
            # when no candidate is scored higher (mirrors E5/version2: an
            # unscored base cannot be picked over a scored candidate,
            # which is what lets the scorer discard a correct base)
            pool_scores = [float("-inf")] + r[scores_key]
            best_idx = max(range(len(pool_correct)), key=lambda i: pool_scores[i])
            out[f"ungated_{name}"].append(pool_correct[best_idx])

            # gated: base if sound stack accepts it; else best-scored accepted candidate
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
    ap.add_argument("--seed", type=int, default=1)  # different seed: a separate draw
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out", default="out/sql_baselines.json")
    a = ap.parse_args()

    with open(trm.MODEL_PATH, "rb") as f:
        saved = pickle.load(f)
    clf, feature_names = saved["model"], saved["feature_names"]

    items = _load_sql_items(a.instances, a.seed)
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
