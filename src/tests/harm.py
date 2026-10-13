import json
import numpy as np
from certver.admit import load_examples
from certver.curve import verdict_matrix, load_candidates, conj
from certver.ci import per_instance
for task, mine in (("sql", "tau=0.01"), ("ie", "tau=0.02")):
    sel = {r["selection"]: r["checks"] for r in json.load(open(f"out/curve_{task}_pilot_f1.json"))["results"]}
    ex = [e for e in load_examples(task, f"data/pilot/pool_{task}_test_seed0.jsonl") if e["model"] != "gold"]
    ids = set(sel[mine]) | set(sel["f1_baseline"]) | set(sel["handwritten"])
    V = verdict_matrix(task, [c for c in load_candidates(task, [f"out/candidates/{task}_*.jsonl"], ex) if c["id"] in ids], ex)
    print(f"== {task}: expected # instances made worse / better than base (N=32), out of 100 per model")
    for name in ("handwritten", mine, "f1_baseline"):
        P = per_instance(ex, conj(V, sel[name], len(ex)), 32)
        for m in sorted({k[0] for k in P}):
            vals = [P[k] for k in P if k[0] == m]
            worse = sum(b - v for v, b in vals if v < b); better = sum(v - b for v, b in vals if v > b)
            print(f"  {name:12s} {m.split('/')[-1][:24]:24s} worse={worse:5.2f} better={better:5.2f}")
