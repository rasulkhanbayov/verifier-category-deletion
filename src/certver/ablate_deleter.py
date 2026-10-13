"""
certver.ablate_deleter -- build the distillation set for "F1 selection minus
the deleting check" (adversarial audit A1), with the same construction as
certver.distill_sets (filter the distillation pool, de-duplicate per input).

  python -m certver.ablate_deleter --out data/distill/ablate/sft_ie_f1_minus_deleter.jsonl
"""
from __future__ import annotations
import argparse, json, sys
from .admit import load_examples
from .curve import verdict_matrix, load_candidates, conj
from soundver import generate as g


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True)
    ap.add_argument("--deleter", default="ie-r0-84f7d14832")
    ap.add_argument("--selections", default="out/distill_ie_selections_pre_repair.json",
                    help="the selections the distillation sets were built from (pre-repair-round pool)")
    a = ap.parse_args(argv)
    task, pool = "ie", "data/distill/pool_ie_distill_seed0.jsonl"
    f1 = json.load(open(a.selections))["f1_pre_repair"]; assert a.deleter in f1
    S = [c for c in f1 if c != a.deleter]
    items = {json.loads(l)["instance_id"]: json.loads(l) for l in open(pool.replace(".jsonl", ".items.jsonl")) if l.strip()}
    ex = [e for e in load_examples(task, pool) if e["model"] != "gold"]
    V = verdict_matrix(task, [c for c in load_candidates(task, ["out/candidates/ie_*.jsonl"], ex) if c["id"] in set(f1)], ex)
    def build(ids):
        m = conj(V, ids, len(ex)); seen, rows = set(), []
        for e, keep in zip(ex, m):
            if not keep:
                continue
            key = (e["instance_id"], " ".join(e["raw"].split()))
            if key in seen:
                continue
            seen.add(key)
            rows.append({"instance_id": e["instance_id"], "prompt": g.PROMPTS[task](items[e["instance_id"]], "base"),
                         "completion": e["raw"].strip()})
        return rows
    full = build(f1)
    n_ref = sum(1 for l in open("data/distill/sft_ie_f1_baseline.jsonl") if l.strip())
    print(f"sanity: rebuilt full F1 set {len(full)} rows vs saved {n_ref}")
    rows = build(S)
    with open(a.out, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(f"F1 checks {len(f1)}; F1 minus deleter: {len(rows)} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
