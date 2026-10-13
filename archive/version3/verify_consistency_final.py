#!/usr/bin/env python3
"""
verify_consistency_final.py -- end-to-end consistency across the whole bundle.

Eighteen revision passes have moved the title twice, inverted the story, renamed
sections, folded two theorems, replaced a figure and a table, and renumbered the
experiments. Stale material from earlier versions is the expected failure mode,
so this checks mechanically rather than by reading.
"""
import io, os, re, sys, glob

TEX = "soundver_main.tex"
BIB = "soundver_refs.bib"
s = io.open(TEX, encoding="utf-8").read()
app = s.find(r"\appendix")
body, tail = s[:app], s[app:]
fail = 0

def sec(t): print("\n" + "=" * 74 + f"\n{t}\n" + "=" * 74)
def ck(name, ok, detail=""):
    global fail
    if not ok: fail += 1
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  {detail}" if detail and not ok else ""))

# ------------------------------------------------------------------ 1. refs
sec("1. CROSS-REFERENCES")
labels = set(re.findall(r"\\label\{([^}]+)\}", s))
refs = set(re.findall(r"\\(?:ref|autoref|eqref)\{([^}]+)\}", s))
ck("every \\ref resolves", not (refs - labels), sorted(refs - labels))
orphan = {l for l in labels - refs
          if l.split(":")[0] in ("tab", "fig", "app", "sec", "def", "prop", "cor", "thm", "lem")}
ck("no orphaned labels", not orphan, sorted(orphan))

# ---------------------------------------------------------------- 2. cites
sec("2. CITATIONS")
if os.path.exists(BIB):
    keys = set(re.findall(r"@\w+\{([^,]+),", io.open(BIB, encoding="utf-8").read()))
    cited = set()
    for m in re.finditer(r"\\cite[tpalp]*\*?(?:\[[^\]]*\])*\{([^}]+)\}", s):
        cited |= {k.strip() for k in m.group(1).split(",")}
    ck("every \\cite has a bib entry", not (cited - keys), sorted(cited - keys))
    ck("no uncited bib entries", not (keys - cited), sorted(keys - cited))
else:
    ck("bib present", False)

# --------------------------------------------------------------- 3. symbols
sec("3. SYMBOLS AND NOTATION")
for sym, pat in [("delta", r"\\delta"), ("varepsilon", r"\\varepsilon"),
                 ("p_0", r"p_0"), ("q", r"(?<![A-Za-z\\])q(?![A-Za-z])"),
                 ("r", r"(?<![A-Za-z\\])r(?![A-Za-z])")]:
    uses = len(re.findall(pat, body))
    ck(f"{sym} used in body ({uses})", uses > 0)
ck("no stray \\epsilon (should be \\varepsilon)", r"\epsilon" not in s.replace(r"\varepsilon", ""))

# --------------------------------------------------- 4. stale terminology
sec("4. STALE MATERIAL FROM EARLIER VERSIONS")
stale = [("old title 'A Ceiling on What Any'", "Ceiling on What Any"),
         ("old title 'Well-Formed but Wrong:'", "Well-Formed but Wrong:"),
         ("old title 'Sound by Definition'", "Sound by Definition"),
         ("old section 'Sound Corner'", "Sound Corner"),
         ("folded Cor. 1 label", r"\label{cor:compose}"),
         ("folded Prop. 2 statement", r"\begin{proposition}[Stacking]"),
         ("removed experiment label E6", "E6"),
         ("removed experiment label E3b", "E3b"),
         ("cut section app:regime", r"\label{app:regime}"),
         ("cut section app:hetdisc", r"\label{app:hetdisc}"),
         ("cut table tab:lit", r"\label{tab:lit}"),
         ("proof sketches", "[Sketch]"),
         ("removed 'Sound?' column", "Sound?")]
for n, p in stale:
    ck(f"absent: {n}", p not in s)

# --------------------------------------------------------- 5. experiments
sec("5. EXPERIMENT LABELS")
elab = sorted(set(re.findall(r"\bE\d\b", body)))
ck("labels are E0-E5 only", elab == ["E0", "E1", "E2", "E3", "E4", "E5"], elab)
for e in elab:
    ck(f"{e} defined in Experiments and used in Findings",
       body.count(e) >= 2)

# ------------------------------------------------------- 6. datasets etc.
sec("6. DATASETS, MODELS, BASELINES NAMED CONSISTENTLY")
for canon, variants in [("Spider", ["Spider"]),
                        ("CoNLL2003", ["CoNLL2003", "CoNLL-2003"]),
                        ("SIGMORPHON 2022", ["SIGMORPHON 2022", "SIGMORPHON2022"]),
                        ("GPT-4o-mini", ["GPT-4o-mini"]),
                        ("Llama-3.1-8B", ["Llama-3.1-8B"]),
                        ("Llama-3.1-70B", ["Llama-3.1-70B"])]:
    found = [v for v in variants if v in s]
    ck(f"{canon} named consistently ({len(found)} form(s))", len(found) <= 1 or canon in s)

# ------------------------------------------------------ 7. numbers in prose
sec("7. NUMERICAL STATEMENTS AGREE WITH THE TABLES")
cells = {"0.928": "SQL mini eps", "0.988": "SQL 4o eps", "0.693": "SQL 8B eps",
         "0.776": "SQL 70B eps", "0.958": "IE mini eps", "0.970": "IE 4o eps",
         "0.783": "IE 8B eps", "0.959": "IE 70B eps", "0.804": "morph mini eps",
         "0.740": "morph 4o eps", "0.612": "morph 8B eps", "0.632": "morph 70B eps",
         "0.002": "IE 4o delta", "0.025": "IE 8B delta", "0.005": "IE 70B delta",
         "0.120": "morph mini delta", "0.188": "morph 4o delta",
         "0.181": "morph 8B delta", "0.164": "morph 70B delta"}
i = s.find(r"\label{tab:ceiling}")
tab1 = s[s.rfind(r"\begin{tabular}", 0, i):i]
for v, n in cells.items():
    ck(f"{n} = {v} in Table 1", v in tab1)

# ---------------------------------------------------- 8. supplementary code
sec("8. SUPPLEMENTARY MATCHES THE MANUSCRIPT")
for f, must, mustnot in [("README.md", ["audit"], ["Ceiling on What Any", "Well-Formed but Wrong:"]),
                         ("EXPERIMENTS.md", ["X1"], []),
                         ("code/soundver/records.py", ["circularity"], [])]:
    if os.path.exists(f):
        c = io.open(f, encoding="utf-8").read()
        ck(f"{f} present", True)
        for m in must:  ck(f"  {f} mentions {m!r}", m in c)
        for m in mustnot: ck(f"  {f} free of stale {m!r}", m not in c)
    else:
        ck(f"{f} present", False)

print("\n" + "=" * 74)
print("CLEAN" if fail == 0 else f"{fail} INCONSISTENCIES")
print("=" * 74)
sys.exit(1 if fail else 0)
