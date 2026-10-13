"""
certver.eval_distill -- score students trained on differently filtered data.

  python -m certver.eval_distill --task ie --gens data/distill/gen_ie_*.jsonl \
      --out out/distill_ie.json

For each generation file (one per training condition): exact-match accuracy
(the task label), accuracy per gold-defined subgroup, and for IE the
micro precision/recall/F1 of each entity field, so a student that never
learned the "else" field shows up as low "else" recall. Paired bootstrap CIs
(over unique test inputs) for every condition against `certified`.
"""
from __future__ import annotations
import argparse, glob, json, os, re, sys
import numpy as np

from soundver import generate as g
from soundver.checks import ie_parses
from .filtering import subgroups
from .ci import boot


def _items(task):
    items = {}
    for s in (0, 1, 2):
        for l in open(f"data/test/pool_{task}_test_seed{s}.items.jsonl"):
            it = json.loads(l)
            items[it["instance_id"]] = it
    return items


def _norm_set(vals):
    return {str(v).strip().lower() for v in (vals if isinstance(vals, list) else [vals])
            if isinstance(v, (str, int, float))}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", required=True)
    ap.add_argument("--gens", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    items = _items(a.task)
    files = sorted(p for pat in a.gens for p in glob.glob(pat))
    per = {}
    res = {}
    for f in files:
        cond = re.sub(r"^gen_[a-z]+_|\.jsonl$", "", os.path.basename(f))
        gens = {json.loads(l)["instance_id"]: json.loads(l)["output"] for l in open(f) if l.strip()}
        cor, sub = {}, {}
        fields = {}
        for iid, out in gens.items():
            it = items[iid]
            if a.task in ("ie", "fewnerd"):
                obj = ie_parses(g._ie_extract_json(out))
                types = g.IE_ENTITY_TYPES if a.task == "ie" else g.FEWNERD_TYPES
                c = (g._field_value_match(obj if isinstance(obj, dict) else None, it["gold"]) if a.task == "ie"
                     else g._fewnerd_match(obj, it["gold"]))
                for t in types:
                    pred = _norm_set(obj.get(t, [])) if isinstance(obj, dict) else set()
                    gold = _norm_set(it["gold"].get(t, []))
                    st = fields.setdefault(t, [0, 0, 0])
                    st[0] += len(pred & gold); st[1] += len(pred); st[2] += len(gold)
            else:
                c = g._label_correct(a.task, it, out, None)
            cor[iid] = float(c)
            for sg in subgroups(a.task, it) + ["ALL"]:
                sub.setdefault(sg, []).append(float(c))
        per[cond] = cor
        res[cond] = {"n": len(cor), "accuracy": float(np.mean(list(cor.values()))),
                     "subgroups": {k: {"n": len(v), "acc": float(np.mean(v))} for k, v in sub.items()},
                     "fields": {t: {"precision": tp / max(1, np_), "recall": tp / max(1, ng),
                                    "f1": 2 * tp / max(1, np_ + ng)} for t, (tp, np_, ng) in fields.items()}}
    if "certified" in per:
        for cond in per:
            if cond == "certified":
                continue
            keys = sorted(set(per[cond]) & set(per["certified"]))
            d = np.array([per["certified"][k] - per[cond][k] for k in keys])
            res[cond]["certified_minus_this"] = boot(d)
            sk = [k for k in keys if "has_else_type" in subgroups(a.task, items[k])] if a.task == "ie" else []
            if sk:
                res[cond]["certified_minus_this_has_else"] = boot(
                    np.array([per["certified"][k] - per[cond][k] for k in sk]))
    for cond, r in res.items():
        line = f"{cond:12s} n={r['n']} acc={100 * r['accuracy']:.1f}"
        if "has_else_type" in r["subgroups"]:
            line += f" has_else acc={100 * r['subgroups']['has_else_type']['acc']:.1f} (n={r['subgroups']['has_else_type']['n']})"
        if "else" in r.get("fields", {}):
            e = r["fields"]["else"]
            line += f" else P/R={e['precision']:.3f}/{e['recall']:.3f}"
        if "certified_minus_this" in r:
            t = r["certified_minus_this"]
            line += f" | cert-this {100*t[0]:+.1f} [{100*t[1]:+.1f},{100*t[2]:+.1f}]"
        if "certified_minus_this_has_else" in r:
            t = r["certified_minus_this_has_else"]
            line += f" has_else {100*t[0]:+.1f} [{100*t[1]:+.1f},{100*t[2]:+.1f}]"
        print(line)
    json.dump(res, open(a.out, "w"), indent=1, default=float)
    return 0


if __name__ == "__main__":
    sys.exit(main())
