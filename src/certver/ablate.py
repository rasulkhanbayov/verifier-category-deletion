"""
certver.ablate -- ablations of the selection/certification procedure (E4).

  python -m certver.ablate --task ie --out out/ablate_ie.json

Every variant selects on split A with the instance-level rule (select_inst,
budget tau/2), then is evaluated three ways: the bound it would CLAIM, the
certificate on B, and the test grid (instance-averaged false-rejection rate,
false acceptance, gated best-of-32 accuracy; seeds 0-2, 3 models pooled).

Variants
  main          all candidates, admission on gold + correct model outputs
  single_split  same selection, but the bound is computed on A (the split it
                was selected on) instead of B: does that bound hold on test?
  gold_only     admission AND certification see gold outputs as the only
                correct examples (HardTests-style validation against gold)
  proposer=X    candidates from one proposer only (gpt4o / opus)
  cands=f       random fraction f of the candidate pool (5 draws each)
"""
from __future__ import annotations
import argparse, glob, json, sys
import numpy as np

from .admit import load_examples, _upper_bound
from .curve import (verdict_matrix, load_candidates, conj, groups_of,
                    gamma_counts, select_inst)
from .ci import per_instance

TAUS = (0.01, 0.02, 0.05)


def _test_eval(task, ids, cands_by_id, seeds, cache):
    """Pooled over seeds and models: instance-averaged delta, eps, gated acc, base acc."""
    tot = {"rc_inst": [], "acc_inc": 0, "n_inc": 0, "gated": [], "base": []}
    for seed in seeds:
        if seed not in cache:
            cache[seed] = [e for e in load_examples(task, f"data/test/pool_{task}_test_seed{seed}.jsonl")
                           if e["model"] != "gold"]
        ex = cache[seed]
        V = verdict_matrix(task, [cands_by_id[i] for i in ids], ex)
        acc = conj(V, ids, len(ex))
        cor = np.array([e["correct"] for e in ex])
        per = {}
        for e, a, c in zip(ex, acc, cor):
            if c:
                t = per.setdefault((e["model"], e["instance_id"]), [0, 0]); t[0] += 1; t[1] += int(not a)
        tot["rc_inst"] += [r / n for n, r in per.values()]
        tot["acc_inc"] += int((acc & ~cor).sum()); tot["n_inc"] += int((~cor).sum())
        for v, b in per_instance(ex, acc, 32).values():
            tot["gated"].append(v); tot["base"].append(b)
    return {"test_inst_delta": float(np.mean(tot["rc_inst"])),
            "test_eps": tot["acc_inc"] / max(1, tot["n_inc"]),
            "test_gated_acc": float(np.mean(tot["gated"])),
            "test_base_acc": float(np.mean(tot["base"]))}


def _bound(acc, cor, groups):
    k, n = gamma_counts(acc, cor, groups)
    return k, n, _upper_bound(k, n)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", required=True)
    ap.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    ap.add_argument("--fractions", nargs="+", type=float, default=[0.1, 0.25, 0.5])
    ap.add_argument("--draws", type=int, default=5)
    ap.add_argument("--no-test", action="store_true")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    t = a.task

    exA = load_examples(t, f"data/pools/pool_{t}_admit_seed0.jsonl")
    exB = load_examples(t, f"data/pools/pool_{t}_certify_seed0.jsonl")
    cands = load_candidates(t, [f"out/candidates/{t}_*.jsonl"], exA)
    by_id = {c["id"]: c for c in cands}
    print(f"{len(cands)} candidates; verdicts on A and B for all of them", flush=True)
    VA = verdict_matrix(t, cands, exA)
    VB = verdict_matrix(t, cands, exB)
    corA = np.array([e["correct"] for e in exA]); gA = groups_of(exA)
    corB = np.array([e["correct"] for e in exB]); gB = groups_of(exB)
    goldA = np.array([e["model"] == "gold" for e in exA])
    goldB = np.array([e["model"] == "gold" for e in exB])

    proposer_of = {}
    for p in glob.glob(f"out/candidates/{t}_*.jsonl"):
        who = "opus" if "opus" in p else "gpt4o"
        for line in open(p):
            if line.strip():
                proposer_of[json.loads(line)["id"]] = who

    variants = []
    for tau in TAUS:
        ids = select_inst(VA, corA, gA, tau / 2)
        variants.append(("main", tau, ids, None))
        variants.append(("single_split", tau, ids, "A"))
        keep = goldA | ~corA          # drop correct MODEL outputs from admission
        sub = {c: v[keep] for c, v in VA.items()}
        ids_g = select_inst(sub, corA[keep], groups_of([e for e, k in zip(exA, keep) if k]), tau / 2)
        variants.append(("gold_only", tau, ids_g, "B_gold"))
        for who in ("gpt4o", "opus"):
            subV = {c: v for c, v in VA.items() if c.startswith("hw:") or proposer_of.get(c) == who}
            variants.append((f"proposer={who}", tau, select_inst(subV, corA, gA, tau / 2), None))
    rng = np.random.default_rng(0)
    synth = [c for c in VA if not c.startswith("hw:")]
    hw = [c for c in VA if c.startswith("hw:")]
    for f in a.fractions:
        for d in range(a.draws):
            pick = set(rng.choice(synth, size=max(1, int(round(f * len(synth)))), replace=False)) | set(hw)
            subV = {c: VA[c] for c in pick}
            variants.append((f"cands={f}#{d}", 0.02, select_inst(subV, corA, gA, 0.01), None))

    rows, cache = [], {}
    for name, tau, ids, bound_on in variants:
        accA = conj(VA, ids, len(exA)); accB = conj(VB, ids, len(exB))
        kA, nA, UA = _bound(accA, corA, gA)
        kB, nB, UB = _bound(accB, corB, gB)
        if bound_on == "A":
            claimed = UA
        elif bound_on == "B_gold":     # what a gold-only procedure would certify
            keepB = goldB | ~corB
            _, _, claimed = _bound(accB[keepB], corB[keepB],
                                   groups_of([e for e, k in zip(exB, keepB) if k]))
        else:
            claimed = UB
        row = {"variant": name, "tau": tau, "n_checks": len(ids), "checks": ids,
               "A_gamma": f"{kA}/{nA}", "B_gamma": f"{kB}/{nB}", "claimed_bound": claimed,
               "certified": claimed <= tau,
               "B_catch": float((~accB & ~corB).sum() / max(1, (~corB).sum()))}
        do_test = not a.no_test and not name.startswith("cands=")
        if do_test:
            row.update(_test_eval(t, ids, by_id, a.seeds, cache))
            row["bound_holds_on_test"] = row["test_inst_delta"] <= claimed
        rows.append(row)
        msg = (f"{name:16s} tau={tau:<5} checks={len(ids):2d} A={row['A_gamma']:>8s} B={row['B_gamma']:>8s} "
               f"claimed U95={claimed:.4f} {'CERT' if row['certified'] else '    '} B_catch={row['B_catch']:.3f}")
        if do_test:
            msg += (f" | test inst-delta={row['test_inst_delta']:.4f} "
                    f"{'holds' if row['bound_holds_on_test'] else 'VIOLATED'} eps={row['test_eps']:.3f} "
                    f"gated={100*row['test_gated_acc']:.1f} (base {100*row['test_base_acc']:.1f})")
        print(msg, flush=True)
    json.dump({"task": t, "rows": rows}, open(a.out, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
