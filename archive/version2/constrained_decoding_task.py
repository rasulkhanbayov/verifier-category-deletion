#!/usr/bin/env python3
"""
constrained_decoding_task.py
-------------------------------
Constrained-decoding baseline for text-to-SQL, the one item from the
paper's original Sec. 6 baseline list never measured, because grammar/
finite-state decoding needs logit-level access that none of the four
OpenRouter-hosted models expose via chat completions.

Runs a small open-weights model LOCALLY (transformers + outlines) with
output constrained to a regex matching a realistic SQL subset, so the
"parses" and "schema_valid"-adjacent syntax properties are guaranteed by
construction rather than audited post hoc, exactly the trade-off the
paper's own related-work paragraph on constrained decoding describes.

SCOPE, STATED HONESTLY: a full SQL context-free grammar is not readily
available (neither outlines nor sqlglot ships one, and hand-writing one
risks being subtly wrong in a way that would silently defeat the point
of this baseline -- guaranteed well-formedness). Instead this uses a
REGEX constraint over a NO-SUBQUERY SQL subset: single or double (via
INTERSECT/UNION/EXCEPT) SELECT ... FROM ... [JOIN ...]* [WHERE ...]
[GROUP BY ...] [HAVING ...] [ORDER BY ...] [LIMIT ...]. Verified against
real Spider dev gold queries: covers 100% of the 875 subquery-free
queries (84.6% of the full 1,034-query dev set) and correctly rejects
malformed/garbage SQL in every spot check. Regular expressions cannot
express nested/balanced subqueries in general, so queries requiring a
subquery (15.4% of dev) are OUT OF SCOPE for this baseline by
construction -- reported as a real coverage limit, not elided.

The resulting SQL string is checked with the SAME functions used for
every other row in this paper (spider_task.check_parses,
check_schema_valid, check_executes, test_suite_accuracy), so the
comparison in Table 3 is apples-to-apples regardless of how the
candidate was generated.
"""
import json
import os
import random
import re
from pathlib import Path
from typing import List, Optional

import spider_task as st
from soundver_experiments import Instance

DB_ROOT = "../spider_data/spider_data/database"
TABLES_JSON = "../spider_data/spider_data/tables.json"

# a permissively-licensed, small (fits comfortably in a shared GPU's
# spare VRAM) instruct model for local generation
MODEL_NAME = "Qwen/Qwen2.5-1.5B-Instruct"


# ----------------------------------------------------------------------
# the regex constraint, verified against real Spider gold queries before
# use (see module docstring for the verification numbers)
# ----------------------------------------------------------------------
def build_sql_regex() -> str:
    ident = r"[A-Za-z_][A-Za-z0-9_.]*"
    alias = r"(?:\s+AS\s+[A-Za-z_][A-Za-z0-9_]*)?"
    value = r"(?:'[^']*'|\"[^\"]*\"|-?\d+(?:\.\d+)?)"
    func = r"(?:COUNT|SUM|AVG|MIN|MAX)\s*\(\s*(?:DISTINCT\s+)?(?:\*|" + ident + r")\s*\)"
    col = r"(?:\*|" + func + r"|" + ident + r")" + alias
    col_list = col + r"(?:\s*,\s*" + col + r")*"
    cond_operand = r"(?:" + func + r"|" + value + r"|" + ident + r")"
    op = r"(?:=|!=|<>|<=|>=|<|>|LIKE|IN)"
    cond_atom = (
        r"(?:" + cond_operand + r"\s*" + op + r"\s*" + cond_operand +
        r"|" + cond_operand + r"\s+BETWEEN\s+" + cond_operand + r"\s+AND\s+" + cond_operand + r")"
    )
    cond = cond_atom + r"(?:\s+(?:AND|OR)\s+" + cond_atom + r")*"
    join = r"(?:\s+(?:INNER\s+)?JOIN\s+" + ident + alias + r"\s+ON\s+" + cond + r")*"

    select_stmt = (
        r"SELECT\s+(?:DISTINCT\s+)?" + col_list +
        r"\s+FROM\s+" + ident + alias + join +
        r"(?:\s+WHERE\s+" + cond + r")?" +
        r"(?:\s+GROUP\s+BY\s+" + col_list + r")?" +
        r"(?:\s+HAVING\s+" + cond + r")?" +
        r"(?:\s+ORDER\s+BY\s+" + col_list + r"(?:\s+(?:ASC|DESC))?)?" +
        r"(?:\s+LIMIT\s+\d+)?"
    )
    return select_stmt + r"(?:\s+(?:INTERSECT|UNION|EXCEPT)\s+" + select_stmt + r")?"


def check_regex_coverage(regex_pattern: str, dev_json_path: str) -> dict:
    """Verification helper: what fraction of real Spider dev gold queries
    does this regex match? Run once at development time, not per-instance
    -- kept here so the coverage claim in the module docstring is
    reproducible rather than just asserted."""
    with open(dev_json_path) as f:
        ds = json.load(f)
    subquery_free = [ex["query"] for ex in ds if ex["query"].upper().count("SELECT") == 1]
    pattern = re.compile(regex_pattern, re.IGNORECASE)
    matched = 0
    for q in subquery_free:
        q_norm = re.sub(r"\s+", " ", q.strip()).rstrip(";").strip()
        if pattern.fullmatch(q_norm):
            matched += 1
    return {
        "subquery_free_matched": matched,
        "subquery_free_total": len(subquery_free),
        "full_dev_total": len(ds),
        "coverage_of_subquery_free": matched / len(subquery_free) if subquery_free else 0.0,
        "coverage_of_full_dev": matched / len(ds) if ds else 0.0,
    }


# ----------------------------------------------------------------------
# local model loading (lazy -- only imported/loaded if this module is
# actually used for generation, so importing it elsewhere doesn't force
# a GPU/model download)
# ----------------------------------------------------------------------
_model = None
_tokenizer = None
_outlines_model = None
_generator_cache = {}  # regex_pattern -> outlines.Generator, since building
                       # the regex FSM is a ~40s one-time cost per pattern
                       # (confirmed empirically) but reused generation calls
                       # against an already-built Generator take <1s


def _load_local_model():
    global _model, _tokenizer, _outlines_model
    if _outlines_model is not None:
        return _outlines_model

    import torch
    import outlines
    from transformers import AutoModelForCausalLM, AutoTokenizer

    # the P100 (CUDA capability 6.0) is below Triton's minimum supported
    # capability (7.0), so torch.compile's inductor backend fails; disable
    # dynamo rather than let every generation call raise/fall back with a
    # multi-line warning
    torch._dynamo.config.suppress_errors = True
    torch._dynamo.disable()

    print(f"Loading {MODEL_NAME} locally (this downloads weights on first run)...", flush=True)
    _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    _model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME, torch_dtype=torch.bfloat16, device_map="cuda"
    )
    _outlines_model = outlines.from_transformers(_model, _tokenizer)
    print("Model loaded.", flush=True)
    return _outlines_model


def _sql_prompt(question: str, schema: dict) -> str:
    schema_str = "\n".join(f"{t}({', '.join(sorted(cs))})" for t, cs in schema.items())
    return (
        "Given the database schema below, write a single SQLite SELECT "
        "query (no subqueries) that answers the question.\n\n"
        f"Schema:\n{schema_str}\n\nQuestion: {question}\nSQL:"
    )


def _get_generator(regex_pattern: str):
    import outlines

    if regex_pattern not in _generator_cache:
        model = _load_local_model()
        _generator_cache[regex_pattern] = outlines.Generator(model, outlines.types.Regex(regex_pattern))
    return _generator_cache[regex_pattern]


def generate_constrained(question: str, schema: dict, regex_pattern: str,
                          temperature: float = 0.0) -> str:
    """One constrained generation. temperature=0.0 gives the (single)
    greedy base output; the same call at temperature>0 for sampled
    candidates, mirroring every other task's base/samples split."""
    generator = _get_generator(regex_pattern)
    prompt = _sql_prompt(question, schema)
    # outlines' Transformers backend generation kwargs pass through to
    # transformers' .generate(); temperature=0.0 needs do_sample=False
    # explicitly, since transformers treats temperature=0 as an error
    # otherwise rather than "greedy".
    if temperature <= 0.0:
        return generator(prompt, max_new_tokens=200, do_sample=False)
    return generator(prompt, max_new_tokens=200, do_sample=True, temperature=temperature)


# ----------------------------------------------------------------------
# the load_instances() implementation
# ----------------------------------------------------------------------
def load_constrained_decoding_instances(n_instances: int = 50, n_samples: int = 8,
                                         temperature: float = 0.7,
                                         tables_json_path: Optional[str] = None,
                                         db_root: Optional[str] = None,
                                         seed: int = 0) -> List[Instance]:
    """Real data source for the constrained-decoding baseline. Requires
    the official Spider database.zip, same as spider_task.py. Generates
    LOCALLY (no OpenRouter spend) with the SQL regex constraint. Uses the
    SAME checks/label as every other SQL row (spider_task's check_parses/
    check_schema_valid/check_executes/test_suite_accuracy)."""
    tables_json_path = tables_json_path or TABLES_JSON
    db_root = db_root or DB_ROOT

    schemas = st.load_schemas(tables_json_path)
    bundle_root = Path(tables_json_path).parent
    with open(bundle_root / "dev.json") as f:
        ds = json.load(f)

    rng = random.Random(seed)
    idxs = list(range(len(ds)))
    rng.shuffle(idxs)
    idxs = idxs[:n_instances]

    regex_pattern = build_sql_regex()

    instances = []
    skipped = []
    for i in idxs:
        ex = ds[i]
        db_id = ex["db_id"]
        db_path = os.path.join(db_root, db_id, f"{db_id}.sqlite")
        if not os.path.exists(db_path):
            continue
        schema = schemas.get(db_id, {})

        try:
            base_sql = generate_constrained(ex["question"], schema, regex_pattern, temperature=0.0)
            sample_sqls = [
                generate_constrained(ex["question"], schema, regex_pattern, temperature=temperature)
                for _ in range(n_samples)
            ]

            def label(sql):
                try:
                    return st.test_suite_accuracy(sql, ex["query"], db_path)
                except ValueError:
                    return False

            def checks(sql):
                parses = st.check_parses(sql)
                schema_valid = parses and st.check_schema_valid(sql, schema)
                executes = schema_valid and st.check_executes(sql, db_path)
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
        print(f"load_constrained_decoding_instances: skipped {len(skipped)}/{len(idxs)} "
              f"instances: {skipped[:5]}{'...' if len(skipped) > 5 else ''}")
    return instances
