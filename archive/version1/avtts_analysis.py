#!/usr/bin/env python3
"""
avtts_analysis.py
-----------------
Reference implementation of the quantities defined in the AV-TTS paper:
  - sound anatomical verifiers (connectivity/count, containment, Euler characteristic)
  - select-best and verifier-weighted aggregation
  - the monotone safeguard (Proposition 1)
  - bootstrap confidence intervals for paired metric differences

Design notes
  * numpy-only (no scipy/skimage) so it runs anywhere.
  * Everything COMPUTES from inputs. The smoke test builds SYNTHETIC masks with
    known structure to demonstrate expected *behavior*; it does NOT hard-code or
    assert any experimental result from the paper. Real Dice/HD95 numbers come
    only from the runs described in avtts_runbook.txt.

Run:  python3 avtts_analysis.py        # executes the smoke test
"""

import numpy as np


# --------------------------------------------------------------------------
# connected components (4-connectivity) via iterative BFS, numpy arrays only
# --------------------------------------------------------------------------
def connected_components(mask):
    """Return (num_components, label_map) for a 2D binary mask, 4-connectivity."""
    mask = (np.asarray(mask) > 0)
    h, w = mask.shape
    labels = np.zeros((h, w), dtype=np.int32)
    cur = 0
    for i in range(h):
        for j in range(w):
            if mask[i, j] and labels[i, j] == 0:
                cur += 1
                stack = [(i, j)]
                labels[i, j] = cur
                while stack:
                    y, x = stack.pop()
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and labels[ny, nx] == 0:
                            labels[ny, nx] = cur
                            stack.append((ny, nx))
    return cur, labels


def largest_cc_fraction(mask):
    """Fraction of foreground mass inside the largest connected component."""
    mask = (np.asarray(mask) > 0)
    total = mask.sum()
    if total == 0:
        return 1.0
    n, labels = connected_components(mask)
    sizes = [(labels == k).sum() for k in range(1, n + 1)]
    return float(max(sizes)) / float(total)


# --------------------------------------------------------------------------
# Euler number for 2D binary image via 2x2 bit-quad counting (Gray, 1971).
# For 4-connectivity: chi = (Q1 - Q3 - 2*QD) / 4, summed over 2x2 windows.
# This is exact and numpy-vectorized.
# --------------------------------------------------------------------------
def euler_number_2d(mask):
    m = (np.asarray(mask) > 0).astype(np.int32)
    m = np.pad(m, 1, mode="constant")
    a = m[:-1, :-1]; b = m[:-1, 1:]; c = m[1:, :-1]; d = m[1:, 1:]
    s = a + b + c + d
    q1 = np.sum(s == 1)
    q3 = np.sum(s == 3)
    # diagonal configs: exactly the two diagonal pairs among the four corners
    diag1 = (a == 1) & (d == 1) & (b == 0) & (c == 0)
    diag2 = (b == 1) & (c == 1) & (a == 0) & (d == 0)
    qd = np.sum(diag1) + np.sum(diag2)
    return float((q1 - q3 - 2 * qd) / 4.0)


# --------------------------------------------------------------------------
# verifier penalty terms (label-free). Higher V = more plausible; V <= 0,
# V == 0 is a perfect structural match to the stated prior.
# --------------------------------------------------------------------------
def verifier_single_blob(mask, expected_euler=1.0,
                         w_conn=1.0, w_euler=0.5):
    """Sound verifier for a single hole-free blob (e.g. prostate slice)."""
    conn_pen = (1.0 - largest_cc_fraction(mask))            # in [0,1]
    euler_pen = abs(euler_number_2d(mask) - expected_euler)  # >= 0
    return -(w_conn * conn_pen + w_euler * euler_pen)


def verifier_containment(inner, outer, w=1.0):
    """Sound verifier for nested structures: inner should lie within outer."""
    inner = (np.asarray(inner) > 0)
    outer = (np.asarray(outer) > 0)
    m = inner.sum()
    if m == 0:
        return 0.0
    outside = np.logical_and(inner, np.logical_not(outer)).sum()
    return -(w * float(outside) / float(m))                  # in [-1, 0]


# --------------------------------------------------------------------------
# selection rules + monotone safeguard (Proposition 1)
# --------------------------------------------------------------------------
def select_best(candidates, verifier, base_index=0):
    """argmax verifier over candidates, ties broken toward the base (index 0).
    Guarantees V(selected) >= V(base): Proposition 1."""
    scores = np.array([verifier(c) for c in candidates], dtype=float)
    best = scores.argmax()
    if np.isclose(scores[best], scores[base_index]):
        best = base_index
    return best, scores


def verifier_weighted(candidates, verifier, temp=1.0):
    """Soft per-pixel fusion with weights = softmax(V/temp). Returns a mask."""
    scores = np.array([verifier(c) for c in candidates], dtype=float)
    wts = np.exp((scores - scores.max()) / temp)
    wts = wts / wts.sum()
    stack = np.stack([(np.asarray(c) > 0).astype(float) for c in candidates], 0)
    soft = np.tensordot(wts, stack, axes=(0, 0))
    return (soft >= 0.5).astype(np.int32), scores


# --------------------------------------------------------------------------
# evaluation helpers
# --------------------------------------------------------------------------
def dice(pred, gt):
    pred = (np.asarray(pred) > 0); gt = (np.asarray(gt) > 0)
    inter = np.logical_and(pred, gt).sum()
    denom = pred.sum() + gt.sum()
    return 1.0 if denom == 0 else 2.0 * inter / denom


def bootstrap_ci(diffs, n_boot=2000, alpha=0.05, seed=0):
    """Percentile bootstrap CI for the mean of paired per-case differences."""
    rng = np.random.default_rng(seed)
    diffs = np.asarray(diffs, dtype=float)
    n = len(diffs)
    means = np.array([rng.choice(diffs, n, replace=True).mean()
                      for _ in range(n_boot)])
    lo, hi = np.percentile(means, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(diffs.mean()), float(lo), float(hi)


# --------------------------------------------------------------------------
# synthetic generators for the smoke test
# --------------------------------------------------------------------------
def disk(size=64, cx=32, cy=32, r=14):
    yy, xx = np.mgrid[0:size, 0:size]
    return ((yy - cy) ** 2 + (xx - cx) ** 2 <= r ** 2).astype(np.int32)


def add_speck(mask, cx=8, cy=8, r=3):
    out = mask.copy()
    yy, xx = np.mgrid[0:mask.shape[0], 0:mask.shape[1]]
    out[((yy - cy) ** 2 + (xx - cx) ** 2 <= r ** 2)] = 1
    return out


def punch_hole(mask, cx=32, cy=32, r=4):
    out = mask.copy()
    yy, xx = np.mgrid[0:mask.shape[0], 0:mask.shape[1]]
    out[((yy - cy) ** 2 + (xx - cx) ** 2 <= r ** 2)] = 0
    return out


# --------------------------------------------------------------------------
# smoke test: demonstrates EXPECTED BEHAVIOR on controlled synthetic data
# --------------------------------------------------------------------------
def smoke_test():
    print("=== AV-TTS smoke test (synthetic; demonstrates behavior, not results) ===")
    gt = disk()

    clean = disk()                       # matches prior: 1 component, no hole
    specked = add_speck(disk())          # 2 components -> connectivity violation
    holed = punch_hole(disk())           # 1 component but a hole -> euler violation

    v = verifier_single_blob
    print("\n[1] Verifier ranks the structurally clean candidate highest:")
    for name, m in [("clean", clean), ("specked", specked), ("holed", holed)]:
        print(f"    V({name:7s}) = {v(m):+.3f}   "
              f"(largestCC={largest_cc_fraction(m):.3f}, euler={euler_number_2d(m):+.1f})")
    assert v(clean) > v(specked) and v(clean) > v(holed), "clean should score highest"

    print("\n[2] Monotone safeguard (Prop. 1): selected V >= base V, always.")
    candidates = [specked, clean, holed]   # base = index 0 (specked)
    idx, scores = select_best(candidates, v, base_index=0)
    print(f"    base V={scores[0]:+.3f}, selected idx={idx}, selected V={scores[idx]:+.3f}")
    assert scores[idx] >= scores[0] - 1e-9, "safeguard violated"

    print("\n[3] Sound (anatomy) vs UNSOUND proxy vs ORACLE selection.")
    # build candidates where the anatomically clean one is also closest to GT,
    # and craft an unsound proxy = 'pick the largest foreground area'.
    big_blob = disk(r=20)                  # larger area, lower Dice to GT(r=14)
    cands = [specked, clean, holed, big_blob]
    # oracle: select by Dice to GT (uses labels; upper bound only)
    oracle_idx = int(np.argmax([dice(c, gt) for c in cands]))
    # anatomy verifier selection (label-free)
    ana_idx, _ = select_best(cands, v, base_index=0)
    # unsound proxy: largest foreground mass (a stand-in for a miscalibrated signal)
    unsound_idx = int(np.argmax([np.asarray(c).sum() for c in cands]))
    print(f"    oracle picks idx {oracle_idx} (Dice={dice(cands[oracle_idx], gt):.3f})")
    print(f"    anatomy picks idx {ana_idx} (Dice={dice(cands[ana_idx], gt):.3f})")
    print(f"    unsound picks idx {unsound_idx} (Dice={dice(cands[unsound_idx], gt):.3f})")
    assert ana_idx == oracle_idx, "sound verifier should match oracle here"
    assert unsound_idx != oracle_idx, "unsound proxy expected to miss here"

    print("\n[4] Containment verifier flags cup-outside-disc:")
    disc = disk(r=18); cup_in = disk(r=8); cup_out = disk(cx=50, r=8)
    print(f"    V(cup inside)  = {verifier_containment(cup_in, disc):+.3f}")
    print(f"    V(cup outside) = {verifier_containment(cup_out, disc):+.3f}")
    assert verifier_containment(cup_in, disc) > verifier_containment(cup_out, disc)

    print("\n[5] Bootstrap CI on synthetic paired differences:")
    rng = np.random.default_rng(0)
    diffs = rng.normal(0.03, 0.05, size=120)   # synthetic per-case Dice deltas
    mean, lo, hi = bootstrap_ci(diffs)
    print(f"    mean delta={mean:+.4f}, 95% CI=({lo:+.4f}, {hi:+.4f})")

    print("\nAll behavioral checks passed. (These are synthetic demonstrations.)")


if __name__ == "__main__":
    smoke_test()
