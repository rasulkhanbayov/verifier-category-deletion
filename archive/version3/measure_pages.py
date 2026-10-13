#!/usr/bin/env python3
"""
measure_pages.py -- measure the ARR/COLING main body of the built PDF.

Main body = title through the end of the last numbered section (Conclusion).
Limitations, Ethics, References and the appendix are excluded, per ARR policy.
Column-aware, so a heading in the right column of page 3 counts as 3.5, not 3.
"""
import fitz, sys

PDF = sys.argv[1] if len(sys.argv) > 1 else "soundver_main.pdf"
LIMIT = float(sys.argv[2]) if len(sys.argv) > 2 else 8.0

d = fitz.open(PDF)
H = d[0].rect.height
hits = []
for i in range(d.page_count):
    spans = []
    for b in d[i].get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for sp in l["spans"]:
                if sp["text"].strip():
                    spans.append(sp)
    spans.sort(key=lambda sp: (0 if sp["bbox"][0] < 300 else 1, sp["bbox"][1]))
    for sp in spans:
        t = sp["text"].strip()
        if sp["size"] > 11.4 and len(t) < 40:
            col = 0 if sp["bbox"][0] < 300 else 1
            hits.append((i + col * 0.5 + (sp["bbox"][1] / H) * 0.5, i + 1, t))

WANT = ["Introduction", "Related", "Setup", "What", "Experiments",
        "Findings", "Conclusion", "Limitations", "References"]
NAME = {"Introduction": "1 Introduction", "Related": "2 Related Work",
        "Setup": "3 Setup", "What": "4 Theory",
        "Experiments": "6 Experiments", "Findings": "7 Findings",
        "Conclusion": "8 Conclusion", "Limitations": "Limitations",
        "References": "References"}
mark = {}
for pos, pg, t in hits:
    for k in WANT:
        if t.startswith(k) and k not in mark and pos > 0.2:
            mark[k] = pos
# Section 5 heading is "Sound Verifier Stacks"; find it after Section 4
for pos, pg, t in hits:
    if t.startswith("Sound") and "What" in mark and pos > mark["What"]:
        mark["Stacks"] = pos
        break

order = ["Introduction", "Related", "Setup", "What", "Stacks",
         "Experiments", "Findings", "Conclusion", "Limitations"]
NAME["Stacks"] = "5 Stacks"

print(f"{'section':22s} {'start':>7s} {'pages':>7s}")
print("-" * 40)
front = mark["Introduction"]
print(f"{'front (title+abs+Fig1)':22s} {0.0:7.2f} {front:7.2f}")
for a, b in zip(order, order[1:]):
    if a in mark and b in mark:
        print(f"{NAME[a]:22s} {mark[a]:7.2f} {mark[b]-mark[a]:7.2f}")

body = mark["Limitations"]
print("-" * 40)
print(f"{'MAIN BODY':22s} {'':7s} {body:7.2f}")
print(f"{'LIMIT':22s} {'':7s} {LIMIT:7.2f}")
delta = body - LIMIT
if delta > 0.02:
    print(f"\n  OVER by {delta:.2f} pages  -- still a desk-reject risk")
    sys.exit(1)
print(f"\n  WITHIN LIMIT, {abs(delta):.2f} pages of headroom")
sys.exit(0)
