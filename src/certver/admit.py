"""
certver.admit -- admission (split A), certification (split B), evaluation (test).

  python -m certver.admit admit   --task sql --candidates out/candidates/sql_round0.jsonl \
                                  --pool data/pools/pool_sql_admit_seed0.jsonl --out out/admit_sql_round0.json
  python -m certver.admit certify --task sql --admitted out/admit_sql_round0.json \
                                  --pool data/pools/pool_sql_certify_seed0.jsonl --out out/certify_sql.json
  python -m certver.admit evaluate --task sql --admitted out/admit_sql_round0.json \
                                  --pool data/pilot/pool_sql_test_seed0.jsonl --out out/eval_sql.json

Correct examples for soundness are every pooled output the admissible label
calls correct PLUS the gold output of every instance (written as a model
would write it). A check is admitted iff it rejects none of them and rejects
at least one incorrect output. version3's hand-written checks (stored per row
in `checks`) go through the same rule as candidates named `hw:<check>`.
"""
from __future__ import annotations
import argparse, concurrent.futures, json, os, sys

from soundver.records import Record
from soundver.rates import estimate
from .sandbox import run_check, strip_gold

WORKERS = int(os.environ.get("CERTVER_ADMIT_WORKERS", "8"))


def _gold_raw(task: str, item: dict) -> str:
    if task == "sql":
        return item["gold_sql"]
    if task == "ie":
        return json.dumps(item["gold"])
    if task == "math":
        return item["gold_solution"]
    if task == "fewnerd":
        return json.dumps(item["gold"])
    if task == "fc":
        return json.dumps(item["gold_call"])
    return "+".join(item["gold_segments"])


def load_examples(task: str, pool_path: str):
    """List of dicts: raw, ctx (gold-stripped), correct, checks (hand-written,
    None for gold rows), model, instance_id, cand_idx."""
    items_path = pool_path.replace(".jsonl", ".items.jsonl")
    items = {}
    with open(items_path) as f:
        for line in f:
            if line.strip():
                d = json.loads(line)
                items[d["instance_id"]] = d
    ex, seen = [], set()
    with open(pool_path) as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            it = items[r["instance_id"]]
            ex.append({"raw": r["raw"], "ctx": strip_gold(it), "correct": r["correct"],
                       "checks": r["checks"], "model": r["model"], "seed": r["seed"],
                       "instance_id": r["instance_id"], "cand_idx": r["cand_idx"]})
            seen.add(r["instance_id"])
    for iid in sorted(seen):
        it = items[iid]
        ex.append({"raw": _gold_raw(task, it), "ctx": strip_gold(it), "correct": True,
                   "checks": None, "model": "gold", "seed": -1,
                   "instance_id": iid, "cand_idx": -2})
    return ex


def _hw_names(examples):
    for e in examples:
        if e["checks"]:
            return sorted(e["checks"])
    return []


def verdicts_for(task: str, cand: dict, examples) -> list | None:
    """Per-example accept/reject. Hand-written checks read stored verdicts;
    gold rows have none stored, so hand-written checks are re-run on gold
    via soundver's scorer."""
    if cand["id"].startswith("hw:"):
        name = cand["id"][3:]
        from soundver import generate as g
        out = []
        for e in examples:
            if e["checks"] is not None:
                out.append(bool(e["checks"][name]))
            else:
                ctx = dict(e["ctx"])
                if task == "sql":
                    import sqlite3
                    conn = sqlite3.connect(g.resolve_db_path(ctx["db_path"]), timeout=5.0)
                    ctx["conn"] = conn
                    ctx["schema"] = {t: set(c) for t, c in ctx["schema"].items()}
                    try:
                        out.append(bool(g.score_checks(task, e["raw"], ctx)[0][name]))
                    finally:
                        conn.close()
                else:
                    out.append(bool(g.score_checks(task, e["raw"], ctx)[0][name]))
        return out
    res = run_check(cand["source"], [(e["raw"], e["ctx"]) for e in examples], task)
    return res.get("verdicts")


def _all_verdicts(task, cands, examples):
    out = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futs = {pool.submit(verdicts_for, task, c, examples): c["id"] for c in cands}
        for fu in concurrent.futures.as_completed(futs):
            out[futs[fu]] = fu.result()
    return out


def _stats(v, examples):
    rc = [i for i, e in enumerate(examples) if e["correct"] and not v[i]]
    n_c = sum(e["correct"] for e in examples)
    inc = [i for i, e in enumerate(examples) if not e["correct"]]
    caught = sum(1 for i in inc if not v[i])
    return {"n_correct": n_c, "rejected_correct": len(rc),
            "rejected_correct_gold": sum(examples[i]["model"] == "gold" for i in rc),
            "n_incorrect": len(inc), "caught_incorrect": caught,
            "catch_rate": caught / len(inc) if inc else float("nan")}, rc


def _upper_bound(k: int, n: int) -> float:
    if n == 0:
        return float("nan")
    if k == 0:
        return 3.0 / n
    from scipy.stats import beta
    return float(beta.ppf(0.95, k + 1, n - k))


def _load_candidates(task, paths, examples):
    cands = []
    for p in paths:
        with open(p) as f:
            cands += [json.loads(l) for l in f if l.strip()]
    cands += [{"id": f"hw:{n}", "name": f"hw:{n}", "source": None, "rationale": "version3 hand-written"}
              for n in _hw_names(examples)]
    return cands


def cmd_admit(a):
    examples = load_examples(a.task, a.pool)
    cands = _load_candidates(a.task, a.candidates, examples)
    print(f"{len(cands)} candidates x {len(examples)} examples "
          f"({sum(e['correct'] for e in examples)} correct incl. gold)", flush=True)
    V = _all_verdicts(a.task, cands, examples)
    report, admitted, feedback = [], [], []
    for c in cands:
        v = V[c["id"]]
        if v is None:
            report.append({"id": c["id"], "name": c["name"], "status": "load_error"})
            continue
        s, rc = _stats(v, examples)
        status = ("admitted" if s["rejected_correct"] == 0 and s["caught_incorrect"] > 0
                  else "vacuous" if s["rejected_correct"] == 0 else "unsound")
        report.append({"id": c["id"], "name": c["name"], "status": status, **s})
        if status == "admitted":
            admitted.append(c)
        elif status == "unsound" and c["source"]:
            feedback.append({"name": c["name"], "source": c["source"],
                             "n_rejected_correct": len(rc),
                             "n_correct": s["n_correct"],
                             "rejected_correct_examples": [
                                 {"ctx": {k: examples[i]["ctx"][k] for k in examples[i]["ctx"]
                                          if k not in ("db_path", "schema", "instance_id")},
                                  "output": examples[i]["raw"][:400],
                                  "is_gold": examples[i]["model"] == "gold"} for i in rc[:8]]})
    report.sort(key=lambda r: (r["status"] != "admitted", -r.get("catch_rate", 0) if r.get("catch_rate") == r.get("catch_rate") else 0))
    with open(a.out, "w") as f:
        json.dump({"task": a.task, "pool": a.pool, "candidates": a.candidates,
                   "report": report, "admitted": admitted, "feedback": feedback}, f, indent=1)
    n = {s: sum(r["status"] == s for r in report) for s in ("admitted", "unsound", "vacuous", "load_error")}
    print(f"admission: {n}")
    for r in report[:40]:
        print(f"  {r['status']:9s} {str(r['name'])[:50]:50s} "
              f"rej_correct={r.get('rejected_correct', '-')!s:>4} "
              f"catch={r.get('catch_rate', float('nan')):.3f}")
    return 0


def _conjunction(task, admitted, examples):
    V = _all_verdicts(task, admitted, examples)
    return [all(V[c["id"]][i] for c in admitted) for i in range(len(examples))], V


def cmd_certify(a):
    with open(a.admitted) as f:
        admitted = json.load(f)["admitted"]
    examples = load_examples(a.task, a.pool)
    conj, V = _conjunction(a.task, admitted, examples)
    s, rc = _stats(conj, examples)
    bound = _upper_bound(s["rejected_correct"], s["n_correct"])
    per = {c["id"]: _stats(V[c["id"]], examples)[0]["rejected_correct"] for c in admitted}
    out = {"task": a.task, "pool": a.pool, "n_admitted": len(admitted), **s,
           "false_rejection_upper_95": bound,
           "certified": s["rejected_correct"] == 0,
           "per_check_rejected_correct": per,
           "rejected_correct_examples": [{"instance_id": examples[i]["instance_id"],
                                          "model": examples[i]["model"],
                                          "output": examples[i]["raw"][:300]} for i in rc[:10]]}
    with open(a.out, "w") as f:
        json.dump(out, f, indent=1)
    print(json.dumps({k: v for k, v in out.items() if k not in ("rejected_correct_examples", "per_check_rejected_correct")}, indent=1))
    bad = {k: v for k, v in per.items() if v}
    if bad:
        print("checks rejecting correct outputs on split B:", bad)
    return 0


def cmd_evaluate(a):
    with open(a.admitted) as f:
        admitted = json.load(f)["admitted"]
    examples = [e for e in load_examples(a.task, a.pool) if e["model"] != "gold"]
    conj, _ = _conjunction(a.task, admitted, examples)
    hw = _hw_names(examples)
    from soundver.records import CHECKS
    hw_sound = list(CHECKS[a.task]) if a.task != "morph" else ["no_empty_segment"]
    by_model = {}
    for e, v in zip(examples, conj):
        by_model.setdefault(e["model"], []).append(Record(
            task=a.task, model=e["model"], seed=e["seed"], instance_id=e["instance_id"],
            cand_idx=e["cand_idx"], correct=e["correct"],
            checks={**e["checks"], "synth": v,
                    "synth_and_hw": v and all(e["checks"][h] for h in hw_sound)}))
    out = {}
    for m, recs in sorted(by_model.items()):
        row = {}
        for name, subset in (("handwritten", hw_sound), ("synth", ["synth"]),
                             ("synth_and_hw", ["synth_and_hw"])):
            R = estimate(recs, subset=subset)
            row[name] = {"p0": R.p0, "p": R.p, "delta": R.delta, "eps": R.eps,
                         "sound": R.sound,
                         "ceiling_pts": R.ceiling_pts() if R.sound else None}
        out[m] = row
        print(m)
        for name, r in row.items():
            print(f"  {name:13s} delta={r['delta']:.4f} eps={r['eps']:.3f} "
                  f"ceiling={r['ceiling_pts'] if r['ceiling_pts'] is None else round(r['ceiling_pts'], 2)}")
    with open(a.out, "w") as f:
        json.dump({"task": a.task, "pool": a.pool, "admitted": [c["id"] for c in admitted],
                   "by_model": out}, f, indent=1)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("admit")
    p.add_argument("--task", required=True); p.add_argument("--candidates", nargs="+", required=True)
    p.add_argument("--pool", required=True); p.add_argument("--out", required=True)
    for name in ("certify", "evaluate"):
        q = sub.add_parser(name)
        q.add_argument("--task", required=True); q.add_argument("--admitted", required=True)
        q.add_argument("--pool", required=True); q.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    return {"admit": cmd_admit, "certify": cmd_certify, "evaluate": cmd_evaluate}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
