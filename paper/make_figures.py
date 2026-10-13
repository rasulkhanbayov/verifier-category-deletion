"""
make_figures.py -- figures for the paper, from ../out/ only.

  python paper/make_figures.py      (needs matplotlib; see requirements.txt)

fig_downstream.pdf: miscellaneous-entity recall on the CoNLL test set (555
inputs) for (a) distilled Qwen3-0.6B students and (b) GRPO policies, one
point per training seed or subsample, a bar at the mean. Values are read
from the same files as Table 3 (make_numbers.py).
"""
import json, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "out")
GEN = os.path.join(HERE, "gen")


def load(n):
    return json.load(open(os.path.join(OUT, n)))


def rec(d, keys):
    return [d[k]["fields"]["else"]["recall"] for k in keys]


def seeds(d, prefix):
    return sorted(k for k in d if k == prefix or (k.startswith(prefix + "_s") and k[len(prefix) + 2:].isdigit()))


DS = load("distill_ie_seeds.json"); AB = load("distill_ie_f1minusdel.json")
MT = load("distill_ie_matched.json"); D0 = load("distill_ie.json"); RL = load("rl2_ie_seeds.json")

# Okabe-Ito colours, plus distinct markers for greyscale readers
F1C, ABC, CEC, MAC, LAC = "#D55E00", "#E69F00", "#0072B2", "#56B4E9", "#444444"
panel_a = [("F1", rec(DS, seeds(DS, "f1_baseline")), F1C, "o"),
           ("F1 w/o\ncheck", rec(AB, [k for k in AB if k.startswith("f1minusdel_s")]), ABC, "D"),
           ("Cert.", rec(DS, seeds(DS, "certified")), CEC, "s"),
           ("Cert.,\nmatched", rec(MT, [k for k in MT if k.startswith("certmatched_s")]), MAC, "^"),
           ("Label", rec(D0, ["oracle"]), LAC, "v")]
start = rec(RL, ["sftinit"])[0]
panel_b = [("Label", rec(RL, seeds(RL, "rl2_label")), LAC, "v"),
           ("Cert.", rec(RL, seeds(RL, "rl2_certified")), CEC, "s"),
           ("F1", rec(RL, seeds(RL, "rl2_f1")), F1C, "o")]

plt.rcParams.update({"font.size": 7, "axes.titlesize": 7.5, "axes.labelsize": 7, "xtick.labelsize": 6.2,
                     "ytick.labelsize": 6.5, "font.family": "serif", "pdf.fonttype": 42})
fig, axes = plt.subplots(1, 2, figsize=(3.3, 1.95), gridspec_kw={"width_ratios": [5, 3]}, sharey=True)


def draw(ax, rows, title):
    for i, (lab, vals, col, mk) in enumerate(rows):
        x = i + np.linspace(-0.12, 0.12, len(vals)) if len(vals) > 1 else np.array([i])
        ax.scatter(x, vals, s=14, color=col, marker=mk, edgecolor="black", linewidth=0.4, zorder=3)
        ax.hlines(np.mean(vals), i - 0.28, i + 0.28, color=col, linewidth=1.6, zorder=2)
    ax.set_xticks(range(len(rows))); ax.set_xticklabels([r[0] for r in rows])
    ax.set_xlim(-0.6, len(rows) - 0.4); ax.set_title(title, pad=3)
    ax.grid(axis="y", linewidth=0.3, alpha=0.6); ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


draw(axes[0], panel_a, "(a) Distillation filter")
draw(axes[1], panel_b, "(b) RL reward gate")
axes[1].axhline(start, color=LAC, linestyle="--", linewidth=0.8, zorder=1)
axes[1].text(len(panel_b) - 0.45, start + 0.012, "start", fontsize=6, ha="right", va="bottom", color=LAC)
axes[0].set_ylabel("Misc.\\ entity recall".replace("\\ ", " "))
axes[0].set_ylim(0, 0.6); axes[0].set_yticks([0, 0.2, 0.4, 0.6])
fig.tight_layout(pad=0.3, w_pad=0.6)
os.makedirs(GEN, exist_ok=True)
fig.savefig(os.path.join(GEN, "fig_downstream.pdf"))
fig.savefig(os.path.join(GEN, "fig_downstream.png"), dpi=300)
print("panel a:", [(r[0].replace("\n", " "), [round(v, 3) for v in r[1]]) for r in panel_a])
print("panel b:", [(r[0].replace("\n", " "), [round(v, 3) for v in r[1]]) for r in panel_b], "start", round(start, 3))


# ======================================================================
# Shared helpers for the additional figures
# ======================================================================
import re
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

MAC = dict(re.findall(r'\\newcommand\{\\(\w+)\}\{(.*)\}', open(os.path.join(GEN, "numbers.tex")).read()))


def m(k):
    """number from gen/numbers.tex, LaTeX markup removed"""
    return MAC[k].replace("$\\pm$", "±").replace("$-$", "−").replace("{,}", ",")


TASKS = ["ie", "fewnerd", "fc", "sql", "math", "morph"]
TNAME = {"ie": "CoNLL", "fewnerd": "Few-NERD", "fc": "Func. call", "sql": "SQL", "math": "GSM8K", "morph": "Morph."}


def clean(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(linewidth=0.3, alpha=0.6); ax.set_axisbelow(True)


# ----------------------------------------------------------------------
# fig_mechanism: the two ingredients of deletion
# ----------------------------------------------------------------------
MD = json.load(open(os.path.join(OUT, "figdata_mechanism.json")))
fig, ax = plt.subplots(figsize=(3.3, 2.35))
ax.axvspan(0, 1, ymin=0.5 / 1.05, ymax=1, color="#D55E00", alpha=0.08, lw=0)
ax.axvline(1, color="black", lw=0.7, ls="--"); ax.axhline(0.5, color="black", lw=0.7, ls=":")
style = {"pool": dict(s=7, color="#9a9a9a", marker="o", alpha=0.55, lw=0, zorder=2, label="LLM-written candidates"),
         "feedback": dict(s=7, color="#9a9a9a", marker="o", alpha=0.55, lw=0, zorder=2),
         "injected": dict(s=26, color="#E69F00", marker="D", edgecolor="black", lw=0.4, zorder=4, label="Few-NERD stress test"),
         "casing": dict(s=40, color="#56B4E9", marker="P", edgecolor="black", lw=0.4, zorder=5, label="Few-NERD casing check"),
         "deleter": dict(s=70, color="#D55E00", marker="*", edgecolor="black", lw=0.4, zorder=6, label="CoNLL deleting check")}
seen = set()
for t in TASKS:
    thr = MD[t]["threshold"]
    for p in MD[t]["points"]:
        k = p["kind"]; st = dict(style[k])
        lab = st.pop("label", None)
        if lab in seen or k == "feedback":
            lab = None
        seen.add(lab)
        ax.scatter(min(p["precision"] / thr, 2.95), p["max_wiped"], label=lab, **st)
ax.set_xlim(0, 3); ax.set_ylim(0, 1.05)
ax.set_xlabel("precision of rejected outputs / (F1/2)")
ax.set_ylabel("largest share of a group lost")
ax.text(0.5, 0.72, "agreement takes it,\ncategory lost", ha="center", va="center", fontsize=5.8, color="#8a3500")
ax.text(1.05, 0.44, "lowers F1 $\\rightarrow$", fontsize=5.6, ha="left", va="center")
ax.text(0.95, 0.44, "$\\leftarrow$ raises F1", fontsize=5.6, ha="right", va="center")
ax.legend(fontsize=5.4, loc="lower right", bbox_to_anchor=(1.0, 0.08), frameon=True, framealpha=0.92, edgecolor="none", handletextpad=0.2, borderaxespad=0.2)
clean(ax); fig.tight_layout(pad=0.3)
fig.savefig(os.path.join(GEN, "fig_mechanism.pdf")); fig.savefig(os.path.join(GEN, "fig_mechanism.png"), dpi=300)
plt.close(fig)
print("mechanism: points in danger zone:",
      sorted((t, p["kind"]) for t in TASKS for p in MD[t]["points"] if p["precision"] < MD[t]["threshold"] and p["max_wiped"] >= 0.5))

# ----------------------------------------------------------------------
# fig_validity: certified bound vs test gamma (dev draws and fresh draw)
# ----------------------------------------------------------------------
RT = json.load(open(os.path.join(OUT, "redteam.json")))
fig, ax = plt.subplots(figsize=(3.3, 2.0))
for i, t in enumerate(TASKS):
    R = json.load(open(os.path.join(OUT, f"robust_{t}.json")))
    b = RT["group_certificate"][t]["tau"]
    row = [r for r in R["rows"] if r["selection"] == "budgeted" and abs((r["budget"] or 0) - b) < 1e-9][0]
    U = 100 * row["B"]["U"]; tg = [100 * g for g in row["test_gamma"]]
    ax.hlines(U, i - 0.32, i + 0.32, color="black", lw=1.6, zorder=3, label="certified bound $U_B$" if i == 0 else None)
    ax.scatter(i + np.array([-0.12, 0, 0.12])[:len(tg)], tg, s=14, color="#0072B2", edgecolor="black", lw=0.4, zorder=4,
               label="test draws (200 inputs)" if i == 0 else None)
    if t in RT["fresh_bstruct"]:
        fv = 100 * RT["fresh_bstruct"][t]["gamma_fresh"]
        ax.scatter(i + 0.24, fv, s=26, marker="D", color="#D55E00" if fv > U else "#E69F00", edgecolor="black", lw=0.4,
                   zorder=5, label="fresh draw (300 inputs)" if t == "ie" else None)
ax.set_xticks(range(len(TASKS))); ax.set_xticklabels([TNAME[t].replace("Func. call", "Func.\ncall") for t in TASKS], fontsize=6)
ax.set_ylabel(r"$\gamma$ (%)"); ax.set_ylim(0, None)
ax.legend(fontsize=5.6, frameon=False, loc="upper right"); clean(ax); fig.tight_layout(pad=0.3)
fig.savefig(os.path.join(GEN, "fig_validity.pdf")); fig.savefig(os.path.join(GEN, "fig_validity.png"), dpi=300)
plt.close(fig)

# ----------------------------------------------------------------------
# fig_cost: certified minus F1 gated accuracy, fresh test data
# ----------------------------------------------------------------------
MODELS = [("meta-llama/llama-3.1-70b-instruct", "Llama-70B", "o"), ("openai/gpt-4o-mini-2024-07-18", "4o-mini", "s"),
          ("qwen/qwen-2.5-72b-instruct", "Qwen-72B", "^")]
fig, ax = plt.subplots(figsize=(3.3, 2.1))
for i, t in enumerate(TASKS):
    Rp = json.load(open(os.path.join(OUT, f"report_{t}_fresh.json")))
    for j, (mid, mn, mk) in enumerate(MODELS):
        if mid not in Rp["by_model"]:
            continue
        d, lo, hi = [100 * v for v in Rp["by_model"][mid]["cert_minus_f1"]]
        y = i + (j - 1) * 0.22
        ax.plot([lo, hi], [y, y], color="#0072B2", lw=1.0)
        ax.scatter(d, y, marker=mk, s=16, color="#0072B2", edgecolor="black", lw=0.4, zorder=3, label=mn if i == 0 else None)
ax.axvline(0, color="black", lw=0.7)
ax.set_yticks(range(len(TASKS))); ax.set_yticklabels([TNAME[t] for t in TASKS], fontsize=6); ax.invert_yaxis()
ax.set_xlabel("certified − F1 gated accuracy (points, 95% CI)")
ax.legend(fontsize=5.6, frameon=False, loc="lower left"); clean(ax); fig.tight_layout(pad=0.3)
fig.savefig(os.path.join(GEN, "fig_cost.pdf")); fig.savefig(os.path.join(GEN, "fig_cost.png"), dpi=300)
plt.close(fig)
print("validity, cost written")


# ----------------------------------------------------------------------
# fig_overview: the two paths from one candidate pool (numbers from gen/numbers.tex)
# ----------------------------------------------------------------------
def mean_only(s):
    return s.split("±")[0]


RED, BLUE, GREY = "#D55E00", "#0072B2", "#555555"
fig, ax = plt.subplots(figsize=(6.6, 2.15)); ax.set_xlim(0, 100); ax.set_ylim(0, 32); ax.axis("off")


def box(x, y, w, h, text, col, fc="white", fs=6.3, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.25,rounding_size=1.2", lw=0.9, ec=col, fc=fc))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, color="black",
            fontweight="bold" if bold else "normal", wrap=True, linespacing=1.15)


def arrow(x0, y0, x1, y1, col):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=7, lw=0.9, color=col))


XS, W = (21.5, 41.5, 61.5, 81.5), 18
box(0.3, 9.5, 17.5, 13, "LLM-written\ncandidate checks\n\n“proper nouns do not\nbelong in the\nmiscellaneous field”", GREY, fc="#f4f4f4", fs=5.9)
top = ["Select by\nagreement (F1)",
       f"check selected:\nrejected outputs\n{float(MAC['precIEElse']):.0%} correct < F1/2 = {float(MAC['thrIE']):.0%}",
       f"filter discards every\ncorrect output for\n{m('frSubPctFoneIEHasElseType')}% of sentences\nwith a misc. entity",
       f"category lost\nstudent recall {m('dsRecFone')}\nRL recall {m('rlRecInit')} → {mean_only(m('rlRecFone'))}"]
bot = ["Select under a budget\n$\\hat\\gamma_A \\leq \\tau/2$",
       "check refused:\nit would exceed\nthe budget",
       "certify γ on held-out\nmodel outputs\n(Clopper–Pearson $U_B$)",
       f"category kept\nstudent recall {m('dsRecCert')}\nRL recall {mean_only(m('rlRecCert'))}"]
for k, (x, tt, bb) in enumerate(zip(XS, top, bot)):
    edge = k in (0, 3)
    box(x, 19.5, W, 11, tt, RED, fc="#fbe9df" if edge else "white", fs=5.9, bold=(k == 0))
    box(x, 1.5, W, 11, bb, BLUE, fc="#e3eef8" if edge else "white", fs=5.9, bold=(k == 0))
arrow(18.3, 18.5, 21.2, 23.5, RED); arrow(18.3, 13.5, 21.2, 8.5, BLUE)
for x in XS[:-1]:
    arrow(x + W + 0.3, 25, x + 20 - 0.3, 25, RED); arrow(x + W + 0.3, 7, x + 20 - 0.3, 7, BLUE)
fig.tight_layout(pad=0.1)
fig.savefig(os.path.join(GEN, "fig_overview.pdf")); fig.savefig(os.path.join(GEN, "fig_overview.png"), dpi=300)
plt.close(fig)
print("overview written")
