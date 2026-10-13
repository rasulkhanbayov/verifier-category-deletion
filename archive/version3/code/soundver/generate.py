"""
soundver.generate -- turn datasets and models into the records everything reads.

This is the missing link. `reconcile`, `validity` and `ladder` all consume
`data/records.jsonl`; nothing in the archive produced it. This does.

It makes real API calls and needs credentials, so it will not run in a sandbox
and it fabricates nothing: with no key it prints the plan and exits non-zero.

  python -m soundver.generate --task sql --dry-run          # plan and cost
  python -m soundver.generate --task sql --out data/records.jsonl

WHAT IT WRITES. One record per (task, model, instance, candidate), the schema in
records.py. The base output is cand_idx = -1 at temperature 0; candidates are
cand_idx 0..N-1 at the sampling temperature.

THE LABEL IS THE PART THAT MATTERS. `correct` must come from an ADMISSIBLE
label, Def. 2 of the paper: one the check does not already entail. For SQL that
means test-suite accuracy, NOT execution match, because execution match entails
the whole stack and would return delta = 0 by construction. That choice is
enforced below rather than left to a flag.

MODEL SNAPSHOTS. `--model` must be a pinned snapshot. `openai/gpt-4o` is a
moving endpoint and is refused, because B9 records that no snapshot strings were
kept for the original runs and the numbers are therefore not reproducible. Do
not repeat that.
"""
from __future__ import annotations
import argparse, concurrent.futures, json, os, sys, threading, time
from dataclasses import asdict

from .records import Record, CHECKS, write
from .checks import (sql_extract, sql_parses, sql_schema_valid, sql_executes,
                     ie_parses, ie_required_fields, ie_schema_valid,
                     ie_no_overlap, morph_no_empty_segment, morph_concatenates)

MOVING = {"openai/gpt-4o", "openai/gpt-4o-mini", "anthropic/claude-3-5-sonnet"}

# Llama-3.1 has no dated-snapshot slug on OpenRouter at all -- meta-llama's
# own endpoints are not versioned the way OpenAI's are, so
# "meta-llama/llama-3.1-8b-instruct" is the only routable id and is a moving
# target by construction (OpenRouter can and does serve it from different
# backend providers on different days). B9 cannot be closed for these models
# the same way it is for GPT-4o's dated snapshots; documented exception,
# mitigated by recording the actual serving `provider` OpenRouter returns
# per request (see PROVIDER_LOG below) rather than silently accepting an
# unpinned model with no record of what actually served it.
# Qwen2.5's OpenRouter ids ("qwen/qwen-2.5-7b-instruct",
# "qwen/qwen-2.5-72b-instruct") are the same category: no dated snapshot
# exists, so the same mitigation applies (kept in this set despite the
# name -- it means "no dated snapshot", not specifically Llama).
LLAMA_NO_SNAPSHOT = {"meta-llama/llama-3.1-8b-instruct",
                     "meta-llama/llama-3.1-70b-instruct",
                     "qwen/qwen-2.5-7b-instruct",
                     "qwen/qwen-2.5-72b-instruct"}

ADMISSIBLE_LABEL = {
    "sql":   "test_suite_accuracy",   # NOT execution match: see Def. 2
    "ie":    "field_value_match",
    "morph": "gold_segmentation_match",
}


def check_snapshot(model: str) -> None:
    if model in MOVING:
        sys.exit(
            f"refusing '{model}': a moving endpoint is not reproducible.\n"
            f"Pass a pinned snapshot, e.g. 'openai/gpt-4o-2024-11-20'.\n"
            f"See B9 in REDFLAGS.md.")
    if model in LLAMA_NO_SNAPSHOT:
        print(f"  NOTE: '{model}' has no dated snapshot on OpenRouter "
              f"(documented B9 exception); serving provider will be logged "
              f"per request instead.", file=sys.stderr)


# --------------------------------------------------------------------------
# dataset loading. Reuses the SCHEMA-PARSING AND PROMPT-CONSTRUCTION LOGIC
# from version2's task adapters (spider_task.py etc, imported as a library),
# never their previously-collected records or output -- this run is a fresh
# collection through this file's own admissible labels and reference checks.
# --------------------------------------------------------------------------
DATA_ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..")
SPIDER_TABLES = os.path.join(DATA_ROOT, "spider_data", "spider_data", "tables.json")
SPIDER_DEV = os.path.join(DATA_ROOT, "spider_data", "spider_data", "dev.json")
SPIDER_DB_ROOT = os.path.join(DATA_ROOT, "spider_data", "spider_data", "database")
IE_ROOT = os.path.join(DATA_ROOT, "ie_data")
MORPH_ROOT = os.path.join(DATA_ROOT, "morph_data")

# IE_ENTITY_TYPES: CoNLL2003/iepile's flat entity-type inventory. The task is
# redesigned here as SLOT FILLING -- one field per type holding a list of
# extracted spans -- so the paper's stated checks (parses as JSON; validates
# against schema; required fields present; no schema-forbidden overlap) are
# meaningful against checks.py's flat-object contract, rather than the
# entity-list format version2 used. See REDFLAGS.md discussion for why this
# was a deliberate redesign, not an oversight.
IE_ENTITY_TYPES = ["location", "else", "organization", "person"]
IE_SCHEMA = {t: "list" for t in IE_ENTITY_TYPES}


def _load_sql_items(n_instances: int, seed: int):
    import random, json as _json
    with open(SPIDER_TABLES) as f:
        tables = _json.load(f)
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
    with open(SPIDER_DEV) as f:
        ds = _json.load(f)
    rng = random.Random(seed)
    idxs = list(range(len(ds)))
    rng.shuffle(idxs)
    items = []
    for i in idxs[:n_instances]:
        ex = ds[i]
        db_path = os.path.join(SPIDER_DB_ROOT, ex["db_id"], f"{ex['db_id']}.sqlite")
        if not os.path.exists(db_path):
            continue
        items.append({
            "instance_id": f"sql-{i:05d}", "question": ex["question"],
            "gold_sql": ex["query"], "db_id": ex["db_id"],
            "db_path": db_path, "schema": schemas.get(ex["db_id"], {}),
        })
    return items


_SQL_FEWSHOT = (
    "Example.\nSchema:\nstudent(id, name, age)\n"
    "Question: What are the names of students older than 20?\n"
    "SQL: SELECT name FROM student WHERE age > 20\n\n")

_SQL_FORMAT_REMINDER = (
    "IMPORTANT: your entire response must be ONLY the raw SQL query and "
    "absolutely nothing else -- no code fences, no leading/trailing "
    "commentary, no explanation of any kind, or the answer will be scored "
    "as wrong.\n\n")


def _sql_prompt(question: str, schema: dict, prompt_id: str = "base") -> str:
    schema_str = "\n".join(f"{t}({', '.join(sorted(cs))})" for t, cs in schema.items())

    if prompt_id == "paraphrase_a":
        head = ("You are a text-to-SQL assistant. Read the schema and the "
                "question, then produce exactly one SQLite query that "
                "correctly answers it. Reply with the SQL only -- no prose, "
                "no markdown.\n\n")
    elif prompt_id == "paraphrase_b":
        head = ("Translate the question below into a single valid SQLite "
                "statement, using only the tables and columns given in the "
                "schema. Return just the query itself, without any "
                "surrounding text or formatting.\n\n")
    else:
        head = ("Given the database schema below, write a single SQLite query "
                "that answers the question. Output ONLY the SQL query, no "
                "explanation, no markdown fences.\n\n")

    fewshot = "" if prompt_id == "no_fewshot" else _SQL_FEWSHOT
    reminder = _SQL_FORMAT_REMINDER if prompt_id == "format_reminder" else ""

    return (f"{head}{fewshot}{reminder}"
            f"Schema:\n{schema_str}\n\nQuestion: {question}\nSQL:")


def _load_ie_items(n_instances: int, seed: int):
    import random, json as _json
    examples = []
    with open(os.path.join(IE_ROOT, "test.json")) as f:
        for line in f:
            line = line.strip()
            if line:
                examples.append(_json.loads(line))
    rng = random.Random(seed)
    idxs = list(range(len(examples)))
    rng.shuffle(idxs)
    items = []
    for i in idxs[:n_instances]:
        ex = examples[i]
        gold = {t: [] for t in IE_ENTITY_TYPES}
        for e in ex["entity"]:
            gold.setdefault(e["entity_type"], []).append(e["entity"])
        items.append({"instance_id": f"ie-{i:05d}", "text": ex["text"], "gold": gold})
    return items


_IE_FIELD_DESC = (
    '  "person": names of people\n'
    '  "location": names of places\n'
    '  "organization": names of companies, teams, institutions, or '
    "other organizations\n"
    '  "else": any OTHER named entity that does not fit the three '
    "types above (e.g. named events, competitions, nationalities "
    "used as proper nouns, titled works) -- NOT ordinary words, "
    "numbers, or dates that are not themselves a named entity.\n")

_IE_FEWSHOT = (
    'Example.\nText: John Smith joined Acme Corp in Paris.\n'
    'JSON: {"person": ["John Smith"], "location": ["Paris"], '
    '"organization": ["Acme Corp"], "else": []}\n\n')

_IE_FORMAT_REMINDER = (
    "IMPORTANT: your entire response must be ONLY the raw JSON object and "
    "absolutely nothing else -- no code fences, no leading/trailing "
    "commentary, no explanation of any kind, or the answer will be scored "
    "as wrong.\n\n")


def _ie_prompt(text: str, prompt_id: str = "base") -> str:
    fields = ", ".join(f'"{t}": [list of exact substrings]' for t in IE_ENTITY_TYPES)

    if prompt_id == "paraphrase_a":
        head = ("You are a named-entity extraction assistant. Read the text "
                "below and identify every named entity, sorting each into "
                "one of the four fields described below. Reply with the "
                "JSON object only -- no prose, no markdown.\n\n")
    elif prompt_id == "paraphrase_b":
        head = ("Find all named entities in the passage below and organize "
                "them into the four categories listed. Return just the "
                "resulting JSON, without any surrounding text or "
                "formatting.\n\n")
    else:
        head = "Extract every named entity from the text below into the following four fields:\n"

    fewshot = "" if prompt_id == "no_fewshot" else _IE_FEWSHOT
    reminder = _IE_FORMAT_REMINDER if prompt_id == "format_reminder" else ""

    return (f"{head}{_IE_FIELD_DESC}"
            "If the text contains no entities of a given type, or no "
            "entities at all, use an empty list for that field -- do not "
            "invent an entity to avoid an empty list. Every field must be "
            f"present. Output ONLY a JSON object of the form {{{fields}}}, "
            f"no explanation, no markdown fences.\n\n{fewshot}{reminder}"
            f"Text: {text}\nJSON:")


def _ie_extract_json(raw: str) -> str:
    import re as _re
    text = raw.strip()
    fence = _re.search(r"```(?:json)?\s*(.*?)```", text, _re.DOTALL | _re.IGNORECASE)
    return fence.group(1).strip() if fence else text


def _field_value_match(pred: dict | None, gold: dict) -> bool:
    """Exact match on extracted field values, case/whitespace-normalised,
    independent of any check above -- Def. 2 admissibility: this label does
    not presuppose parses/schema_valid/no_overlap."""
    if pred is None:
        return False
    def norm(d):
        out = {}
        for t in IE_ENTITY_TYPES:
            v = d.get(t, [])
            v = v if isinstance(v, list) else [v]
            out[t] = sorted(str(x).strip().lower() for x in v if isinstance(x, (str, int, float)))
        return out
    return norm(pred) == norm(gold)


def _load_morph_items(n_instances: int, seed: int):
    import random
    rows = []
    with open(os.path.join(MORPH_ROOT, "eng.word.test.gold.tsv"), encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            rows.append((parts[0], parts[1]))
    rng = random.Random(seed)
    idxs = list(range(len(rows)))
    rng.shuffle(idxs)
    items = []
    for i in idxs[:n_instances]:
        surface, gold_str = rows[i]
        gold_segs = [m[2:] if m.startswith("@@") else m for m in gold_str.split(" ") if m]
        items.append({"instance_id": f"morph-{i:05d}", "surface": surface,
                      "gold_segments": gold_segs})
    return items


_MORPH_FORMAT_REMINDER = (
    " IMPORTANT: your entire response must be ONLY the segmentation and "
    "absolutely nothing else -- no leading/trailing commentary, no "
    "explanation of any kind, or the answer will be scored as wrong.")


def _morph_prompt(surface: str, prompt_id: str = "base") -> str:
    if prompt_id == "paraphrase_a":
        head = ("Break the English word below down into its component "
                "morphemes (prefixes, roots, and suffixes). Reply with the "
                "morphemes only, joined by '+', and nothing else.")
    elif prompt_id == "paraphrase_b":
        head = ("Decompose the following word into its morphological parts "
                "and list them separated by '+'. Do not include any other "
                "text in your answer.")
    else:
        head = ("Segment the following English word into its morphemes "
                "(prefixes, roots, suffixes). Output ONLY the morphemes "
                "separated by '+', with no explanation.")

    fewshot = ("" if prompt_id == "no_fewshot"
               else " e.g. for 'subsidised' output: subside+y+ise+ed")
    reminder = _MORPH_FORMAT_REMINDER if prompt_id == "format_reminder" else ""

    return f"{head}{fewshot}{reminder}\n\nWord: {surface}\nSegmentation:"


def _gold_segmentation_match(segs, gold_segs) -> bool:
    """Exact list match against the gold canonical segmentation -- Def. 2
    admissibility: does not presuppose no_empty_segment or concatenates."""
    return list(segs) == list(gold_segs)


LOADERS = {"sql": _load_sql_items, "ie": _load_ie_items, "morph": _load_morph_items}
PROMPTS = {"sql": lambda it, pid: _sql_prompt(it["question"], it["schema"], pid),
          "ie": lambda it, pid: _ie_prompt(it["text"], pid),
          "morph": lambda it, pid: _morph_prompt(it["surface"], pid)}
PROMPT_VARIANTS = ("base", "paraphrase_a", "paraphrase_b", "no_fewshot", "format_reminder")


def score_checks(task: str, raw: str, item: dict):
    """Apply the reference stack. Returns (check name -> bool, parsed output)."""
    if task == "sql":
        q = sql_extract(raw)
        p = sql_parses(q)
        sv = p and sql_schema_valid(q, item["schema"])
        ex = sv and sql_executes(q, item.get("conn"))
        return ({"parses": p, "schema_valid": bool(sv), "executes": bool(ex)}, q)
    if task == "ie":
        cleaned = _ie_extract_json(raw)
        o = ie_parses(cleaned)
        required = IE_ENTITY_TYPES
        rf = ie_required_fields(o, required)
        return ({"parses": o is not None,
                 "required_fields": rf,
                 "schema_valid": rf and ie_schema_valid(o, IE_SCHEMA),
                 "no_overlap": rf and ie_no_overlap(o, item["text"])}, o)
    segs = [s.strip() for s in raw.strip().split("+") if s.strip()]
    return ({"no_empty_segment": morph_no_empty_segment(segs),
             "concatenates": morph_concatenates(segs, item["surface"])}, segs)


# --------------------------------------------------------------------------
# completion call. Minimal OpenRouter client, deliberately self-contained
# (not importing version2's openrouter_client.py) so this module has no
# runtime dependency outside this archive; the request/response shape is the
# same OpenRouter chat-completions API either way.
# --------------------------------------------------------------------------
def _api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY")
    if key:
        return key
    env_path = os.path.join(DATA_ROOT, ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith("OPENROUTER_API_KEY"):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("OPENROUTER_API_KEY not set and not found in ../.env")


# E5's degradation experiment needs a genuinely UNSOUND scorer (mean
# log-probability of the completion, rejecting/ranking down the least
# confident candidates) attached per-candidate. Some providers serving a
# given OpenRouter model slug do not return logprobs at all; pinned to
# providers confirmed (this session) to return them for these two models,
# mirroring version2's own documented finding of the same gap.
LOGPROB_PROVIDER = {
    "meta-llama/llama-3.1-8b-instruct": "Novita",
    "meta-llama/llama-3.1-70b-instruct": "CoreWeave",
}


def _complete(model: str, prompt: str, temperature: float, max_tokens: int = 512,
              retries: int = 6, want_logprobs: bool = False):
    """Returns (text, provider, system_fingerprint, mean_logprob).
    mean_logprob is None when want_logprobs is False, or when the
    responding provider did not return per-token logprobs even after
    pinning (checked, not assumed) -- callers must not treat a missing
    score as zero. provider/system_fingerprint are what B9's Llama
    exception (LLAMA_NO_SNAPSHOT) is logged against.

    RATE-LIMIT HANDLING: a 429 (Too Many Requests) or 504 (Gateway
    Timeout, observed in practice to correlate with upstream throttling
    under sustained high request volume, not just transient network
    blips) needs a much longer backoff than a generic transient error --
    confirmed the hard way: the original 3-retry/1-2-4s backoff let an
    entire (task, model, seed) cell fail 200/200 outright once
    OpenRouter started rate-limiting this key under sustained load.
    Respects a `Retry-After` header when the API provides one, and
    otherwise backs off exponentially starting from a much longer base
    (10s) than a generic-error retry (1s), since a 429/504 needs real
    cooldown time to clear, not a quick reattempt."""
    import requests
    headers = {"Authorization": f"Bearer {_api_key()}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}],
              "temperature": temperature, "max_tokens": max_tokens}
    if want_logprobs:
        payload["logprobs"] = True
        if model in LOGPROB_PROVIDER:
            payload["provider"] = {"only": [LOGPROB_PROVIDER[model]]}
    last_err = None
    for attempt in range(retries):
        try:
            resp = requests.post("https://openrouter.ai/api/v1/chat/completions",
                                 headers=headers, json=payload, timeout=60)
            if resp.status_code in (429, 504):
                retry_after = resp.headers.get("Retry-After")
                if retry_after is not None:
                    try:
                        delay = float(retry_after)
                    except ValueError:
                        delay = 10.0 * (2 ** attempt)
                else:
                    delay = 10.0 * (2 ** attempt)
                delay = min(delay, 120.0)
                last_err = requests.exceptions.HTTPError(
                    f"{resp.status_code} rate/gateway limited")
                time.sleep(delay)
                continue
            resp.raise_for_status()
            data = resp.json()
            choice = data["choices"][0]
            text = choice["message"]["content"]
            mean_logprob = None
            if want_logprobs:
                lp = choice.get("logprobs")
                if lp and lp.get("content"):
                    token_logprobs = [t["logprob"] for t in lp["content"] if "logprob" in t]
                    if token_logprobs:
                        mean_logprob = sum(token_logprobs) / len(token_logprobs)
            return text, data.get("provider"), data.get("system_fingerprint"), mean_logprob
        except Exception as e:  # noqa: BLE001 -- network/API errors, retry then surface
            last_err = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"OpenRouter call failed after {retries} attempts: {last_err}")


def _label_correct(task: str, item: dict, raw: str, parsed) -> bool:
    """The admissible label per Def. 2 -- computed independently of any
    check above, never entailing one."""
    if task == "sql":
        q = sql_extract(raw)
        try:
            import sys as _sys
            _sys.path.insert(0, DATA_ROOT + "/version2")
            from spider_task import test_suite_accuracy
            return test_suite_accuracy(q, item["gold_sql"], item["db_path"])
        except ValueError:
            return False
    if task == "ie":
        return _field_value_match(parsed if isinstance(parsed, dict) else None,
                                  item["gold"])
    return _gold_segmentation_match(parsed, item["gold_segments"])


def plan(task: str, models, seeds, n_inst: int, n_cand: int) -> None:
    calls = len(models) * len(seeds) * n_inst * (1 + n_cand)
    print(f"  task            {task}")
    print(f"  label           {ADMISSIBLE_LABEL[task]}  (admissible by Def. 2)")
    print(f"  checks          {CHECKS[task]}")
    print(f"  models          {len(models)}: {', '.join(models)}")
    print(f"  seeds           {seeds}")
    print(f"  instances       {n_inst}")
    print(f"  candidates      {n_cand} at temperature 0.7, plus 1 greedy")
    print(f"  total API calls {calls:,}")
    print(f"\n  Budget >= 400 instances per cell for the capability ladder (X0);")
    print(f"  200 does not separate adjacent models on epsilon.")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", required=True, choices=sorted(CHECKS))
    ap.add_argument("--models", nargs="+",
                    default=["openai/gpt-4o-2024-11-20"])
    ap.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2, 3, 4])
    ap.add_argument("--instances", type=int, default=200)
    ap.add_argument("--candidates", type=int, default=32)
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--prompt-id", default="base")
    ap.add_argument("--out", default="data/records.jsonl")
    ap.add_argument("--want-logprobs", action="store_true",
                    help="capture mean per-token log-probability as each "
                         "candidate's score, for E5's degradation "
                         "experiment (an unsound confidence scorer). Off "
                         "by default since it is not needed for the "
                         "soundness/ceiling audit and pins Llama requests "
                         "to a specific provider (see LOGPROB_PROVIDER).")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    for m in a.models:
        check_snapshot(m)

    print("GENERATION PLAN\n")
    plan(a.task, a.models, a.seeds, a.instances, a.candidates)

    if a.dry_run:
        return 0

    try:
        _api_key()
    except RuntimeError:
        print("\nOPENROUTER_API_KEY is not set. Nothing was generated.")
        print("This script never invents outputs; set the key and re-run.")
        return 2

    max_tokens = {"sql": 256, "ie": 512, "morph": 64}[a.task]
    records = []
    # B9 mitigation for LLAMA_NO_SNAPSHOT models: OpenRouter's actual serving
    # `provider` (and system_fingerprint, when returned) logged per request
    # to a side file next to the records, since Record's schema (records.py)
    # is shared, validated infrastructure other modules depend on and is not
    # extended here just to carry this one task's provenance metadata.
    provider_log_path = os.path.splitext(a.out)[0] + ".providers.jsonl"
    provider_log = open(provider_log_path, "a")
    provider_log_lock = threading.Lock()

    def process_one(task, model, seed, item, prompt_id):
        """One instance: greedy base + `a.candidates` sampled candidates.
        Runs on a worker thread -- I/O-bound (network calls), so the GIL is
        not a bottleneck here. Returns (list[Record], list[provider dict],
        error-or-None) rather than raising, so one bad instance cannot take
        down the whole batch of concurrent futures."""
        recs, prov_entries = [], []
        sql_conn = None
        t_start = time.time()
        try:
            prompt = PROMPTS[task](item, prompt_id)
            local_item = item
            if task == "sql":
                import sqlite3
                sql_conn = sqlite3.connect(item["db_path"], timeout=5.0)
                sql_conn.text_factory = lambda b: b.decode("utf-8", errors="replace")
                local_item = {**item, "conn": sql_conn}

            base_text, base_prov, base_fp, base_lp = _complete(
                model, prompt, temperature=0.0, max_tokens=max_tokens,
                want_logprobs=a.want_logprobs)
            if time.time() - t_start > 30:
                print(f"    [slow] {item['instance_id']} base completion took "
                     f"{time.time() - t_start:.0f}s", flush=True)
            base_checks, base_parsed = score_checks(task, base_text, local_item)
            base_correct = _label_correct(task, local_item, base_text, base_parsed)
            recs.append(Record(task=task, model=model, seed=seed,
                               instance_id=item["instance_id"], cand_idx=-1,
                               correct=base_correct, checks=base_checks,
                               score=base_lp, prompt_id=prompt_id))
            if model in LLAMA_NO_SNAPSHOT:
                prov_entries.append({"model": model, "instance_id": item["instance_id"],
                                     "cand_idx": -1, "provider": base_prov,
                                     "system_fingerprint": base_fp})

            for c in range(a.candidates):
                t_c = time.time()
                cand_text, cand_prov, cand_fp, cand_lp = _complete(
                    model, prompt, temperature=a.temperature, max_tokens=max_tokens,
                    want_logprobs=a.want_logprobs)
                cand_checks, cand_parsed = score_checks(task, cand_text, local_item)
                t_label = time.time()
                cand_correct = _label_correct(task, local_item, cand_text, cand_parsed)
                if time.time() - t_label > 15:
                    print(f"    [slow] {item['instance_id']} cand={c} "
                         f"_label_correct took {time.time() - t_label:.0f}s "
                         f"(sql={sql_extract(cand_text)[:80]!r})", flush=True)
                if time.time() - t_c > 30:
                    print(f"    [slow] {item['instance_id']} cand={c} total "
                         f"{time.time() - t_c:.0f}s", flush=True)
                recs.append(Record(task=task, model=model, seed=seed,
                                   instance_id=item["instance_id"], cand_idx=c,
                                   correct=cand_correct, checks=cand_checks,
                                   score=cand_lp, prompt_id=prompt_id))
                if model in LLAMA_NO_SNAPSHOT:
                    prov_entries.append({"model": model, "instance_id": item["instance_id"],
                                         "cand_idx": c, "provider": cand_prov,
                                         "system_fingerprint": cand_fp})
            return recs, prov_entries, None
        except Exception as e:
            return [], [], (item["instance_id"], str(e)[:150])
        finally:
            if sql_conn is not None:
                sql_conn.close()

    N_WORKERS = int(os.environ.get("SOUNDVER_GEN_WORKERS", "8"))
    for seed in a.seeds:
        items = LOADERS[a.task](a.instances, seed)
        print(f"\nseed={seed}: {len(items)} instances loaded "
              f"({N_WORKERS} concurrent workers)", flush=True)
        for model in a.models:
            print(f"  model={model}", flush=True)
            t0 = time.time()
            skipped = []
            done = 0
            # PER-INSTANCE HARD TIMEOUT (not just as_completed with no bound):
            # a pathological model-generated SQL query executed with no
            # SQLite progress handler can run for an unbounded time (the
            # sqlite3.connect(timeout=...) parameter only bounds LOCK-WAIT
            # time, not query execution time -- a real gotcha, confirmed the
            # hard way: this exact scenario stalled a real collection run
            # for 4+ hours on a single hung instance while every other
            # future had already finished, because as_completed() with no
            # timeout cannot skip ahead of one that never completes).
            # Threads that hang past the timeout are abandoned (Python
            # cannot forcibly kill a thread) but the BATCH no longer waits
            # on them forever; any records they eventually produce are
            # simply never collected.
            PER_INSTANCE_TIMEOUT_S = int(os.environ.get("SOUNDVER_INSTANCE_TIMEOUT", "180"))
            # NOT a `with` block deliberately: ThreadPoolExecutor.__exit__
            # calls shutdown(wait=True), which blocks until EVERY submitted
            # future finishes -- including an abandoned, still-hung one --
            # silently defeating the whole point of the timeout logic below
            # (confirmed the hard way: with a `with` block here, a
            # deliberately-hung test future still made the block wait
            # forever even though the loop below had already "moved on").
            # shutdown(wait=False) below lets the process continue without
            # waiting for a hung thread; Python cannot forcibly kill it, so
            # it leaks until process exit, but it no longer blocks progress.
            pool = concurrent.futures.ThreadPoolExecutor(max_workers=N_WORKERS)
            futures = {pool.submit(process_one, a.task, model, seed, item,
                                   a.prompt_id): item for item in items}
            pending = set(futures)
            while pending:
                finished, pending = concurrent.futures.wait(
                    pending, timeout=PER_INSTANCE_TIMEOUT_S,
                    return_when=concurrent.futures.FIRST_COMPLETED)
                if not finished:
                    # nothing finished within the timeout window at all --
                    # everything still pending is presumed hung.
                    for fut in pending:
                        it = futures[fut]
                        skipped.append((it["instance_id"], "hard timeout: "
                                       f"no future completed within "
                                       f"{PER_INSTANCE_TIMEOUT_S}s"))
                        done += 1
                    break
                for fut in finished:
                    recs, prov_entries, err = fut.result()
                    if err is not None:
                        skipped.append(err)
                    else:
                        records.extend(recs)
                        if prov_entries:
                            with provider_log_lock:
                                for pe in prov_entries:
                                    provider_log.write(json.dumps(pe) + "\n")
                                provider_log.flush()
                    done += 1
                    if done % 25 == 0:
                        print(f"    {done}/{len(items)} instances, "
                              f"{len(records)} records so far, "
                              f"{time.time() - t0:.0f}s elapsed", flush=True)
            pool.shutdown(wait=False)

            if skipped:
                print(f"    skipped {len(skipped)}/{len(items)}: "
                      f"{skipped[:5]}{'...' if len(skipped) > 5 else ''}")
            write(records, a.out)
            print(f"  model={model} done, {len(records)} total records "
                  f"written to {a.out}", flush=True)

    provider_log.close()
    print(f"\nDone. {len(records)} records written to {a.out}.")
    if os.path.getsize(provider_log_path) > 0:
        print(f"Serving-provider log for un-pinned Llama models: {provider_log_path}")
    else:
        os.remove(provider_log_path)
    return 0


if __name__ == "__main__":
    code = main()
    # os._exit, not sys.exit: ThreadPoolExecutor worker threads are NOT
    # daemon threads, so the interpreter normally blocks at process exit
    # until every thread finishes -- including one abandoned as "hung"
    # by the per-instance timeout above (shutdown(wait=False) only stops
    # the executor from waiting, it does not detach the threads). All
    # real work (records written, files closed) is already done by this
    # point, so it is safe to skip Python's normal thread-join-on-exit
    # here rather than have the whole process hang anyway on a single
    # abandoned thread from the very last batch.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)
