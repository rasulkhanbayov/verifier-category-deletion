"""
certver.sandbox -- run LLM-written candidate checks on pooled outputs.

A candidate check is Python source defining

    def check(output: str, ctx: dict) -> bool

`output` is the model's raw text; `ctx` is the instance context WITHOUT any
gold field (a check that could see gold would not be a label-free verifier).
For SQL, `ctx` also carries `schema` ({table: [columns]}) and the check may
call `execute(sql)` (read-only, row-capped, time-limited) and `extract_sql(raw)`.

Fail-closed: an exception, a timeout or a non-bool return counts as REJECT.
A buggy check therefore shows up as unsound at admission rather than passing
silently.

This guards against accidents in LLM-written code (infinite loops, imports
of os/subprocess, file access), not against a determined adversary: imports
are allow-listed and dangerous names are refused by AST inspection, and the
code runs in a separate process with CPU, memory and wall-clock limits.
"""
from __future__ import annotations
import ast, json, multiprocessing as mp, os

ALLOWED_IMPORTS = {"re", "json", "math", "string", "collections", "itertools",
                   "unicodedata", "functools", "sqlglot", "difflib"}
FORBIDDEN_NAMES = {"open", "exec", "eval", "compile", "__import__", "globals",
                   "locals", "vars", "getattr", "setattr", "delattr", "input",
                   "breakpoint", "exit", "quit", "memoryview"}
GOLD_FIELDS = {"gold_sql", "gold", "gold_segments", "gold_solution", "gold_answer", "gold_call"}
PER_CALL_TIMEOUT_S = 2
MAX_TIMEOUTS = 3  # after this many, reject everything left: the check is unusable
MEMORY_LIMIT_BYTES = 16 * 1024 ** 3  # virtual address space; numeric libraries reserve a lot of it


class UnsafeCheck(ValueError):
    pass


def validate_source(src: str) -> None:
    """Static refusal of anything outside the allow-list. Raises UnsafeCheck."""
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        raise UnsafeCheck(f"syntax error: {e}") from e
    has_check = False
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            mods = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            for m in mods:
                if m.split(".")[0] not in ALLOWED_IMPORTS:
                    raise UnsafeCheck(f"import of {m!r} not allowed")
        elif isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            raise UnsafeCheck(f"use of {node.id!r} not allowed")
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise UnsafeCheck(f"dunder attribute {node.attr!r} not allowed")
        elif isinstance(node, ast.FunctionDef) and node.name == "check":
            has_check = True
    if not has_check:
        raise UnsafeCheck("no function named `check`")


def strip_gold(ctx: dict) -> dict:
    return {k: v for k, v in ctx.items() if k not in GOLD_FIELDS and k != "conn"}


def _parse_ie(raw: str):
    """Same parsing the IE label and version3's checks use; None if unparseable."""
    from soundver.generate import _ie_extract_json
    from soundver.checks import ie_parses
    return ie_parses(_ie_extract_json(raw))


def _segments(raw: str) -> list:
    """Same segmentation parsing the morphology label uses."""
    return [s.strip() for s in raw.strip().split("+") if s.strip()]


def _worker(src: str, examples: list, task: str, out_q) -> None:
    import resource, signal, sqlite3
    resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT_BYTES, MEMORY_LIMIT_BYTES))
    from soundver.checks import sql_extract

    class _Timeout(Exception):
        pass

    def _alarm(*_):
        raise _Timeout()
    signal.signal(signal.SIGALRM, _alarm)

    ns: dict = {}
    try:
        exec(compile(src, "<check>", "exec"), ns)  # noqa: S102 -- validated above
        fn = ns["check"]
    except Exception as e:  # noqa: BLE001
        out_q.put({"error": f"load failed: {e!r}"[:300]})
        return

    verdicts, errors, timeouts = [], 0, 0
    conns: dict = {}
    for raw, ctx in examples:
        if timeouts >= MAX_TIMEOUTS:
            verdicts.append(False)
            errors += 1
            continue
        helpers = {}
        if task == "sql":
            from soundver.generate import resolve_db_path
            db = resolve_db_path(ctx.get("db_path"))

            def execute(q, _db=db):
                import time as _t
                if _db not in conns:
                    c = sqlite3.connect(f"file:{_db}?mode=ro", uri=True)
                    c.text_factory = lambda b: b.decode("utf-8", errors="replace")
                    conns[_db] = c
                deadline = _t.monotonic() + PER_CALL_TIMEOUT_S
                # signal.alarm cannot interrupt a running sqlite C call; this can
                conns[_db].set_progress_handler(lambda: int(_t.monotonic() > deadline), 10000)
                return conns[_db].execute(q).fetchmany(200)
            helpers = {"execute": execute, "extract_sql": sql_extract}
        elif task in ("ie", "fewnerd"):
            helpers = {"parse_json": _parse_ie}
        elif task == "fc":
            from soundver.generate import fc_parse_call
            helpers = {"parse_call": fc_parse_call}
        elif task == "morph":
            helpers = {"segments": _segments}
        elif task == "math":
            from soundver.generate import math_final_answer
            helpers = {"final_answer": math_final_answer}
        ns.update(helpers)
        signal.alarm(PER_CALL_TIMEOUT_S)
        try:
            v = fn(raw, dict(ctx))
            verdicts.append(v if isinstance(v, bool) else False)
        except _Timeout:
            verdicts.append(False)
            errors += 1
            timeouts += 1
        except BaseException:  # noqa: BLE001 -- fail closed
            verdicts.append(False)
            errors += 1
        finally:
            signal.alarm(0)
    out_q.put({"verdicts": verdicts, "errors": errors,
               "aborted": timeouts >= MAX_TIMEOUTS})


def run_check(src: str, examples: list, task: str, wall_timeout_s: float | None = None) -> dict:
    """examples: list of (raw_output, ctx) with gold already stripped.
    Returns {"verdicts": [bool...], "errors": int} or {"error": str}."""
    validate_source(src)
    for _, ctx in examples:
        if GOLD_FIELDS & set(ctx):
            raise ValueError("ctx contains a gold field; call strip_gold first")
    wall = wall_timeout_s or (PER_CALL_TIMEOUT_S * len(examples) + 30)
    ctx_mp = mp.get_context("forkserver")
    q = ctx_mp.Queue()
    p = ctx_mp.Process(target=_worker, args=(src, examples, task, q))
    p.start()
    import time as _time, queue as _queue
    deadline = _time.monotonic() + wall
    res = None
    while res is None:
        try:
            res = q.get(timeout=5)
        except _queue.Empty:
            if not p.is_alive():
                res = {"error": f"worker died (exit code {p.exitcode})"}
            elif _time.monotonic() > deadline:
                res = {"error": f"wall timeout {wall:.0f}s"}
    p.join(5)
    if p.is_alive():
        p.kill()
    return res


def load_pool(path: str, items_path: str):
    """Pair each pooled output with its gold-stripped context.
    Returns list of (row, ctx) where row keeps `correct` for admission."""
    items = {}
    with open(items_path) as f:
        for line in f:
            if line.strip():
                d = json.loads(line)
                items[d["instance_id"]] = strip_gold(d)
    out = []
    with open(path) as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                out.append((r, items[r["instance_id"]]))
    return out
