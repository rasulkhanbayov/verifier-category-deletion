"""
spider_task.py
----------------
Text-to-SQL task plug-in for soundver_experiments.py's load_instances(),
following Table 1 (soundver_main.tex) and BLOCKERS.txt R6/R7/X1.

Sound-column checks implemented here: parses, schema-valid, executes.
"full sound stack" in Table 2 is the conjunction of all three.

Correctness label: TEST-SUITE ACCURACY (Zhong, Yu & Klein, EMNLP 2020),
not raw execution match. BLOCKERS.txt X1: execution match marks a query
that fails to run as incorrect, which makes the "executes" check's delta
zero BY CONSTRUCTION rather than by measurement -- circular for exactly
the check this paper leans on hardest. Test-suite accuracy instead
executes both the predicted and gold query against several DISTILLED
(perturbed) copies of the database and compares result sets, so a query
that fails to run is simply wrong on every distillation, and a query that
runs but returns the wrong rows is caught too -- neither is definitionally
tied to "executes" succeeding.

DATABASE FILES: this module requires the official Spider database.zip
(Yale LILY lab), unzipped so that `db_root/<db_id>/<db_id>.sqlite` exists
for every db_id in the loaded split. Point SPIDER_DB_ROOT at that
directory before calling load_spider_instances(). No community mirror is
used here per the explicit decision to source only the official release.
"""

import os
import re
import sqlite3
import random
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import sqlglot
from sqlglot import exp

import openrouter_client as orc
from soundver_experiments import Instance

SPIDER_DB_ROOT = os.environ.get("SPIDER_DB_ROOT", "")  # set once you have the official unzip


# ----------------------------------------------------------------------
# sound-column checks (Table 1: parses; schema-valid; executes)
# ----------------------------------------------------------------------
_QUERY_TYPES = (exp.Select, exp.Union, exp.Intersect, exp.Except)


def check_parses(sql: str) -> bool:
    """Nominally sound: a gold query parses by definition of the task.

    sqlglot's default error level is lenient: input with no SELECT
    keyword at all, e.g. 'SELEKT * FRM singer', is silently reinterpreted
    as an arithmetic expression with aliases rather than rejected, so a
    bare parse_one() call without error_level=RAISE is not a real
    well-formedness check. RAISE closes that gap: malformed tokens raise.

    The remaining gap, found as a concrete correct-but-check-failed case
    in the pilot's soundness measurement: sqlglot represents a query built
    from set operations (INTERSECT/UNION/EXCEPT, all common and legal in
    Spider gold queries) as an exp.Intersect/exp.Union/exp.Except node,
    NOT an exp.Select node, even though each branch is itself a SELECT.
    An isinstance(parsed, exp.Select) check rejects these outright, so
    every correct query using a set operation was measured as a parses
    violation -- not a real extraction or normalisation defect, but a
    check that didn't recognise legal SQL syntax it was never scoped to
    exclude. Checking against the tuple of query-producing node types
    fixes it without weakening the rejection of genuinely malformed input
    (an arithmetic-expression misparse of garbage tokens is none of these
    four types either).
    """
    from sqlglot.errors import ErrorLevel
    try:
        parsed = sqlglot.parse_one(sql, read="sqlite", error_level=ErrorLevel.RAISE)
        return isinstance(parsed, _QUERY_TYPES)
    except Exception:
        return False


def check_schema_valid(sql: str, schema: dict) -> bool:
    """Nominally sound: a gold query references only existing tables and
    columns. schema = {table_name: set(column_names)}, lowercased.

    Two known leaks fixed here, both found as concrete correct-but-
    check-failed cases in the pilot's soundness measurement:

    1. A reference to a SELECT-clause output alias (e.g. `ORDER BY
       num_departures` where `num_departures` is `COUNT(...) AS
       num_departures` earlier in the same query) is valid SQL -- SQLite
       resolves it against the alias, not the schema (flight_2).
    2. SQLite resolves a double-quoted token against the schema first and
       falls back to a string literal only if no column matches (a
       documented SQLite compatibility misfeature); sqlglot's sqlite
       dialect always parses a double-quoted token as an
       identifier/Column node regardless of whether it matches anything,
       so `WHERE airportname = "Alton"` produces a phantom Column named
       "Alton". A first attempt filtered these by requiring the name to
       look like a multi-word/punctuated string, which caught
       "The Rise of the Blue Beetle!" but missed single-word literals
       like "Alton", "Brazil", "CD" -- exactly the common case, since most
       WHERE-clause string literals in Spider queries ARE single words.
       The correct fix uses what sqlglot already records: whether the
       token was double-quoted in the source
       (`column.this.quoted`). A double-quoted token that does not match
       any real column is a misparsed literal by SQLite's own resolution
       rule, independent of how many words it contains; a bare
       (non-quoted) column that doesn't match the schema is a genuine
       schema violation.
    """
    try:
        parsed = sqlglot.parse_one(sql, read="sqlite")
    except Exception:
        return False
    if parsed is None:
        return False
    tables = {t.name.lower() for t in parsed.find_all(exp.Table)}
    if not tables.issubset(schema.keys()):
        return False
    all_cols = set().union(*schema.values()) if schema else set()
    aliases = {a.alias.lower() for a in parsed.find_all(exp.Alias) if a.alias}
    for col in parsed.find_all(exp.Column):
        name = col.name.lower()
        if name == "*" or name in aliases:
            continue
        if name not in all_cols:
            if getattr(col.this, "quoted", False):
                continue  # double-quoted token with no schema match: a string literal, per SQLite's own rule
            return False
    return True


def _connect(db_path: str, timeout: float = 5.0) -> sqlite3.Connection:
    """sqlite3.connect with a lenient text_factory. At least one official
    Spider database (wta_1/players.last_name) contains non-UTF-8 bytes in a
    TEXT column, which crashes the default strict UTF-8 decoder on ANY
    SELECT * over that table -- this is a data-quality property of the
    upstream benchmark, not a query correctness issue, so we decode with
    errors='replace' rather than let one bad row make every check_executes/
    test_suite_accuracy call against that database silently return False."""
    conn = sqlite3.connect(db_path, timeout=timeout)
    conn.text_factory = lambda b: b.decode("utf-8", errors="replace")
    return conn


def check_executes(sql: str, db_path: str, timeout_s: float = 5.0) -> bool:
    """Nominally sound only up to the X1 circularity warning -- this
    checks that the query RUNS, not that it is correct. Used as one
    conjunct of the sound stack, never as the correctness label itself."""
    try:
        conn = _connect(db_path, timeout_s)
        conn.execute(sql)
        conn.close()
        return True
    except Exception:
        return False


def execution_result(sql: str, db_path: str, timeout_s: float = 5.0):
    """The query's result set on the ORIGINAL database (not a distilled
    copy), as a hashable frozenset of row tuples, or None if it fails to
    execute. Used for execution-clustered self-consistency (BLOCKERS.txt
    X6: string-level voting over SQL text is a straw man for this task;
    the standard is clustering by execution result)."""
    try:
        conn = _connect(db_path, timeout_s)
        rows = conn.execute(sql).fetchall()
        conn.close()
        return frozenset(tuple(r) for r in rows)
    except Exception:
        return None


# ----------------------------------------------------------------------
# test-suite accuracy (Zhong et al. 2020), simplified
# ----------------------------------------------------------------------
def _row_set(rows) -> frozenset:
    return frozenset(tuple(r) for r in rows)


def _make_distilled_copy(src_db_path: str, dst_db_path: str, seed: int,
                          keep_fraction: float = 0.7) -> None:
    """A crude distillation: copy the schema, then keep only a random
    subset of rows per table. This perturbs the data (not the schema) so
    two queries with the same result SET on the perturbed rows are more
    likely to be truly equivalent, and a query that happens to match gold
    only on the original untouched rows is exposed. A full test-suite
    implementation additionally perturbs values within-domain; this is a
    minimal version and should be upgraded before results are reported
    (see BLOCKERS.txt-equivalent note in soundver_experiments.py)."""
    src = _connect(src_db_path)
    if os.path.exists(dst_db_path):
        os.remove(dst_db_path)
    dst = _connect(dst_db_path)
    rng = random.Random(seed)

    schema_rows = src.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL "
        "AND name != 'sqlite_sequence'").fetchall()
    for name, create_sql in schema_rows:
        dst.execute(create_sql)
    dst.commit()

    for name, _ in schema_rows:
        cols = [r[1] for r in src.execute(f"PRAGMA table_info({name})")]
        rows = src.execute(f"SELECT * FROM {name}").fetchall()
        keep = [r for r in rows if rng.random() < keep_fraction]
        if keep:
            placeholders = ",".join(["?"] * len(cols))
            dst.executemany(f"INSERT INTO {name} VALUES ({placeholders})", keep)
    dst.commit()
    src.close()
    dst.close()


def test_suite_accuracy(pred_sql: str, gold_sql: str, db_path: str,
                         n_distillations: int = 3, cache_dir: str = "/tmp/soundver_distilled") -> bool:
    """True iff pred_sql's result set matches gold_sql's on every
    distilled copy. A pred_sql that fails to execute on any copy is
    simply wrong there, exactly like a pred_sql with the wrong rows --
    no special-casing of 'does it run', which is what breaks the
    circularity in X1."""
    os.makedirs(cache_dir, exist_ok=True)
    db_id = Path(db_path).stem
    for seed in range(n_distillations):
        dpath = os.path.join(cache_dir, f"{db_id}_{seed}.sqlite")
        if not os.path.exists(dpath):
            _make_distilled_copy(db_path, dpath, seed=seed)
        conn = _connect(dpath, timeout=5.0)
        try:
            gold_rows = _row_set(conn.execute(gold_sql).fetchall())
        except Exception:
            conn.close()
            raise ValueError(f"gold query failed to execute on distillation: {gold_sql}")
        try:
            pred_rows = _row_set(conn.execute(pred_sql).fetchall())
        except Exception:
            conn.close()
            return False
        conn.close()
        if pred_rows != gold_rows:
            return False
    return True


# ----------------------------------------------------------------------
# schema loading (from Spider's tables.json, not the .sqlite files)
# ----------------------------------------------------------------------
def load_schemas(tables_json_path: str) -> dict:
    """{db_id: {table_name_lower: set(column_name_lower)}} from Spider's
    tables.json, which ships in the official database.zip alongside the
    per-db sqlite files."""
    import json
    with open(tables_json_path) as f:
        tables = json.load(f)
    out = {}
    for entry in tables:
        db_id = entry["db_id"]
        table_names = [t.lower() for t in entry["table_names_original"]]
        cols = {t: set() for t in table_names}
        for (tbl_idx, col_name), _ in zip(entry["column_names_original"], entry["column_types"]):
            if tbl_idx == -1:
                continue
            cols[table_names[tbl_idx]].add(col_name.lower())
        out[db_id] = cols
    return out


# ----------------------------------------------------------------------
# prompt construction
# ----------------------------------------------------------------------
def _sql_prompt(question: str, schema: dict) -> str:
    schema_str = "\n".join(f"{t}({', '.join(sorted(cs))})" for t, cs in schema.items())
    return (
        "Given the database schema below, write a single SQLite query that "
        "answers the question. Output ONLY the SQL query, no explanation, "
        "no markdown fences.\n\n"
        f"Schema:\n{schema_str}\n\nQuestion: {question}\nSQL:"
    )


def _extract_sql(raw: str) -> str:
    """Strip markdown fences and leading/trailing prose the model may add
    despite the instruction not to -- this IS the extraction step
    Sec. 5 warns is the largest source of realised-soundness leaks."""
    text = raw.strip()
    fence = re.search(r"```(?:sql)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    text = text.rstrip(";").strip()
    return text


# ----------------------------------------------------------------------
# the load_instances() implementation
# ----------------------------------------------------------------------
def load_spider_instances(model: str, split: str = "dev", n_instances: int = 50,
                           n_samples: int = 8, temperature: float = 0.7,
                           tables_json_path: Optional[str] = None,
                           db_root: Optional[str] = None, seed: int = 0) -> List[Instance]:
    """Real E1/E2 data source for text-to-SQL. Requires SPIDER_DB_ROOT (or
    db_root) pointing at the official, unzipped Spider database.zip's
    `database/` directory, and tables_json_path pointing at its
    tables.json. Reads dev.json/train_spider.json directly from the same
    bundle rather than the HF hub mirror, since the official zip already
    has matching gold SQL and this avoids any train/dev split drift
    between sources. Spends real OpenRouter credit: n_instances *
    (1 + n_samples) completions.

    split: "dev" or "train" -- reads <bundle_root>/dev.json or
    <bundle_root>/train_spider.json, where <bundle_root> is tables_json_path's
    parent directory.
    """
    import json

    db_root = db_root or SPIDER_DB_ROOT
    if not db_root or not tables_json_path:
        raise RuntimeError(
            "load_spider_instances needs the official Spider database.zip. "
            "Set SPIDER_DB_ROOT (or pass db_root=) to the unzipped "
            "database/ directory and pass tables_json_path=.../tables.json. "
            "Not sourcing this from a community mirror, per the explicit "
            "provenance decision.")

    schemas = load_schemas(tables_json_path)
    bundle_root = Path(tables_json_path).parent
    split_file = bundle_root / ("dev.json" if split == "dev" else "train_spider.json")
    with open(split_file) as f:
        ds = json.load(f)

    rng = random.Random(seed)
    idxs = list(range(len(ds)))
    rng.shuffle(idxs)
    idxs = idxs[:n_instances]

    instances = []
    skipped = []
    for i in idxs:
        ex = ds[i]
        db_id = ex["db_id"]
        db_path = os.path.join(db_root, db_id, f"{db_id}.sqlite")
        if not os.path.exists(db_path):
            continue  # skip instances whose db wasn't in the provided bundle
        schema = schemas.get(db_id, {})
        prompt = _sql_prompt(ex["question"], schema)

        # Generation calls are real spend, already committed once made --
        # isolate everything AFTER them per-instance so a database-side
        # bug (e.g. a reserved table name, a bad encoding) can't discard
        # already-paid-for completions from every other instance in the
        # batch. A prior run lost ~200 instances' worth of generations
        # this way when one database (out of 166) raised past the single
        # ValueError this used to catch.
        try:
            base_raw = orc.chat_completion(model, prompt, temperature=0.0, max_tokens=256)
            base_sql = _extract_sql(base_raw)
            sample_raws = orc.sample_candidates(model, prompt, n_samples, temperature, max_tokens=256)
            sample_sqls = [_extract_sql(r) for r in sample_raws]

            def label(pred_sql):
                try:
                    return test_suite_accuracy(pred_sql, ex["query"], db_path)
                except ValueError:
                    return False  # gold itself failed; exclude by treating as unusable, not fabricated-correct

            def checks(sql):
                parses = check_parses(sql)
                schema_valid = parses and check_schema_valid(sql, schema)
                executes = schema_valid and check_executes(sql, db_path)
                return {"parses": parses, "schema_valid": schema_valid, "executes": executes}

            instances.append(Instance(
                correct_base=label(base_sql),
                correct_samples=[label(s) for s in sample_sqls],
                checks_base=checks(base_sql),
                checks_samples=[checks(s) for s in sample_sqls],
                scorer_scores=None,
            ))
        except Exception as e:
            skipped.append((db_id, str(e)[:150]))

    if skipped:
        print(f"load_spider_instances: skipped {len(skipped)}/{len(idxs)} instances "
              f"due to per-instance errors (generations for these were still paid "
              f"for): {skipped[:5]}{'...' if len(skipped) > 5 else ''}")
    return instances


def load_spider_instances_with_scorer(model: str, split: str = "dev", n_instances: int = 50,
                                       n_samples: int = 8, temperature: float = 0.7,
                                       tables_json_path: Optional[str] = None,
                                       db_root: Optional[str] = None, seed: int = 0,
                                       logprob_reject_percentile: float = 25.0) -> List[Instance]:
    """Like load_spider_instances, but additionally captures each
    candidate's mean log-probability (via
    orc.chat_completion_with_logprobs) for Experiments 5/6, which need a
    genuinely UNSOUND scorer -- one with delta > 0, i.e. one that can
    reject a correct output.

    Two things this adds, both requested in BLOCKERS.txt's own Sec. 6
    baseline list ("reject the highest-log-probability candidate"):

    1. scorer_scores = per-candidate mean log-probability, used by
       rule_ungated_bestofn / rule_reject_gated's score_fn to RANK
       accepted candidates (higher logprob = more confident = ranked
       higher, which is the deliberately naive, unsound heuristic).
    2. checks["confidence_gate"] = a boolean gate, True (accepted) unless
       the output's mean log-probability falls in the bottom
       logprob_reject_percentile of this instance's pool (base + samples),
       in which case it is False (rejected). This is deliberately unsound:
       a correct-but-verbose or genuinely uncertain-sounding correct query
       can have low confidence and get rejected by this check, giving it
       real delta > 0, which is exactly what Experiments 5/6 need to test
       (Cor. 3's degradation condition and Cor. 1's safe-composition
       guarantee).
    """
    import json
    import numpy as np

    db_root = db_root or SPIDER_DB_ROOT
    if not db_root or not tables_json_path:
        raise RuntimeError(
            "load_spider_instances_with_scorer needs the official Spider "
            "database.zip. Set SPIDER_DB_ROOT (or pass db_root=) to the "
            "unzipped database/ directory and pass "
            "tables_json_path=.../tables.json.")

    schemas = load_schemas(tables_json_path)
    bundle_root = Path(tables_json_path).parent
    split_file = bundle_root / ("dev.json" if split == "dev" else "train_spider.json")
    with open(split_file) as f:
        ds = json.load(f)

    rng = random.Random(seed)
    idxs = list(range(len(ds)))
    rng.shuffle(idxs)
    idxs = idxs[:n_instances]

    instances = []
    skipped = []
    for i in idxs:
        ex = ds[i]
        db_id = ex["db_id"]
        db_path = os.path.join(db_root, db_id, f"{db_id}.sqlite")
        if not os.path.exists(db_path):
            continue
        schema = schemas.get(db_id, {})
        prompt = _sql_prompt(ex["question"], schema)

        try:
            base_result = orc.chat_completion_with_logprobs(
                model, prompt, temperature=0.0, max_tokens=256)
            base_sql = _extract_sql(base_result["text"])
            base_logprob = base_result["mean_logprob"]

            sample_results = orc.sample_candidates_with_logprobs(
                model, prompt, n_samples, temperature, max_tokens=256)
            sample_sqls = [_extract_sql(r["text"]) for r in sample_results]
            sample_logprobs = [r["mean_logprob"] for r in sample_results]

            all_logprobs = [lp for lp in [base_logprob] + sample_logprobs if lp is not None]
            if len(all_logprobs) < 2:
                skipped.append((db_id, "insufficient logprobs returned for this instance"))
                continue
            threshold = float(np.percentile(all_logprobs, logprob_reject_percentile))

            def label(pred_sql):
                try:
                    return test_suite_accuracy(pred_sql, ex["query"], db_path)
                except ValueError:
                    return False

            def checks(sql, logprob):
                parses = check_parses(sql)
                schema_valid = parses and check_schema_valid(sql, schema)
                executes = schema_valid and check_executes(sql, db_path)
                confidence_gate = logprob is not None and logprob > threshold
                return {"parses": parses, "schema_valid": schema_valid,
                        "executes": executes, "confidence_gate": confidence_gate}

            instances.append(Instance(
                correct_base=label(base_sql),
                correct_samples=[label(s) for s in sample_sqls],
                checks_base=checks(base_sql, base_logprob),
                checks_samples=[checks(s, lp) for s, lp in zip(sample_sqls, sample_logprobs)],
                scorer_scores=[lp if lp is not None else float("-inf") for lp in sample_logprobs],
            ))
        except Exception as e:
            skipped.append((db_id, str(e)[:150]))

    if skipped:
        print(f"load_spider_instances_with_scorer: skipped {len(skipped)}/{len(idxs)} "
              f"instances: {skipped[:5]}{'...' if len(skipped) > 5 else ''}")
    return instances


# ----------------------------------------------------------------------
# baseline scorers: self-consistency (execution-clustered) and
# LLM-as-judge, both stored as scorer_scores exactly like the
# log-probability scorer in load_spider_instances_with_scorer
# ----------------------------------------------------------------------
_JUDGE_PROMPT = """You are judging whether a candidate SQL query correctly \
answers a natural-language question, given a database schema. You do NOT \
have access to a gold answer. Judge from the query's logic alone: does it \
plausibly compute what the question asks, using the right tables and \
columns? Output ONLY a single integer from 0 to 100, where 100 means \
certainly correct and 0 means certainly wrong. No explanation.

Schema:
{schema_str}

Question: {question}

Candidate SQL: {sql}

Score (0-100):"""


def _judge_score(question: str, schema: dict, sql: str, judge_model: str) -> float:
    """LLM-as-judge score in [0, 1], no gold access. Falls back to 0.5
    (uninformative) if the judge's output doesn't parse as a number,
    rather than silently treating a parse failure as either extreme."""
    schema_str = "\n".join(f"{t}({', '.join(sorted(cs))})" for t, cs in schema.items())
    prompt = _JUDGE_PROMPT.format(schema_str=schema_str, question=question, sql=sql)
    try:
        raw = orc.chat_completion(judge_model, prompt, temperature=0.0, max_tokens=10)
        match = re.search(r"\d+", raw)
        if not match:
            return 0.5
        score = max(0, min(100, int(match.group())))
        return score / 100.0
    except Exception:
        return 0.5


def load_spider_instances_with_baselines(model: str, judge_model: str = "gpt-4o",
                                          split: str = "dev", n_instances: int = 50,
                                          n_samples: int = 8, temperature: float = 0.7,
                                          tables_json_path: Optional[str] = None,
                                          db_root: Optional[str] = None, seed: int = 0):
    """Like load_spider_instances, but additionally returns, per instance,
    the self-consistency cluster size and an LLM-as-judge score for every
    sample, for the self-consistency and LLM-as-judge baselines
    (Sec. 6's baseline list, "current selection methods").

    Returns (instances, self_consistency_scores, judge_scores), where the
    latter two are List[List[float]] parallel to instances[i].correct_samples,
    since neither baseline is a boolean check for the gate -- both are
    unsound scorers meant for the SCORER position (Cor. 1), not the gate,
    exactly like the log-probability scorer.

    Self-consistency score: the fraction of the N-sample pool (including
    this candidate) whose execution result matches this candidate's
    (BLOCKERS.txt X6: clustered by execution result, not by output
    string, since string-level voting over SQL text is a straw man for
    this task). A candidate that fails to execute gets a cluster of size
    zero among executing candidates and is scored 0.0, since a
    non-executing candidate cannot win a vote among results that do run.

    LLM-as-judge score: GPT-4o judges each candidate independently, given
    only the question, schema and candidate SQL -- no gold access, exactly
    as an LLM judge would operate at deployment time.
    """
    import json

    db_root = db_root or SPIDER_DB_ROOT
    if not db_root or not tables_json_path:
        raise RuntimeError(
            "load_spider_instances_with_baselines needs the official "
            "Spider database.zip. Set SPIDER_DB_ROOT (or pass db_root=) "
            "and tables_json_path=.../tables.json.")

    schemas = load_schemas(tables_json_path)
    bundle_root = Path(tables_json_path).parent
    split_file = bundle_root / ("dev.json" if split == "dev" else "train_spider.json")
    with open(split_file) as f:
        ds = json.load(f)

    rng = random.Random(seed)
    idxs = list(range(len(ds)))
    rng.shuffle(idxs)
    idxs = idxs[:n_instances]

    instances, sc_scores, judge_scores = [], [], []
    skipped = []
    for i in idxs:
        ex = ds[i]
        db_id = ex["db_id"]
        db_path = os.path.join(db_root, db_id, f"{db_id}.sqlite")
        if not os.path.exists(db_path):
            continue
        schema = schemas.get(db_id, {})
        prompt = _sql_prompt(ex["question"], schema)

        try:
            base_raw = orc.chat_completion(model, prompt, temperature=0.0, max_tokens=256)
            base_sql = _extract_sql(base_raw)
            sample_raws = orc.sample_candidates(model, prompt, n_samples, temperature, max_tokens=256)
            sample_sqls = [_extract_sql(r) for r in sample_raws]

            def label(pred_sql):
                try:
                    return test_suite_accuracy(pred_sql, ex["query"], db_path)
                except ValueError:
                    return False

            def checks(sql):
                parses = check_parses(sql)
                schema_valid = parses and check_schema_valid(sql, schema)
                executes = schema_valid and check_executes(sql, db_path)
                return {"parses": parses, "schema_valid": schema_valid, "executes": executes}

            instances.append(Instance(
                correct_base=label(base_sql),
                correct_samples=[label(s) for s in sample_sqls],
                checks_base=checks(base_sql),
                checks_samples=[checks(s) for s in sample_sqls],
                scorer_scores=None,
            ))

            # self-consistency: cluster by execution result over the sample pool
            results = [execution_result(s, db_path) for s in sample_sqls]
            executing = [r for r in results if r is not None]
            from collections import Counter
            counts = Counter(executing)
            total_executing = len(executing) if executing else 1
            sc_scores.append([
                (counts[r] / total_executing) if r is not None else 0.0
                for r in results
            ])

            # LLM-as-judge: independent score per sample, no gold access
            judge_scores.append([
                _judge_score(ex["question"], schema, s, judge_model) for s in sample_sqls
            ])
        except Exception as e:
            skipped.append((db_id, str(e)[:150]))

    if skipped:
        print(f"load_spider_instances_with_baselines: skipped {len(skipped)}/{len(idxs)} "
              f"instances: {skipped[:5]}{'...' if len(skipped) > 5 else ''}")
    return instances, sc_scores, judge_scores
