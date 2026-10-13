"""
certver.spider_distill -- database perturbation used by the SQL label.

Copied verbatim from version2's spider_task.py (archive/version2/spider_task.py:
_connect and _make_distilled_copy) so that the label does not depend on the
archive. Behaviour is unchanged: the perturbed copies are identical.
"""
import os
import random
import sqlite3


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
