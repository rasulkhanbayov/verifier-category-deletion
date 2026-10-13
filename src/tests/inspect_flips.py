import json, random, sqlite3
from soundver.checks import sql_extract
items = {json.loads(l)["instance_id"]: json.loads(l) for l in open("data/pools/pool_sql_admit_seed0.items.jsonl")}
rows = [json.loads(l) for l in open("data/pools/pool_sql_admit_seed0.jsonl")]
random.seed(1)
for old, new in ((True, False), (False, True)):
    fl = [r for r in rows if r["correct_v2label"] == old and r["correct"] == new]
    print(f"===== old={old} -> new={new}: {len(fl)}")
    for r in random.sample(fl, 4):
        it = items[r["instance_id"]]
        con = sqlite3.connect(it["db_path"]); con.text_factory = lambda b: b.decode("utf-8", "replace")
        g = con.execute(it["gold_sql"]).fetchall()
        try: p = con.execute(sql_extract(r["raw"])).fetchall()
        except Exception as e: p = f"ERR {e}"
        print("Q:", it["question"][:100]); print("  gold:", it["gold_sql"][:120]); print("  pred:", sql_extract(r["raw"])[:120])
        print("  orig gold:", str(g[:4])[:120], f"(n={len(g)})"); print("  orig pred:", str(p[:4])[:120], f"(n={len(p) if isinstance(p, list) else '-'})")
