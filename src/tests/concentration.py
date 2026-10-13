import json, glob
from collections import Counter
import numpy as np
from certver.admit import load_examples
from certver.curve import verdict_matrix, load_candidates, conj
for task, mine in (("sql", "tau=0.01"), ("ie", "tau=0.02")):
    sel = {r["selection"]: r["checks"] for r in json.load(open(f"out/curve_{task}_pilot_f1.json"))["results"]}
    ex = load_examples(task, f"data/pools/pool_{task}_certify_seed0.jsonl")
    ids = set(sel[mine]) | set(sel["f1_baseline"]) | set(sel["handwritten"])
    names = {json.loads(l)["id"]: json.loads(l)["name"] for p in glob.glob(f"out/candidates/{task}_*.jsonl") for l in open(p)}
    V = verdict_matrix(task, [c for c in load_candidates(task, [f"out/candidates/{task}_*.jsonl"], ex) if c["id"] in ids], ex)
    print(f"== {task} (split B)")
    for name in ("handwritten", mine, "f1_baseline"):
        acc = conj(V, sel[name], len(ex))
        by = {}
        for e, a in zip(ex, acc):
            if e["correct"]:
                by.setdefault(e["instance_id"], []).append(a)
        n_inst = len(by)
        wiped = sum(1 for v in by.values() if not any(v))
        partial = sum(1 for v in by.values() if any(v) and not all(v))
        blame = Counter()
        for i, (e, a) in enumerate(zip(ex, acc)):
            if e["correct"] and not a:
                for c in sel[name]:
                    if not V[c][i]: blame[names.get(c, c)] += 1
        print(f"  {name:12s} instances with a correct output: {n_inst}; ALL correct outputs rejected: {wiped}; some rejected: {partial}")
        print(f"      false rejections by check: {dict(blame.most_common(4))}")
