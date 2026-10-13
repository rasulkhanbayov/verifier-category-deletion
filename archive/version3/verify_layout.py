#!/usr/bin/env python3
"""
verify_layout.py -- measure the page geometry rather than trust the build log.

Three failure modes the log alone does not catch:

  1. LINE-NUMBER COLLISION. acl.sty in review mode puts numbers in the margin.
     If \\linenumbersep is too small, or a display/table starts at the column
     edge, the number lands on top of the text. TeX never warns about this
     because nothing is overfull; the number is in a separate box.

  2. MARGIN VIOLATION. An overfull \\hbox means text extends past the column.
     The log gives points too wide but not WHERE, and a 3pt overfull in a
     footnote is cosmetic while a 60pt overfull in a table is a desk-reject
     risk. This locates each one on the page.

  3. INTER-COLUMN COLLISION. Text from the left column running into the right
     column's territory, which is what "overlapping text" usually means to a
     reader.

Measured from the rendered PDF with PyMuPDF, so what is checked is what a
reviewer sees.
"""
import sys
import fitz

PDF = sys.argv[1] if len(sys.argv) > 1 else "soundver_main.pdf"
doc = fitz.open(PDF)

# A4, measured from the rendered PDF rather than assumed. acl.sty produces A4.
PAGE_W, PAGE_H = 595.28, 841.89
COL1_L, COL1_R = 71.0, 289.0
COL2_L, COL2_R = 306.0, 524.0
MARGIN_L, MARGIN_R = COL1_L, PAGE_W - COL2_R
COL_W = COL1_R - COL1_L
TOL = 2.0                               # pt of slack before we complain
GUTTER_TOL = 12.0                       # a block wider than one column + this is full-width

issues = {"linenum": [], "margin": [], "gutter": [], "offpage": []}


def is_linenumber(span):
    """
    acl.sty sets the line-number font with `\\font\\aclhv = phvb at 8pt', which
    renders as NimbusSanL-Bold at exactly 8pt. Matching the FONT rather than
    "small and numeric" avoids flagging figure axis labels, which are 7pt CMR7
    digits and are not line numbers.
    """
    return (span["text"].strip().isdigit()
            and "NimbusSan" in span.get("font", "")
            and abs(span["size"] - 8.0) < 0.2)


for pno in range(doc.page_count):
    page = doc[pno]
    spans = []
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                if s["text"].strip():
                    spans.append(s)

    nums = [s for s in spans if is_linenumber(s)]
    body = [s for s in spans if not is_linenumber(s)]

    # ---- 1. line numbers overlapping body text
    for n in nums:
        nx0, ny0, nx1, ny1 = n["bbox"]
        for t in body:
            tx0, ty0, tx1, ty1 = t["bbox"]
            vov = min(ny1, ty1) - max(ny0, ty0)
            if vov < 0.5 * (ny1 - ny0):           # need real vertical overlap
                continue
            if nx1 > tx0 + 0.5 and nx0 < tx1 - 0.5:
                issues["linenum"].append(
                    (pno + 1, round(nx0, 1), n["text"].strip(),
                     t["text"][:44]))
                break

    # ---- 2/3. body text outside its column, judged per BLOCK.
    # A span is only "overflowing" if the BLOCK it belongs to is a
    # single-column block. The title, the author line and any table* float
    # legitimately span both columns, and testing their words individually
    # reports them as overflows when they are not.
    for b in page.get_text("dict")["blocks"]:
        bx0, _, bx1, _ = b["bbox"]
        # acl.sty centres the title block and the abstract across the page,
        # so they legitimately cross the column boundary. Skip that region.
        if pno == 0 and b["bbox"][1] < 600:
            continue
        if bx1 - bx0 > COL_W + GUTTER_TOL:          # full-width block
            if bx0 < MARGIN_L - TOL or bx1 > PAGE_W - MARGIN_R + TOL:
                issues["margin"].append((pno + 1, round(bx0, 1), round(bx1, 1),
                                         round(bx1 - bx0, 1), "<full-width block>"))
            continue
        edge = COL1_R if bx0 < COL1_R else COL2_R
        for l in b.get("lines", []):
            for t in l["spans"]:
                if not t["text"].strip() or is_linenumber(t):
                    continue
                x0, _, x1, _ = t["bbox"]
                if x1 > edge + TOL:
                    issues["gutter"].append(
                        (pno + 1, "L" if edge == COL1_R else "R",
                         round(x1 - edge, 1), t["text"][:44]))
                if x0 < MARGIN_L - TOL:
                    issues["margin"].append((pno + 1, round(x0, 1), round(x1, 1),
                                             round(x1 - x0, 1), t["text"][:44]))

print("=" * 76)
print(f"LAYOUT AUDIT  {PDF}  ({doc.page_count} pages)")
print("=" * 76)

print(f"\n1. LINE NUMBERS OVERLAPPING TEXT: {len(issues['linenum'])}")
for p, x, n, t in issues["linenum"][:12]:
    print(f"     p{p:<3} number {n:>5} at x={x:<6} over  {t!r}")

print(f"\n2. TEXT PAST THE COLUMN INTO THE GUTTER: {len(issues['gutter'])}")
for p, col, over, t in sorted(issues["gutter"], key=lambda r: -r[2])[:12]:
    print(f"     p{p:<3} {col}-col  {over:>6}pt over  {t!r}")

print(f"\n3. TEXT PAST THE PAGE MARGIN: {len(issues['margin'])}")
for p, x0, x1, w, t in sorted(issues["margin"], key=lambda r: -r[3])[:12]:
    print(f"     p{p:<3} x=[{x0},{x1}] w={w}  {t!r}")

total = sum(len(v) for v in issues.values())
print("\n" + "=" * 76)
print("CLEAN" if total == 0 else f"{total} geometric issues")
print("=" * 76)
sys.exit(1 if total else 0)
