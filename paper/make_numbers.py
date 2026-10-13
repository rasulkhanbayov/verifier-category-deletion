#!/usr/bin/env python3
"""
make_numbers.py (v4.1) -- every number in the paper comes from here.

Reads out/*.json (repo root) and writes paper/gen/: tab_safety.tex,
tab_fresh.tex, tab_down.tex, tab_validity.tex, tab_ablate.tex,
numbers.tex (\\newcommand macros). Re-run after any
experiment change; never hand-edit gen/. The v4.0 generator is kept as
make_numbers_v4.0.py for the old draft (main_v4.0.tex).
"""
import glob, json, os, re
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "out")
DATA = os.path.join(HERE, "..", "data")
GEN = os.path.join(HERE, "gen")
os.makedirs(GEN, exist_ok=True)

TASKS = ["ie", "fewnerd", "fc", "sql", "math", "morph"]
TN = {"ie": "CoNLL", "fewnerd": "Few-NERD", "fc": "Func.\\ call", "sql": "SQL", "math": "GSM8K", "morph": "Morph."}
TAG = {"ie": "IE", "fewnerd": "Fewnerd", "fc": "FC", "sql": "SQL", "math": "Math", "morph": "Morph"}
MODELS = ["meta-llama/llama-3.1-70b-instruct", "openai/gpt-4o-mini-2024-07-18", "qwen/qwen-2.5-72b-instruct"]
MN = {MODELS[0]: "Llama-3.1-70B", MODELS[1]: "GPT-4o-mini", MODELS[2]: "Qwen2.5-72B"}
MT = {MODELS[0]: "Llama", MODELS[1]: "Mini", MODELS[2]: "Qwen"}
BUDGETS = (0.01, 0.02, 0.05)
M = {}


def mac(k, v):
    assert re.fullmatch(r"[A-Za-z]+", k), k
    M[k] = v


def load(n):
    return json.load(open(os.path.join(OUT, n)))


def pct(x, d=1):
    return f"{100 * x:.{d}f}"


def rate(x):
    """resampling rate in %: integer, but one decimal when 0 < x < 1% so small rates never print as 0"""
    return pct(x, 1) if 0 < x < 0.01 else pct(x, 0)


def sgn(x, d=1):
    s = f"{abs(100 * x):.{d}f}"
    return ("+" if x >= 0 else "$-$") + s


def ci(t, d=1):
    return f"{sgn(t[0], d)} [{sgn(t[1], d)}, {sgn(t[2], d)}]"


def pick(curve_rows):
    for b in BUDGETS:
        r = [x for x in curve_rows if x["selection"] == f"itau={b}"][0]
        if r["certified"]:
            return b, r
    raise SystemExit("no certified budget")


# ---------------------------------------------------------- safety table (B)
rows = []
for t in TASKS:
    R = load(f"robust_{t}.json")
    C = load(f"curve_{t}_inst_multi.json")["results"]
    b, crow = pick(C)
    rr = {(x["selection"], x["budget"]): x for x in R["rows"]}
    hw = rr[("handwritten", None)]; f1 = rr[("f1", None)]; apv = rr[("apv", None)]
    bud = rr[("budgeted", b)]; grp = rr[("group", b)]
    assert set(bud["checks"]) == set(crow["checks"]), f"{t}: robust budgeted != curve certified selection"
    assert bud["B"]["U"] <= b, f"{t}: not certified at {b} after Bonferroni"
    rs = R["resampling"]
    cells = [TN[t]]
    cells += [pct(x["B"]["catch"]) for x in (hw, f1, apv, bud)] + [""]   # "" = spacer column
    cells += [str(x["B"]["k"]) for x in (hw, f1, apv, bud)] + [""]
    cells += [rate(rs[k]["deletion_rate"]) for k in ("f1", "apv", "budgeted", "group")]
    rows.append(" & ".join(cells) + r" \\")
    T = TAG[t]
    mac(f"budget{T}", f"{100 * b:g}")
    mac(f"boundB{T}", pct(bud["B"]["U"], 2))
    for k, x in (("Hw", hw), ("Fone", f1), ("Apv", apv), ("Cert", bud), ("Group", grp)):
        mac(f"catch{k}{T}", pct(x["B"]["catch"]))
        mac(f"gammaK{k}{T}", str(x["B"]["k"]))
        mac(f"boundU{k}{T}", pct(x["B"]["U"], 2))
        mac(f"nChecks{k}{T}", str(x["n_checks"]))
        mac(f"worstWiped{k}{T}", pct(x["B"]["worst_group_wiped_frac"], 0))
    for k, kk in (("f1", "Fone"), ("apv", "Apv"), ("budgeted", "Cert"), ("group", "Group"), ("f1_constrained", "Fonec")):
        mac(f"delRate{kk}{T}", rate(rs[k]["deletion_rate"]))
        mac(f"worstWipedMean{kk}{T}", pct(rs[k]["worst_wiped_mean"], 1))
        mac(f"resCatch{kk}{T}", pct(rs[k]["catch_mean"], 1))
        mac(f"coverage{kk}{T}", pct(rs[k]["coverage"], 0))
    if "strong_handwritten" in {x["selection"] for x in R["rows"]}:
        s = rr[("strong_handwritten", None)]
        mac(f"catchStrong{T}", pct(s["B"]["catch"])); mac(f"gammaKStrong{T}", str(s["B"]["k"]))
    mac(f"groupsN{T}", str(int(sum(1 for n in R["B_group_sizes"] if n >= 50))))
open(os.path.join(GEN, "tab_safety.tex"), "w").write("\n".join(rows) + "\n")

# -------------------------------------------------- fresh test accuracy (4 tasks)
fr = []
for t in [t for t in TASKS if os.path.exists(os.path.join(OUT, f"report_{t}_fresh.json"))]:
    Rp = load(f"report_{t}_fresh.json")
    first = True
    for m in MODELS:
        if m not in Rp["by_model"] or Rp["by_model"][m]["n_units"] < 100:
            continue
        x = Rp["by_model"][m]
        hw, f1, ce = x["handwritten"], x["f1_baseline"], x["certified"]
        ap = x.get("apv_baseline", f1)
        fr.append((f"\\multirow{{{sum(1 for mm in MODELS if mm in Rp['by_model'] and Rp['by_model'][mm]['n_units'] >= 100)}}}{{*}}{{{TN[t]}}}" if first else "")
                  + f" & {MN[m]} & {pct(x['base_acc'])} & {pct(hw['acc'])} & {pct(f1['acc'])} & {pct(ap['acc'])} & {pct(ce['acc'])} & "
                  f"{ci(x['cert_minus_f1'])} & {pct(f1['inst_avg_delta'], 1)} & {pct(ap['inst_avg_delta'], 1)} & {pct(ce['inst_avg_delta'], 1)} \\\\")
        first = False
        T, mt = TAG[t], MT[m]
        mac(f"frAccCert{T}{mt}", pct(ce["acc"])); mac(f"frAccHw{T}{mt}", pct(hw["acc"]))
        mac(f"frAccFone{T}{mt}", pct(f1["acc"])); mac(f"frAccBase{T}{mt}", pct(x["base_acc"]))
        mac(f"frGain{T}{mt}", sgn(x["cert_minus_hw"][0])); mac(f"frGainLo{T}{mt}", sgn(x["cert_minus_hw"][1]))
        mac(f"frGainHi{T}{mt}", sgn(x["cert_minus_hw"][2])); mac(f"frVsFone{T}{mt}", sgn(x["cert_minus_f1"][0]))
        mac(f"frVsFoneLo{T}{mt}", sgn(x["cert_minus_f1"][1])); mac(f"frVsFoneHi{T}{mt}", sgn(x["cert_minus_f1"][2]))
        mac(f"frDltCert{T}{mt}", pct(ce["inst_avg_delta"], 1)); mac(f"frDltFone{T}{mt}", pct(f1["inst_avg_delta"], 1))
        mac(f"frDltApv{T}{mt}", pct(ap["inst_avg_delta"], 1))
    fr.append(r"\addlinespace[2pt]")
    F = Rp["filtering"]
    for k, kk in (("handwritten", "Hw"), ("certified", "Cert"), ("f1_baseline", "Fone")):
        mac(f"frLost{kk}{TAG[t]}", f"{F[k]['lost']}/{F[k]['n']}")
        mac(f"frPrec{kk}{TAG[t]}", f"{F[k]['precision']:.3f}"); mac(f"frRec{kk}{TAG[t]}", f"{F[k]['recall']:.3f}")
        for g, v in F[k]["subgroups"].items():
            gn = "".join(w.capitalize() for w in re.sub(r"[^a-z]", " ", g).split())
            mac(f"frSub{kk}{TAG[t]}{gn}", f"{v['lost']}/{v['n']}")
            mac(f"frSubPct{kk}{TAG[t]}{gn}", pct(v["lost"] / max(1, v["n"]), 0))
open(os.path.join(GEN, "tab_fresh.tex"), "w").write("\n".join(fr[:-1]) + "\n")
# development draws (multi-model pools) for the IE accuracy comparison
Rd = load("report_ie_multi.json")
for m in MODELS:
    if m in Rd["by_model"]:
        x = Rd["by_model"][m]; mt = MT[m]
        mac(f"devVsFoneIE{mt}", sgn(x["cert_minus_f1"][0]))
        mac(f"devVsFoneLoIE{mt}", sgn(x["cert_minus_f1"][1])); mac(f"devVsFoneHiIE{mt}", sgn(x["cert_minus_f1"][2]))

# ------------------------------------------------------ downstream (distill, RL)
dr = []
S3 = load("distill_ie_seeds.json")
def agg(keys, field):
    v = [S3[k] for k in keys]
    if field == "acc": a = [100 * x["accuracy"] for x in v]
    elif field == "else": a = [100 * x["subgroups"]["has_else_type"]["acc"] for x in v]
    else: a = [x["fields"]["else"]["recall"] for x in v]
    return np.mean(a), (np.std(a, ddof=1) if len(a) > 1 else 0.0)
for cond, lab in (("f1_baseline", "F1-selected"), ("certified", "Certified")):
    ks = [k for k in S3 if k == cond or k.startswith(cond + "_s")]
    a, e, r = agg(ks, "acc"), agg(ks, "else"), agg(ks, "rec")
    dr.append(f"Distill, CoNLL (0.6B, {len(ks)} seeds) & {lab} & {a[0]:.1f}$\\pm${a[1]:.1f} & {e[0]:.1f}$\\pm${e[1]:.1f} & {r[0]:.2f}$\\pm${r[1]:.2f} \\\\")
    kk = "Fone" if cond == "f1_baseline" else "Cert"
    mac(f"dsAcc{kk}", f"{a[0]:.1f}"); mac(f"dsAccSd{kk}", f"{a[1]:.1f}"); mac(f"dsElse{kk}", f"{e[0]:.1f}")
    mac(f"dsElseSd{kk}", f"{e[1]:.1f}"); mac(f"dsRec{kk}", f"{r[0]:.2f}"); mac(f"dsRecSd{kk}", f"{r[1]:.2f}")
if os.path.exists(os.path.join(OUT, "distill_ie_matched.json")):
    Mt = load("distill_ie_matched.json")
    ks = [k for k in Mt if k.startswith("certmatched")]
    v = [Mt[k] for k in ks]
    a = [100 * x["accuracy"] for x in v]; e = [100 * x["subgroups"]["has_else_type"]["acc"] for x in v]
    r = [x["fields"]["else"]["recall"] for x in v]
    dr.append(f"\\quad size-matched ({len(ks)} subsamples) & Certified & {np.mean(a):.1f}$\\pm${np.std(a, ddof=1):.1f} & "
              f"{np.mean(e):.1f}$\\pm${np.std(e, ddof=1):.1f} & {np.mean(r):.2f}$\\pm${np.std(r, ddof=1):.2f} \\\\")
    mac("dsMatchedAcc", f"{np.mean(a):.1f}"); mac("dsMatchedElse", f"{np.mean(e):.1f}"); mac("dsMatchedRec", f"{np.mean(r):.2f}")
if os.path.exists(os.path.join(OUT, "distill_ie_f1minusdel.json")):
    ABx = load("distill_ie_f1minusdel.json"); ks = [k for k in ABx if k.startswith("f1minusdel_s")]
    a = [100 * ABx[k]["accuracy"] for k in ks]; e = [100 * ABx[k]["subgroups"]["has_else_type"]["acc"] for k in ks]
    r = [ABx[k]["fields"]["else"]["recall"] for k in ks]
    dr.append(f"\\quad without the deleting check ({len(ks)} seeds) & F1-selected & {np.mean(a):.1f}$\\pm${np.std(a, ddof=1):.1f} & "
              f"{np.mean(e):.1f}$\\pm${np.std(e, ddof=1):.1f} & {np.mean(r):.2f}$\\pm${np.std(r, ddof=1):.2f} \\\\")
if os.path.exists(os.path.join(OUT, "distill_ie_1p7b.json")):
    B7 = load("distill_ie_1p7b.json")
    for cond, lab in (("f1_baseline_1p7b", "F1-selected"), ("certified_1p7b", "Certified")):
        x = B7[cond]
        dr.append(f"\\quad 1.7B student & {lab} & {100 * x['accuracy']:.1f} & {100 * x['subgroups']['has_else_type']['acc']:.1f} & "
                  f"{x['fields']['else']['recall']:.2f} \\\\")
        kk = "Fone" if cond.startswith("f1") else "Cert"
        mac(f"dsBigAcc{kk}", f"{100 * x['accuracy']:.1f}"); mac(f"dsBigElse{kk}", f"{100 * x['subgroups']['has_else_type']['acc']:.1f}")
        mac(f"dsBigRec{kk}", f"{x['fields']['else']['recall']:.2f}")
dr.append(r"\addlinespace[2pt]")
RL = load("rl2_ie_seeds.json") if os.path.exists(os.path.join(OUT, "rl2_ie_seeds.json")) else load("rl2_ie.json")
for cond, lab in (("sftinit", "Start (label-filtered SFT)"), ("rl2_label", "RL, label reward"), ("rl2_certified", "RL, certified gate"), ("rl2_f1", "RL, F1 gate")):
    ks = [k for k in RL if k == cond or k.startswith(cond + "_s")]
    v = [RL[k] for k in ks]
    a = [100 * x["accuracy"] for x in v]; e = [100 * x["subgroups"]["has_else_type"]["acc"] for x in v]
    r = [x["fields"]["else"]["recall"] for x in v]
    if len(ks) >= 3:
        fmt = (lambda arr, d: f"{np.mean(arr):.{d}f}$\\pm${np.std(arr, ddof=1):.{d}f}")
    else:
        fmt = (lambda arr, d: " / ".join(f"{z:.{d}f}" for z in arr))
    dr.append(f"RL, CoNLL ({len(ks)} seed{'s' if len(ks) > 1 else ''}) & {lab} & {fmt(a, 1)} & {fmt(e, 1)} & {fmt(r, 2)} \\\\")
    kk = {"sftinit": "Init", "rl2_label": "Label", "rl2_certified": "Cert", "rl2_f1": "Fone"}[cond]
    mac(f"rlAcc{kk}", fmt(a, 1)); mac(f"rlElse{kk}", fmt(e, 1)); mac(f"rlRec{kk}", fmt(r, 2))
    mac(f"rlRecMin{kk}", f"{min(r):.2f}"); mac(f"rlRecMax{kk}", f"{max(r):.2f}"); mac(f"rlN{kk}", str(len(ks)))
FN = load("distill_fewnerd.json")
FS = load("distill_fewnerd_seeds.json") if os.path.exists(os.path.join(OUT, "distill_fewnerd_seeds.json")) else None
dr.append(r"\addlinespace[2pt]")
for cond, lab in (("handwritten", "Hand-written"), ("f1_baseline", "F1-selected"), ("certified", "Certified")):
    x = FN[cond]
    seeds = [100 * FS[k]["accuracy"] for k in FS if isinstance(FS[k], dict) and "accuracy" in FS[k]
             and (k == cond or (k.startswith(cond + "_s") and k[len(cond) + 2:].isdigit()))] if FS else []
    if len(seeds) > 1:
        dr.append(f"Distill, Few-NERD (0.6B, {len(seeds)} seeds) & {lab} & {np.mean(seeds):.1f}$\\pm${np.std(seeds, ddof=1):.1f} & -- & -- \\\\")
    else:
        dr.append(f"Distill, Few-NERD (0.6B{', 1 seed' if FS else ''}) & {lab} & {100 * x['accuracy']:.1f} & -- & -- \\\\")
    mac(f"fnAcc{ {'handwritten': 'Hw', 'f1_baseline': 'Fone', 'certified': 'Cert'}[cond] }", f"{100 * x['accuracy']:.1f}")
for cond, kk in (("handwritten", "Hw"), ("f1_baseline", "Fone"), ("none", "None")):
    t = FN[cond]["certified_minus_this"]; mac(f"fnDiff{kk}", ci(t))
if os.path.exists(os.path.join(OUT, "distill_fewnerd_seeds.json")):
    FS = load("distill_fewnerd_seeds.json")
    for cond, kk in (("certified", "Cert"), ("f1_baseline", "Fone")):
        v = [100 * FS[k]["accuracy"] for k in FS if isinstance(FS[k], dict) and "accuracy" in FS[k]
             and (k == cond or (k.startswith(cond + "_s") and k[len(cond) + 2:].isdigit()))]
        mac(f"fnSeed{kk}", f"{np.mean(v):.1f}"); mac(f"fnSeedSd{kk}", f"{np.std(v, ddof=1):.1f}"); mac("fnSeedN", str(len(v)))
open(os.path.join(GEN, "tab_down.tex"), "w").write("\n".join(dr) + "\n")

# ----------------------------------------------------- validity and transfer
vr = []
for t in TASKS:
    R = load(f"robust_{t}.json"); C = load(f"curve_{t}_inst_multi.json")["results"]
    if not any(x.get("test_gamma") for x in R["rows"]):
        continue
    b, _ = pick(C)
    rr = {(x["selection"], x["budget"]): x for x in R["rows"]}
    for sel, lab in ((("handwritten", None), "Hand-written"), (("f1", None), "F1-selected"),
                     (("apv", None), "AutoPyVerifier obj."), (("budgeted", b), "Certified")):
        x = rr[sel]
        mx = max(x["test_gamma"]); mean = float(np.mean(x["test_gamma"]))
        ok = "yes" if mean <= x["B"]["U"] else r"\textbf{no}"
        vr.append(f"{TN[t] if sel[0] == 'handwritten' else ''} & {lab} & {pct(x['B']['U'], 2)} & {pct(mean, 2)} & {pct(mx, 2)} & {ok} \\\\")
        lk = {"handwritten": "Hw", "f1": "Fone", "apv": "Apv", "budgeted": "Cert"}[sel[0]]
        mac(f"valMean{lk}{TAG[t]}", pct(mean, 2)); mac(f"valMax{lk}{TAG[t]}", pct(mx, 2)); mac(f"valU{lk}{TAG[t]}", pct(x["B"]["U"], 2))
    vr.append(r"\addlinespace[2pt]")
    mac(f"covCert{TAG[t]}", pct(R["resampling"]["budgeted"]["coverage"], 0))
open(os.path.join(GEN, "tab_validity.tex"), "w").write("\n".join(vr[:-1]) + "\n")
for t, m, mt in (("sql", "meta-llama/llama-3.1-8b-instruct", "Llamaeight"), ("sql", "qwen/qwen-2.5-7b-instruct", "Qwenseven"),
                 ("math", "meta-llama/llama-3.1-8b-instruct", "Llamaeight")):
    x = load(f"report_{t}_fresh_weak.json")
    y = x["by_model"][m]
    mac(f"wkDltCert{TAG[t]}{mt}", pct(y["certified"]["inst_avg_delta"], 2))
    mac(f"wkDltFone{TAG[t]}{mt}", pct(y["f1_baseline"]["inst_avg_delta"], 2))
    mac(f"wkDltHw{TAG[t]}{mt}", pct(y["handwritten"]["inst_avg_delta"], 1))
    mac(f"wkBound{TAG[t]}", M[f"boundB{TAG[t]}"])   # Bonferroni-corrected certified bound (same as tab:fresh caption)
    mac(f"wkRecHw{TAG[t]}", f"{x['filtering']['handwritten']['recall']:.2f}")
    mac(f"wkRecCert{TAG[t]}", f"{x['filtering']['certified']['recall']:.2f}")

# ----------------------------------------------------------------- ablations
ar = []
labels = {"main": "Full method", "gold_only": "Gold-only admission and certification",
          "single_split": "Single split (bound on A)", "proposer=gpt4o": "GPT-4o candidates only",
          "proposer=opus": "Claude Opus candidates only"}
from scipy.stats import beta as _beta
def _cp(k, n, a):
    return 1.0 if k >= n else float(_beta.ppf(1 - a, k + 1, n - k))
ALPHA = 0.05 / len(BUDGETS)   # the paper's certificate: Bonferroni over the three budgets
def _claimed(x):
    """Bound each procedure would report, at the paper's corrected level. ablate.py stored
    the UNcorrected 95% bound; we recompute from the stored counts. For gold_only the
    count on B's gold answers was not stored: it is recovered exactly by inverting the
    stored 95% bound (the Clopper-Pearson bound is strictly increasing in k)."""
    if x["variant"] == "single_split":
        k, n = map(int, x["A_gamma"].split("/"))
    elif x["variant"] == "gold_only":
        n = int(x["B_gamma"].split("/")[1])
        ks = [k for k in range(n) if abs(_cp(k, n, 0.05) - x["claimed_bound"]) < 1e-9]
        assert len(ks) == 1, "gold_only count not recoverable"
        k = ks[0]
    else:
        k, n = map(int, x["B_gamma"].split("/"))
        assert abs(_cp(k, n, 0.05) - x["claimed_bound"]) < 1e-9, "stored bound does not match stored counts"
    return _cp(k, n, ALPHA)
for t in ("sql", "ie"):
    A = {r["variant"]: r for r in load(f"ablate_{t}_multi.json")["rows"] if r["tau"] == 0.05}
    for v in ("main", "gold_only", "single_split", "proposer=gpt4o", "proposer=opus"):
        x = A[v]; cl = _claimed(x); holds = x["test_inst_delta"] <= cl
        ar.append(f"{TN[t] if v == 'main' else ''} & {labels[v]} & {pct(cl, 2)} & {pct(x['test_inst_delta'], 2)} & "
                  f"{'yes' if holds else chr(92) + 'textbf{no}'} & {pct(x['B_catch'])} & {pct(x['test_gated_acc'])} \\\\")
        k = {"main": "Main", "gold_only": "Gold", "single_split": "Single", "proposer=gpt4o": "Gpt", "proposer=opus": "Opus"}[v]
        mac(f"abl{k}Claim{TAG[t]}", pct(cl, 2)); mac(f"abl{k}Test{TAG[t]}", pct(x["test_inst_delta"], 2))
        mac(f"abl{k}Catch{TAG[t]}", pct(x["B_catch"]))
    g = A["gold_only"]; mac(f"ablGoldRatio{TAG[t]}", f"{g['test_inst_delta'] / _claimed(g):.1f}")
    ar.append(r"\addlinespace[2pt]")
open(os.path.join(GEN, "tab_ablate.tex"), "w").write("\n".join(ar[:-1]) + "\n")

# (the unused trade-off figure was removed on 2026-10-13: it plotted the uncorrected bound; figures now come from make_figures.py)

# ------------------------------------------------------- audit + misc numbers
flips = json.load(open(os.path.join(GEN, "label_flips.json"))) if os.path.exists(os.path.join(GEN, "label_flips.json")) else None
if flips:
    mac("labelFalsePos", pct(flips["tf"] / (flips["tt"] + flips["tf"])))
    mac("labelFalseNeg", pct(flips["ft"] / (flips["ft"] + flips["ff"])))
    mac("labelN", f"{sum(flips.values()):,}".replace(",", "{,}"))
for t in TASKS:
    n = sum(sum(1 for l in open(p) if l.strip()) for p in glob.glob(os.path.join(OUT, "candidates", f"{t}_*.jsonl")))
    mac(f"cand{TAG[t]}", str(n))
mac("candTotal", str(sum(int(M[f"cand{TAG[t]}"]) for t in TASKS)))

# ------------------------------------------- when F1 deletes (f1rule + stress test)
FR = load("f1rule.json")
mac("ruleN", str(sum(FR[t]["rule_checked"] for t in TASKS)))
mac("ruleAgree", str(sum(FR[t]["rule_agrees"] for t in TASKS)))
for t in TASKS:
    mac(f"thr{TAG[t]}", f"{FR[t]['threshold']:.2f}")
    mac(f"nDeletable{TAG[t]}", str(len(FR[t]["deletable"])))
mac("precIEElse", f"{FR['ie']['group_precision']['has_else_type']:.2f}")
ie_w = [w for w in FR["ie"]["wipers"] if w["group_deletable"] and w["solo_dF1"] > 0]
mac("nIsolatingIE", str(len(ie_w)))
mac("nIsolatingOther", str(sum(1 for t in TASKS if t != "ie" for w in FR[t]["wipers"]
                                if w["group_deletable"] and w["solo_dF1"] > 0)))
inj = FR["fewnerd"]["injected"]
picked = sorted(x["id"].replace("inj:no_", "") for x in inj if x["picked_step"] is not None)
mac("injNFewnerd", str(len(inj))); mac("injNPicked", str(len(picked)))
mac("injPicked", ", ".join(picked[:-1]) + " and " + picked[-1])
mac("injPrecPickedMax", f"{max(x['precision'] for x in inj if x['picked_step'] is not None):.2f}")
mac("injPrecUnpickedMin", f"{min(x['precision'] for x in inj if x['picked_step'] is None):.2f}")
mac("injThrPickedMin", f"{min(x['threshold_at_step'] for x in inj if x['picked_step'] is not None):.2f}")
mac("injPrecSQL", f"{FR['sql']['injected'][0]['precision']:.2f}")
RI = load("robust_fewnerd_inject.json")
rs = RI["resampling"]
mac("injDelFone", pct(rs["f1"]["deletion_rate"], 1)); mac("injDelBudget", rate(rs["budgeted"]["deletion_rate"]))
mac("injDelFonec", rate(rs["f1_constrained"]["deletion_rate"])); mac("injDelGroup", rate(rs["group"]["deletion_rate"]))
f1row = [r for r in RI["rows"] if r["selection"] == "f1"][0]
mac("injGammaKFone", str(f1row["B"]["k"])); mac("injWipedFone", pct(f1row["B"]["worst_group_wiped_frac"], 0))
mac("injWipedGroupFone", f1row["B"]["worst_group_wiped"].replace("has_", ""))
mac("injTestGammaFone", pct(float(np.mean(f1row["test_gamma"])), 1))
mac("injInConstrained", str(sum(1 for r in RI["rows"] if r["budget"] is not None for cc in r["checks"] if cc.startswith("inj:"))))
# E1/E2 (claim-evidence audit): deletion conditional on the isolating check; output-level budget
if os.path.exists(os.path.join(OUT, "resample_detail_ie.json")):
    RD = load("resample_detail_ie.json")
    dele = [w["id"] for w in FR["ie"]["wipers"] if w["group_deletable"] and w["solo_dF1"] > 0][0]
    av = [r for r in RD["replicates"] if dele in r["available_isolating"]]
    na = [r for r in RD["replicates"] if dele not in r["available_isolating"]]
    mac("rdAvailIE", str(len(av))); mac("rdNIE", str(len(RD["replicates"])))
    for s, kk in (("f1", "Fone"), ("apv", "Apv"), ("budgeted", "Budget"), ("output_level", "Outlvl")):
        mac(f"rdDelAvail{kk}IE", pct(np.mean([r[s]["deleted"] for r in av]), 0))
        mac(f"rdDelNot{kk}IE", pct(np.mean([r[s]["deleted"] for r in na]), 0))
    mac("rdCatchOutlvlIE", pct(RD["summary"]["output_level"]["catch_mean"], 1))
    mac("rdCatchBudgetIE", pct(RD["summary"]["budgeted"]["catch_mean"], 1))
    outl = []
    for t in TASKS:
        fp = os.path.join(OUT, f"resample_detail_{t}.json")
        if os.path.exists(fp):
            outl.append(load(f"resample_detail_{t}.json")["summary"]["output_level"]["deletion_rate"])
    if os.path.exists(os.path.join(OUT, "resample_detail_fewnerd_inject.json")):
        RI2 = load("resample_detail_fewnerd_inject.json")["summary"]
        outl.append(RI2["output_level"]["deletion_rate"])
        mac("rdDelOutlvlInj", rate(RI2["output_level"]["deletion_rate"]))
        mac("rdCatchOutlvlInj", pct(RI2["output_level"]["catch_mean"], 1)); mac("rdCatchBudgetInj", pct(RI2["budgeted"]["catch_mean"], 1))
    mac("rdDelOutlvlMax", pct(max(outl), 0)); mac("rdNTasksOutlvl", str(len(outl)))
if os.path.exists(os.path.join(OUT, "resample_detail_fewnerd_e5.json")):
    E5 = load("resample_detail_fewnerd_e5.json"); R5 = E5["replicates"]
    for s, kk in (("f1", "Fone"), ("apv", "Apv"), ("budgeted", "Budget"), ("output_level", "Outlvl"), ("group", "Group")):
        o = [r[s]["wiped_frac"].get("has_other", 0.0) for r in R5]
        mac(f"eOther{kk}", pct(float(np.mean(o)), 1)); mac(f"eOtherPnine{kk}", pct(float(np.percentile(o, 90)), 0))
        mac(f"eDel{kk}", rate(E5["summary"][s]["deletion_rate"]))
    mac("eNnew", str(sum(1 for f in glob.glob(os.path.join(OUT, "candidates_e5", "fewnerd_round1_*.jsonl")) for l in open(f) if l.strip())))
# adversarial audit (existing outputs)
if os.path.exists(os.path.join(OUT, "adversarial_ie.json")):
    AD = load("adversarial_ie.json")
    mac("advGoldRejA", pct(AD["deleter_rejects_gold"]["A"]["frac"], 0)); mac("advGoldRejB", pct(AD["deleter_rejects_gold"]["B"]["frac"], 0))
    tw = AD["f1_on_AplusB"]["has_else_wiped_on_test_pools"]
    mac("advABmin", pct(min(tw), 0)); mac("advABmax", pct(max(tw), 0))
    W = AD["f1_wiped_on_B"]; CS = AD["cluster_share_has_else"]
    rich = [k for k, v in CS.items() if v >= 0.25]; poor = [k for k, v in CS.items() if v < 0.10]
    mac("advClRichMin", pct(min(W[k]["wiped"] for k in rich), 0)); mac("advClRichMax", pct(max(W[k]["wiped"] for k in rich), 0))
    mac("advClPoorMax", pct(max(W[k]["wiped"] for k in poor), 0))
    Q = AD["distill_misc_quality"]
    for cond, kk in (("f1_baseline", "Fone"), ("certified", "Cert"), ("oracle", "Oracle"), ("none", "None")):
        mac(f"advMiscN{kk}", f"{Q[cond]['misc_entities']:,}".replace(",", "{,}"))
        mac(f"advMiscPrec{kk}", pct(Q[cond]["misc_precision"], 0)); mac(f"advMiscTitle{kk}", pct(Q[cond]["share_titlecase"], 0))
# uncertainty on resampling rates (Wilson 95%) and continuous worst-group loss
def wilson(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n; cen = (p + z * z / (2 * n)) / d; h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return cen - h, cen + h
RIE = load("robust_ie.json"); nrep = RIE["replicates"]
lo, hi = wilson(round(RIE["resampling"]["f1"]["deletion_rate"] * nrep), nrep)
mac("ciDelFoneIELo", pct(lo, 0)); mac("ciDelFoneIEHi", pct(hi, 0))
mac("worstMeanFoneIE", pct(RIE["resampling"]["f1"]["worst_wiped_mean"], 0)); mac("worstMeanBudgetIE", pct(RIE["resampling"]["budgeted"]["worst_wiped_mean"], 0))
ntot = 6 * nrep; mac("nRepTotal", f"{ntot:,}".replace(",", "{,}")); mac("ruleThreeTotal", f"{100 * 3 / ntot:.2f}")
RSQ = load("robust_sql.json"); lo, hi = wilson(round(RSQ["resampling"]["budgeted"]["coverage"] * nrep), nrep)
mac("ciCovSQLLo", pct(lo, 0)); mac("ciCovSQLHi", pct(hi, 0))
# budget sensitivity (tau = 1% and 5%; A-budget 0.005 / 0.025)
bs_del, bs_worst, bs_n = [], [], 0
for b in ("0.005", "0.025"):
    for t in TASKS:
        fp = os.path.join(OUT, f"resample_detail_{t}_b{b}.json")
        if os.path.exists(fp):
            D = load(f"resample_detail_{t}_b{b}.json"); bs_n += 1
            for s in ("budgeted", "group", "output_level", "f1_constrained"):
                bs_del.append(D["summary"][s]["deletion_rate"])
            bs_worst.append(max(r["budgeted"]["worst_frac"] for r in D["replicates"]))
if bs_n:
    mac("bsDelMax", pct(max(bs_del), 0)); mac("bsWorstMax", pct(max(bs_worst), 0)); mac("bsRuns", str(bs_n))
if os.path.exists(os.path.join(OUT, "distill_ie_f1minusdel.json")):
    AB = load("distill_ie_f1minusdel.json"); ks = [k for k in AB if k.startswith("f1minusdel_s")]
    rec = [AB[k]["fields"]["else"]["recall"] for k in ks]; acc = [100 * AB[k]["accuracy"] for k in ks]
    mac("ablDelN", str(len(ks))); mac("ablDelRec", f"{np.mean(rec):.2f}"); mac("ablDelAcc", f"{np.mean(acc):.1f}")
    mac("ablDelRecMin", f"{min(rec):.2f}"); mac("ablDelRecMax", f"{max(rec):.2f}")
# integrity audit: student predictions, base model, Spider aliases (from saved outputs)
import sys as _sys
_sys.path.insert(0, os.path.join(HERE, "..", "src"))
from soundver import generate as _g
def _misc_preds(path):
    n = t = 0
    for l in open(path):
        o = _g._ie_extract_json(json.loads(l)["output"])
        if isinstance(o, str):
            try:
                o = json.loads(o)
            except ValueError:
                o = None
        if isinstance(o, dict):
            for e_ in (o.get("else") or []):
                if isinstance(e_, str):
                    n += 1; t += e_.istitle()
    return n, t / max(1, n)
for cond, kk in (("f1_baseline", "Fone"), ("certified", "Cert"), ("oracle", "Oracle")):
    n_, t_ = _misc_preds(os.path.join(DATA, "distill", f"gen_ie_{cond}.jsonl"))
    mac(f"stuMiscN{kk}", str(n_)); mac(f"stuMiscTitle{kk}", pct(t_, 0))
RLb = load("rl2_ie.json")["base"]
mac("rlRecBase", f"{RLb['fields']['else']['recall']:.2f}"); mac("rlElseBase", pct(RLb["subgroups"]["has_else_type"]["acc"], 1))
nj = na = 0
for f in glob.glob(os.path.join(DATA, "pools", "pool_sql_*_seed0.items.jsonl")):
    for l in open(f):
        s = json.loads(l)["gold_sql"]
        if re.search(r"\bjoin\b", s, re.I):
            nj += 1; na += bool(re.search(r"\bas\s+T\d", s, re.I))
mac("sqlJoinN", f"{nj:,}".replace(",", "{,}")); mac("sqlJoinAlias", f"{na:,}".replace(",", "{,}"))
mac("delRateFoneMaxOther", pct(max(load(f"robust_{t}.json")["resampling"]["f1"]["deletion_rate"] for t in TASKS if t != "ie"), 1))
# red-team review analyses (existing outputs)
if os.path.exists(os.path.join(OUT, "redteam.json")):
    RT = load("redteam.json")
    GA = RT["gold_admission_f1"]
    mac("rtGaDeletedAny", "yes" if any(GA[t]["zero"]["deleted"] or GA[t]["one_pct"]["deleted"] for t in TASKS) else "no")
    mac("rtGaTakesDeleter", "yes" if GA["ie"]["zero"]["takes_deleter"] or GA["ie"]["one_pct"]["takes_deleter"] else "no")
    mac("rtGaCatchIE", pct(GA["ie"]["one_pct"]["catch"], 1)); mac("rtGaCatchSQLzero", pct(GA["sql"]["zero"]["catch"], 1))
    mac("rtGaAdmSQLzero", str(GA["sql"]["zero"]["admitted"])); mac("rtGaNSQL", str(GA["sql"]["zero"]["of"]))
    FB = RT["fresh_bstruct"]
    for t in FB:
        mac(f"rtFresh{TAG[t]}", pct(FB[t]["gamma_fresh"], 2))
    mac("rtFreshHoldN", str(sum(1 for t in FB if FB[t]["holds"]))); mac("rtFreshN", str(len(FB)))
    go = RT["gold_only_sql_test_gamma"]["mean"]
    mac("rtGoldOnlyTestGammaSQL", pct(go, 1)); mac("rtGoldOnlyRatioSQL", f"{go / float(M['ablGoldClaimSQL']) * 100:.1f}")
    GC = RT["group_certificate"]
    mac("rtGroupCertN", str(sum(1 for t in GC if GC[t]["certified_group"]))); mac("rtGroupUIE", pct(GC["ie"]["U_group_max"], 1))
    mac("rtFoneNoGoldTakes", "yes" if RT["f1_without_gold_ie"]["takes_deleter"] else "no")
def _nlines(path):
    return f"{sum(1 for l in open(path) if l.strip()):,}".replace(",", "{,}")
mac("szFone", _nlines(os.path.join(DATA, "distill", "sft_ie_f1_baseline.jsonl")))
mac("szCert", _nlines(os.path.join(DATA, "distill", "sft_ie_certified.jsonl")))
mac("szOracle", _nlines(os.path.join(DATA, "distill", "sft_ie_oracle.jsonl")))
mac("szAbl", _nlines(os.path.join(DATA, "distill", "ablate", "sft_ie_f1_minus_deleter.jsonl")))
mac("szEvalIE", _nlines(os.path.join(DATA, "distill", "eval_ie_prompts.jsonl")))
mac("szEvalFewnerd", _nlines(os.path.join(DATA, "distill_fewnerd", "eval_fewnerd_prompts.jsonl")))
if os.path.exists(os.path.join(OUT, "figdata_mechanism.json")):
    FD = load("figdata_mechanism.json")
    pts = [(t, p_) for t in FD for p_ in FD[t]["points"]]
    mac("figMechN", str(len(pts)))
    mac("figMechClip", str(sum(1 for t, p_ in pts if p_["precision"] / FD[t]["threshold"] >= 2.95)))
    mac("figMechDanger", str(sum(1 for t, p_ in pts if p_["precision"] < FD[t]["threshold"] and p_["max_wiped"] >= 0.5)))
    mac("figMechDangerInj", str(sum(1 for t, p_ in pts if p_["kind"] == "injected" and p_["precision"] < FD[t]["threshold"] and p_["max_wiped"] >= 0.5)))
RS = load("robust_sql_inject.json")
mac("injDelFoneSQL", pct(RS["resampling"]["f1"]["deletion_rate"], 0))

with open(os.path.join(GEN, "numbers.tex"), "w") as f:
    f.write("% generated by make_numbers.py (v4.1) -- do not edit\n")
    for k, v in sorted(M.items()):
        f.write(f"\\newcommand{{\\{k}}}{{{v}}}\n")
print(f"wrote {len(M)} macros")
