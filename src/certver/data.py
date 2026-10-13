"""
certver.data -- instance loaders for the four disjoint splits.

  proposal : training instances shown to the check-proposer LLM
  admit    : split A, decides which candidate checks are admitted
  certify  : split B, re-certifies the conjunction (never used for selection)
  distill  : fresh training inputs for the downstream data-filtering
             experiment (never used for selection or certification)
  test     : the version3 evaluation split (Spider dev, CoNLL test,
             SIGMORPHON test), loaded through soundver's own loaders so the
             test instances match version3 exactly
  fresh    : test-set instances never used in test draws 0-2 (which were
             looked at during development); for the final, untouched
             evaluation (v4.1 plan, review item M4)

Proposal/admit/certify are disjoint slices of ONE seeded shuffle of the
task's training set, so membership is deterministic and cannot overlap.
"""
from __future__ import annotations
import json, os, random

from soundver import generate as _g

SPLIT_SEED = 20261008
SPLIT_SIZES = {"proposal": 50, "admit": 1000, "certify": 1000, "distill": 2000}
SPIDER_TRAIN = os.path.join(_g.DATA_ROOT, "spider_data", "spider_data", "train_spider.json")


def _spider_schemas():
    with open(_g.SPIDER_TABLES) as f:
        tables = json.load(f)
    schemas = {}
    for entry in tables:
        names = [t.lower() for t in entry["table_names_original"]]
        cols = {t: set() for t in names}
        for (ti, cn), _ in zip(entry["column_names_original"], entry["column_types"]):
            if ti != -1:
                cols[names[ti]].add(cn.lower())
        schemas[entry["db_id"]] = cols
    return schemas


def _train_sql():
    with open(SPIDER_TRAIN) as f:
        ds = json.load(f)
    schemas = _spider_schemas()
    out = []
    for i, ex in enumerate(ds):
        db_path = os.path.join(_g.SPIDER_DB_ROOT, ex["db_id"], f"{ex['db_id']}.sqlite")
        if os.path.exists(db_path):
            out.append({"instance_id": f"sqltr-{i:05d}", "question": ex["question"],
                        "gold_sql": ex["query"], "db_id": ex["db_id"],
                        "db_path": os.path.relpath(db_path, _g.REPO_ROOT), "schema": schemas.get(ex["db_id"], {})})
    return out


def _train_ie():
    out = []
    with open(os.path.join(_g.IE_ROOT, "train.json")) as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            ex = json.loads(line)
            gold = {t: [] for t in _g.IE_ENTITY_TYPES}
            for e in ex["entity"]:
                gold.setdefault(e["entity_type"], []).append(e["entity"])
            out.append({"instance_id": f"ietr-{i:05d}", "text": ex["text"], "gold": gold})
    return out


def _train_morph():
    out = []
    with open(os.path.join(_g.MORPH_ROOT, "eng.word.train.tsv"), encoding="utf-8") as f:
        for i, line in enumerate(f):
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 2 or not parts[0]:
                continue
            segs = [m[2:] if m.startswith("@@") else m for m in parts[1].split(" ") if m]
            out.append({"instance_id": f"morphtr-{i:06d}", "surface": parts[0],
                        "gold_segments": segs})
    return out


def _train_math():
    items = _g._load_math_items(10 ** 9, 0, split="train")
    items.sort(key=lambda it: it["instance_id"])
    return [{**it, "instance_id": it["instance_id"].replace("math-", "mathtr-")} for it in items]


def _train_fewnerd():
    return sorted(_g._load_fewnerd_items(10 ** 9, 0, split="train"), key=lambda it: it["instance_id"])


def _train_fc():
    return sorted(_g._load_fc_items(10 ** 9, 0, split="train"), key=lambda it: it["instance_id"])


_TRAIN = {"sql": _train_sql, "ie": _train_ie, "morph": _train_morph, "math": _train_math,
          "fewnerd": _train_fewnerd, "fc": _train_fc}


def load_split(task: str, split: str, n: int | None = None, seed: int = 0):
    """Instances for one split. `n` truncates (for pilots); `seed` only
    matters for the test split, where it reproduces version3's draw."""
    if split == "test":
        return _g.LOADERS[task](n or 200, seed)
    if split == "fresh":
        seen = {it["instance_id"] for s in (0, 1, 2) for it in _g.LOADERS[task](200, s)}
        allit = [it for it in _g.LOADERS[task](10 ** 9, 12345) if it["instance_id"] not in seen]
        return allit[: (n or 300)]
    if split not in SPLIT_SIZES:
        raise ValueError(f"unknown split {split!r}")
    pool = _TRAIN[task]()
    random.Random(SPLIT_SEED).shuffle(pool)
    start = 0
    for name in ("proposal", "admit", "certify", "distill"):
        size = SPLIT_SIZES[name]
        if name == split:
            items = pool[start:start + size]
            return items[:n] if n else items
        start += size
