"""
certver.sqllabel -- the SQL correctness label used in the paper.

version2's test_suite_accuracy (which version3 used) compares queries only on
crude 70%-row subsamples of each database, as frozensets. Measured defects:
a query returning nothing can match a gold query whose join rows were
subsampled away, and frozensets ignore duplicates and row order. Its own
docstring says it "should be upgraded before results are reported".

This label: CORRECT iff the prediction's result equals gold's on the ORIGINAL
database AND on every distilled copy, where "equals" is
  - a multiset comparison (duplicates count),
  - order-sensitive only if the gold query has ORDER BY,
  - up to a permutation of result columns (as in Spider's official eval).
A prediction that fails to execute is incorrect. Instances whose gold query
fails on the original database are unusable (raise GoldError).
"""
from __future__ import annotations
import itertools, os, re, sqlite3, sys, time
from collections import Counter

from .spider_distill import _make_distilled_copy

TIMEOUT_S = 5
N_DISTILLED = 3
CACHE = "/tmp/soundver_distilled"


class GoldError(ValueError):
    pass


def _run(db: str, q: str):
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.text_factory = lambda b: b.decode("utf-8", errors="replace")
    deadline = time.monotonic() + TIMEOUT_S
    con.set_progress_handler(lambda: int(time.monotonic() > deadline), 10000)
    try:
        return con.execute(q).fetchall()
    finally:
        con.close()


def _norm(v):
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def _equal(gold, pred, ordered: bool) -> bool:
    if len(gold) != len(pred):
        return False
    if not gold:
        return True
    ng, npd = len(gold[0]), len(pred[0])
    if ng != npd:
        return False
    g = [tuple(_norm(x) for x in r) for r in gold]
    p = [tuple(_norm(x) for x in r) for r in pred]
    perms = itertools.permutations(range(npd)) if npd <= 6 else [tuple(range(npd))]
    for perm in perms:
        pp = [tuple(r[i] for i in perm) for r in p]
        if (pp == g) if ordered else (Counter(pp) == Counter(g)):
            return True
    return False


def _dbs(db_path: str):
    os.makedirs(CACHE, exist_ok=True)
    db_id = os.path.splitext(os.path.basename(db_path))[0]
    out = [db_path]
    for s in range(N_DISTILLED):
        d = os.path.join(CACHE, f"{db_id}_{s}.sqlite")
        if not os.path.exists(d):
            _make_distilled_copy(db_path, d, seed=s)
        out.append(d)
    return out


def sql_correct(pred: str, gold: str, db_path: str) -> bool:
    from soundver.generate import resolve_db_path
    db_path = resolve_db_path(db_path)
    ordered = bool(re.search(r"\border\s+by\b", gold, re.IGNORECASE))
    for i, db in enumerate(_dbs(db_path)):
        try:
            g = _run(db, gold)
        except Exception as e:  # noqa: BLE001
            if i == 0:
                raise GoldError(f"gold fails on original DB: {e}") from e
            continue  # a distilled copy gold cannot run on carries no information
        try:
            p = _run(db, pred)
        except Exception:  # noqa: BLE001
            return False
        if not _equal(g, p, ordered):
            return False
    return True
