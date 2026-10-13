#!/usr/bin/env python3
"""
verify_figures.py -- geometric audit of every page of the built PDF.

Three checks, none of them visual:
  1. text-vs-text  : pairwise intersection of glyph bounding boxes
  2. text-vs-ink   : every vector stroke flattened to segments and tested against
                     every text box with Liang-Barsky clipping (catches a curve
                     running through a label, which a bbox-vs-bbox test misses)
  3. margin bleed  : any ink or glyph outside the type block
"""
import fitz, sys
from collections import defaultdict

PDF = "soundver_main.pdf"
PAD = 0.6          # shrink glyph boxes to approximate ink, not font padding
MARGIN_TOL = 2.0

def shrink(r, pad=PAD):
    return fitz.Rect(r.x0+pad, r.y0+pad, r.x1-pad, r.y1-pad)

def liang_barsky(x0, y0, x1, y1, rect):
    """True if segment (x0,y0)-(x1,y1) intersects rect."""
    dx, dy = x1-x0, y1-y0
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x0-rect.x0), (dx, rect.x1-x0),
                 (-dy, y0-rect.y0), (dy, rect.y1-y0)):
        if p == 0:
            if q < 0: return False
        else:
            t = q/p
            if p < 0:
                if t > t1: return False
                if t > t0: t0 = t
            else:
                if t < t0: return False
                if t < t1: t1 = t
    return True

def flatten(item):
    """Yield line segments from a drawing item; Beziers -> 8 chords."""
    op = item[0]
    if op == "l":
        yield (item[1].x, item[1].y, item[2].x, item[2].y)
    elif op == "c":
        p0, p1, p2, p3 = item[1], item[2], item[3], item[4]
        prev = (p0.x, p0.y)
        for k in range(1, 9):
            t = k/8
            mt = 1-t
            x = (mt**3*p0.x + 3*mt*mt*t*p1.x + 3*mt*t*t*p2.x + t**3*p3.x)
            y = (mt**3*p0.y + 3*mt*mt*t*p1.y + 3*mt*t*t*p2.y + t**3*p3.y)
            yield (prev[0], prev[1], x, y)
            prev = (x, y)
    elif op == "re":
        r = item[1]
        yield (r.x0, r.y0, r.x1, r.y0); yield (r.x1, r.y0, r.x1, r.y1)
        yield (r.x1, r.y1, r.x0, r.y1); yield (r.x0, r.y1, r.x0, r.y0)

doc = fitz.open(PDF)
tot_tt = tot_ti = tot_mb = 0
per_page = defaultdict(lambda: [0,0,0])

for pno in range(doc.page_count):
    page = doc[pno]
    # glyph boxes
    boxes = []
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                if s["text"].strip():
                    boxes.append((shrink(fitz.Rect(s["bbox"])), s["text"].strip()[:28]))

    # 1. text vs text
    for i in range(len(boxes)):
        for j in range(i+1, len(boxes)):
            a, b = boxes[i][0], boxes[j][0]
            if a.intersects(b):
                inter = fitz.Rect(a); inter.intersect(b)
                if inter.get_area() > 1.0:
                    per_page[pno+1][0] += 1
                    tot_tt += 1
                    if tot_tt <= 12:
                        print(f"  TEXT-TEXT  p{pno+1}: '{boxes[i][1]}' x '{boxes[j][1]}' "
                              f"area={inter.get_area():.1f}")

    # 2. strokes vs text
    segs = []
    for d in page.get_drawings():
        if d.get("stroke") is None:      # fills (shading) are not "lines through labels"
            continue
        for it in d["items"]:
            segs.extend(flatten(it))
    for (r, t) in boxes:
        hits = sum(1 for (x0,y0,x1,y1) in segs if liang_barsky(x0,y0,x1,y1,r))
        if hits:
            per_page[pno+1][1] += hits
            tot_ti += hits
            if tot_ti <= 400 and hits >= 2:
                print(f"  STROKE-TEXT p{pno+1}: {hits:3d} segs through '{t}'")

    # 3. margin bleed
    tb = fitz.Rect(page.rect)
    tb.x0 += 55; tb.x1 -= 55; tb.y0 += 45; tb.y1 -= 45
    for (r, t) in boxes:
        if (r.x0 < tb.x0-MARGIN_TOL or r.x1 > tb.x1+MARGIN_TOL):
            per_page[pno+1][2] += 1; tot_mb += 1
            if tot_mb <= 12:
                print(f"  MARGIN     p{pno+1}: '{t}' x=[{r.x0:.1f},{r.x1:.1f}] "
                      f"block=[{tb.x0:.1f},{tb.x1:.1f}]")

print()
print("="*66)
print("FIGURE / PAGE GEOMETRY SUMMARY")
print("="*66)
print(f"  text-vs-text overlaps ........ {tot_tt}")
print(f"  stroke-through-label hits .... {tot_ti}")
print(f"  margin bleeds ................ {tot_mb}")
print()
worst = sorted(per_page.items(), key=lambda kv: -sum(kv[1]))[:8]
print("  worst pages (tt / stroke / margin):")
for p, v in worst:
    if sum(v): print(f"    p{p:>2}: {v[0]:>4} / {v[1]:>4} / {v[2]:>3}")
