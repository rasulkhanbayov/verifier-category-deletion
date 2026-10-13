"""
soundver.records -- the per-instance record schema everything else reads.

B7 is the root cause of B2, B3 and B6: nothing in the shipped bundle lets a
number be regenerated. This module fixes the format so that it can be, and
supplies a synthetic generator so the whole harness is executable before the
real records exist.

SCHEMA. One JSON object per line. One line per (task, model, instance,
candidate). The base output is the candidate with index -1.

  task        str    "sql" | "ie" | "morph"
  model       str    e.g. "openai/gpt-4o-2024-11-20"   <- the SNAPSHOT (B9)
  seed        int
  instance_id str    stable id within the task's split
  cand_idx    int    -1 for the greedy base output, 0..N-1 for samples
  correct     bool   the task metric. MUST NOT presuppose any gate check.
  checks      dict   check name -> bool, one entry per check in the stack
  score       float  optional, the scorer's value for this candidate
  prompt_id   str    which prompt variant produced it (B8-V2); "base" default

The `correct` field is the one that decides everything. Section 6's circularity
condition applies: for SQL it must be test-suite accuracy, never execution
match; for morphology it must be gold-segmentation match, never a conjunction
with "concatenates".
"""
from __future__ import annotations
import json, gzip, io, os
from dataclasses import dataclass, field, asdict
from typing import Iterator, Sequence

CHECKS = {
    "sql":   ["parses", "schema_valid", "executes"],
    "ie":    ["parses", "required_fields", "schema_valid", "no_overlap"],
    "morph": ["no_empty_segment", "concatenates"],
}


@dataclass
class Record:
    task: str
    model: str
    seed: int
    instance_id: str
    cand_idx: int
    correct: bool
    checks: dict
    score: float | None = None
    prompt_id: str = "base"

    @property
    def is_base(self) -> bool:
        return self.cand_idx == -1

    def accepted_by(self, subset: Sequence[str]) -> bool:
        """Conjunction of the named checks. Missing check -> KeyError, loudly."""
        return all(self.checks[c] for c in subset)


def _open(path: str):
    return gzip.open(path, "rt") if path.endswith(".gz") else io.open(path, "r")


def load(path: str) -> list[Record]:
    out = []
    with _open(path) as fh:
        for ln, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"{path}:{ln}: not JSON ({e})") from e
            missing = {"task", "model", "seed", "instance_id",
                       "cand_idx", "correct", "checks"} - d.keys()
            if missing:
                raise ValueError(f"{path}:{ln}: missing fields {sorted(missing)}")
            if d["task"] not in CHECKS:
                raise ValueError(f"{path}:{ln}: unknown task {d['task']!r}")
            want = set(CHECKS[d["task"]])
            have = set(d["checks"])
            if not want <= have:
                raise ValueError(
                    f"{path}:{ln}: task {d['task']} needs checks {sorted(want)}, "
                    f"record has {sorted(have)}")
            out.append(Record(**{k: d[k] for k in
                                 ("task", "model", "seed", "instance_id",
                                  "cand_idx", "correct", "checks")},
                              score=d.get("score"),
                              prompt_id=d.get("prompt_id", "base")))
    if not out:
        raise ValueError(f"{path}: no records")
    return out


def write(records: Sequence[Record], path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    op = gzip.open if path.endswith(".gz") else io.open
    with op(path, "wt") as fh:
        for r in records:
            fh.write(json.dumps(asdict(r), sort_keys=True) + "\n")


def synthesize(task: str = "sql", model: str = "synthetic/model-v0",
               n_instances: int = 200, n_cands: int = 32, seed: int = 0,
               p0: float = 0.72, p: float = 0.73, eps: float = 0.99,
               delta: float = 0.0, prompt_id: str = "base") -> list[Record]:
    """
    Generate records with KNOWN rates so every estimator can be checked against
    ground truth. This is a smoke test, not evidence about any language model,
    and nothing it produces may appear in the paper.
    """
    import numpy as np
    rng = np.random.default_rng(seed)
    names = CHECKS[task]
    out: list[Record] = []
    for i in range(n_instances):
        iid = f"{task}-{i:05d}"
        for c in range(-1, n_cands):
            corr = bool(rng.random() < (p0 if c == -1 else p))
            # accept with prob (1-delta) if correct, eps if not; then split the
            # verdict across the stack so the LAST check is the binding one
            acc = bool(rng.random() < ((1 - delta) if corr else eps))
            chk = {nm: True for nm in names}
            if not acc:
                chk[names[rng.integers(0, len(names))]] = False
            out.append(Record(task=task, model=model, seed=seed,
                              instance_id=iid, cand_idx=c, correct=corr,
                              checks=chk, score=float(rng.normal()),
                              prompt_id=prompt_id))
    return out
