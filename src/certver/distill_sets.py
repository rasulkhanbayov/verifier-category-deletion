"""
certver.distill_sets -- build training sets by filtering a fresh output pool.

  python -m certver.distill_sets --task ie --pool data/distill/pool_ie_distill_seed0.jsonl \
      --curve out/curve_ie_inst_multi.json --out-dir data/distill

The distill pool's inputs are disjoint from the proposal/admit/certify splits,
so nothing here was used to select or certify a check. For each condition we
keep the outputs the verifier accepts, de-duplicated per input:
  none          every output
  handwritten   version3's hand-written stack
  f1_baseline   F1-selected synthesised verifier (uncertified)
  certified     the certified synthesised verifier (report's pre-specified rule)
  oracle        only outputs the label calls correct (upper bound; uses gold)
Writes sft_{condition}.jsonl ({instance_id, prompt, completion}) and stats.json.
"""
from __future__ import annotations
import argparse, json, os, sys
import numpy as np

from soundver import generate as g
from .admit import load_examples
from .curve import verdict_matrix, load_candidates, conj
from .filtering import subgroups
from .report import pick_certified


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", required=True)
    ap.add_argument("--pool", required=True)
    ap.add_argument("--curve", required=True)
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args(argv)

    curve = json.load(open(a.curve))["results"]
    cname, _ = pick_certified(curve)
    sel = {r["selection"]: r["checks"] for r in curve}
    S = {"handwritten": sel["handwritten"], "f1_baseline": sel["f1_baseline"], "certified": sel[cname]}
    items = {json.loads(l)["instance_id"]: json.loads(l)
             for l in open(a.pool.replace(".jsonl", ".items.jsonl")) if l.strip()}
    ex = [e for e in load_examples(a.task, a.pool) if e["model"] != "gold"]
    ids = {c for v in S.values() for c in v}
    V = verdict_matrix(a.task, [c for c in load_candidates(a.task, [f"out/candidates/{a.task}_*.jsonl"], ex)
                                if c["id"] in ids], ex)
    masks = {k: conj(V, v, len(ex)) for k, v in S.items()}
    masks["none"] = np.ones(len(ex), dtype=bool)
    masks["oracle"] = np.array([e["correct"] for e in ex])

    stats = {"certified_selection": cname}
    for cond, m in masks.items():
        seen, rows = set(), []
        n_cor = 0
        sub_cor = {}
        for e, keep in zip(ex, m):
            if not keep:
                continue
            key = (e["instance_id"], " ".join(e["raw"].split()))
            if key in seen:
                continue
            seen.add(key)
            it = items[e["instance_id"]]
            rows.append({"instance_id": e["instance_id"],
                         "prompt": g.PROMPTS[a.task](it, "base"), "completion": e["raw"].strip()})
            n_cor += int(e["correct"])
            if e["correct"]:
                for sg in subgroups(a.task, it):
                    sub_cor[sg] = sub_cor.get(sg, 0) + 1
        with open(os.path.join(a.out_dir, f"sft_{a.task}_{cond}.jsonl"), "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        stats[cond] = {"examples": len(rows), "correct": n_cor,
                       "precision": n_cor / max(1, len(rows)),
                       "inputs_covered": len({r["instance_id"] for r in rows}),
                       "correct_examples_by_subgroup": sub_cor}
        print(f"{cond:12s} examples={len(rows):6d} precision={n_cor / max(1, len(rows)):.3f} "
              f"correct has_else={sub_cor.get('has_else_type', 0)} inputs={stats[cond]['inputs_covered']}")
    json.dump(stats, open(os.path.join(a.out_dir, f"sft_{a.task}_stats.json"), "w"), indent=1)
    # the test inputs the students will be evaluated on (all draws, de-duplicated)
    test = {}
    for s in (0, 1, 2):
        for l in open(f"data/test/pool_{a.task}_test_seed{s}.items.jsonl"):
            it = json.loads(l)
            test[it["instance_id"]] = {"instance_id": it["instance_id"],
                                       "prompt": g.PROMPTS[a.task](it if a.task != "sql" else
                                                                   {**it, "schema": {t: set(c) for t, c in it["schema"].items()}}, "base")}
    with open(os.path.join(a.out_dir, f"eval_{a.task}_prompts.jsonl"), "w") as f:
        for r in test.values():
            f.write(json.dumps(r) + "\n")
    print(f"{len(test)} unique test inputs written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
