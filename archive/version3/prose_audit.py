#!/usr/bin/env python3
"""
prose_audit.py -- measure the prose before rewriting it.

Fifteen passes of surgical replacement is precisely how a manuscript acquires
tics: the editor's own constructions accumulate, seams go unread, and
over-compression turns sentences telegraphic. This measures rather than guesses.
"""
import io, re, sys
from collections import Counter

s = io.open("soundver_main.tex", encoding="utf-8").read()
app = s.find(r"\appendix")
body = s[:app]

# strip LaTeX to approximate readable prose
def strip(t):
    t = re.sub(r"\\begin\{(figure|table|tikzpicture|tabular|align|equation)\*?\}.*?\\end\{\1\*?\}", " ", t, flags=re.S)
    t = re.sub(r"\\(cite[tp]?|citealp|ref|label|miss|textcolor)\{[^}]*\}", " X ", t)
    t = re.sub(r"\$[^$]*\$", " M ", t)
    t = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^}]*\})?", " ", t)
    t = re.sub(r"[{}%]", " ", t)
    return re.sub(r"\s+", " ", t).strip()

prose = strip(body)
sents = [x.strip() for x in re.split(r"(?<=[.!?])\s+(?=[A-Z])", prose) if len(x.split()) > 3]
lens = [len(x.split()) for x in sents]
mean = sum(lens)/len(lens)
var = (sum((l-mean)**2 for l in lens)/len(lens))**0.5

print("="*72); print("SENTENCE LENGTH"); print("="*72)
print(f"  sentences: {len(sents)}   mean {mean:.1f} words   sd {var:.1f}   range {min(lens)}-{max(lens)}")
print("  human academic range is roughly sd 9-14; uniform length is the")
print("  classic generated-text signature.")
print(f"  verdict: {'OK' if 8 < var < 16 else 'CHECK'}")
long_ = [x for x in sents if len(x.split()) > 45]
print(f"  sentences over 45 words: {len(long_)}")
for x in long_[:4]: print(f"    ({len(x.split())}w) {x[:110]}...")

print()
print("="*72); print("FORMULAIC / LLM PHRASING"); print("="*72)
tells = ["it is important to note","it is worth noting","notably","importantly",
         "arguably","furthermore","moreover","additionally","in conclusion",
         "delve","leverage","underscore","showcase","nuanced","realm","landscape",
         "tapestry","robustly","crucial","pivotal","vital","seamless","novel approach",
         "we propose a novel","state-of-the-art","significantly better",
         "in this section, we","this allows us to","to this end","in order to",
         "a wide range of","plays a role","not only"]
found = [(t, prose.lower().count(t)) for t in tells if prose.lower().count(t)]
print("  " + ("none found" if not found else ""))
for t,c in sorted(found, key=lambda x:-x[1]): print(f"    {t:26s} {c}")

print()
print("="*72); print("EDITOR TICS (constructions I may have accumulated)"); print("="*72)
tics = {
  "rather than": r"\brather than\b",
  "which is/which suggests": r"\bwhich (is|suggests|means|makes)\b",
  "colon-then-reveal": r"[a-z]: [a-z]",
  "semicolon": r";",
  "sentence-initial But/And/So": r"(?:^|(?<=[.!?] ))(But|And|So|Yet)\b",
  "exactly (intensifier)": r"\bexactly\b",
  "precisely": r"\bprecisely\b",
  "plainly/plain": r"\bplainl?y?\b",
  "that is/namely": r"\b(that is|namely)\b",
  "not X but Y": r"\bnot [a-z ]{3,20} but\b",
  "parenthetical dash": r" -- ",
  "em dash": "\u2014",
}
for k, p in tics.items():
    n = len(re.findall(p, prose))
    per1k = 1000*n/len(prose.split())
    flag = "  <-- high" if per1k > 6 else ""
    print(f"    {k:28s} {n:4d}   ({per1k:.1f} per 1k words){flag}")

print()
print("="*72); print("REPEATED PHRASES (4-grams appearing 3+ times)"); print("="*72)
w = re.findall(r"[a-z']+", prose.lower())
grams = Counter(" ".join(w[i:i+4]) for i in range(len(w)-3))
rep = [(g,c) for g,c in grams.most_common(40) if c >= 3 and not any(
    x in g for x in ("of the","in the","to the","for the","and the","the ceiling is"))]
print("  " + ("none" if not rep else ""))
for g,c in rep[:14]: print(f"    {c}x  {g}")

print()
print("="*72); print("SECTIONING DENSITY"); print("="*72)
paras = re.findall(r"\\paragraph\{([^}]*)\}", body)
secs  = re.findall(r"\\(?:sub)?section\*?\{([^}]*)\}", body)
print(f"  \\section headings in body : {len(secs)}")
print(f"  \\paragraph headings       : {len(paras)}")
print(f"  words per paragraph heading: {len(prose.split())//max(len(paras),1)}")
print("  (under ~90 words per heading suggests over-sectioning)")
for p in paras: print(f"    - {p[:66]}")
