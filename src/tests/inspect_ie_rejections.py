import json, glob
import numpy as np
from certver.admit import load_examples
from certver.curve import verdict_matrix, load_candidates, conj
r = json.load(open("out/curve_ie_AB.json"))
row = [x for x in r["results"] if x["selection"] == "tau=0"][0]
names = {}
for p in glob.glob("out/candidates/ie_*.jsonl"):
    for l in open(p):
        c = json.loads(l); names[c["id"]] = c["name"]
print("tau=0 checks:", [names.get(c, c) for c in row["checks"]])
exB = load_examples("ie", "data/pools/pool_ie_certify_seed0.jsonl")
cands = [c for c in load_candidates("ie", ["out/candidates/ie_*.jsonl"], exB) if c["id"] in row["checks"]]
V = verdict_matrix("ie", cands, exB)
for i, e in enumerate(exB):
    if e["correct"] and not all(V[c][i] for c in row["checks"]):
        failed = [names.get(c, c) for c in row["checks"] if not V[c][i]]
        print(f"[{e['model'][:10]}] failed={failed}\n   text: {e['ctx']['text'][:150]}\n   out:  {e['raw'][:200]}")
