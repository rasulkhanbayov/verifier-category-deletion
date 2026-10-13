import concurrent.futures, time
from certver.data import load_split
from certver.sandbox import run_check, strip_gold

if __name__ == "__main__":
    items = load_split("sql", "test", 20, 0)
    ex = [(it["gold_sql"], strip_gold({**it, "schema": {t: sorted(c) for t, c in it["schema"].items()}}))
          for it in items]
    srcs = ["def check(output, ctx):\n    return 'select' in output.lower()",
            "def check(output, ctx):\n    execute(extract_sql(output)); return True",
            "def check(output, ctx):\n    while True: pass"] * 3
    t = time.time()
    with concurrent.futures.ThreadPoolExecutor(8) as p:
        res = list(p.map(lambda s: run_check(s, ex, "sql"), srcs))
    print([(sum(r["verdicts"]), r["errors"]) for r in res], f"{time.time() - t:.1f}s")
