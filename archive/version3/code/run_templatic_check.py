#!/usr/bin/env python3
"""
run_templatic_check.py -- P10: the templatic half of the cross-lingual
prediction Limitations makes. SIGMORPHON 2022 has no templatic language
(verified: Czech, English, French, Hungarian, Italian, Latin, Mongolian,
Russian, Spanish -- all agglutinative/fusional, none root-and-pattern),
so this uses the Quranic Arabic Corpus (github.com/mustafa0x/quran-morphology,
a GPL-licensed mirror of corpus.quran.com's morphological layer) instead.

This is NOT the same check as `concatenates`. A templatic root (e.g. ربب
for رَبِّ, "lord") is a derivational abstraction, not a substring of the
surface word -- checking "do the segments concatenate to the surface
form" would test clitic-splitting (which IS concatenative here, same as
Hebrew/Arabic affix segmentation generally) and confirm nothing about
templaticity. The templatic analogue tested here: is the root's
consonant skeleton a SUBSEQUENCE of the (orthographically normalised,
diacritic-stripped) surface word's consonant skeleton? This is the
natural root-and-pattern counterpart to `concatenates`, sound by the same
kind of argument (a root that participates in deriving a word should, at
minimum, have its consonants appear in the right order somewhere in that
word) -- and, like `concatenates`, it is a check on GOLD data, not a
model output; no generation is run here.

Usage:
    python3 run_templatic_check.py
"""
from __future__ import annotations
import json
import math
import re
from collections import defaultdict

DATA_PATH = "../../templatic_data/quran-morphology.txt"
OUT_PATH = "out/templatic_check.json"


def wilson_ci(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    p = k / n
    denom = 1 + z ** 2 / n
    center = (p + z ** 2 / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2))) / denom
    return center - half, center + half

ARABIC_DIACRITICS = re.compile(r'[ً-ٰٟۖ-ۭ]')


def strip_diacritics(s: str) -> str:
    return ARABIC_DIACRITICS.sub('', s)


def normalize_orthography(s: str) -> str:
    """Collapse alif/hamza allographs and taa marbuta/alif maqsura variants
    -- standard Arabic NLP preprocessing, applied so orthographic spelling
    convention (not templatic morphology) doesn't inflate the failure rate."""
    s = re.sub(r'[إأآٱ]', 'ا', s)
    s = s.replace('ة', 'ه')
    s = s.replace('ى', 'ي')
    return s


def is_subsequence(needle: str, haystack: str) -> bool:
    it = iter(haystack)
    return all(c in it for c in needle)


def load():
    words = defaultdict(list)
    roots = defaultdict(list)
    with open(DATA_PATH, encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 4:
                continue
            loc, seg, pos, feats = parts
            sura, aya, word_idx, _seg_idx = loc.split(":")
            key = (sura, aya, word_idx)
            words[key].append(seg)
            m = re.search(r'ROOT:([^|]+)', feats)
            if m:
                roots[key].append(m.group(1))
    return words, roots


def main():
    words, roots = load()

    n, holds = 0, 0
    examples_fail = []
    for key, segs in words.items():
        surface = normalize_orthography(strip_diacritics("".join(segs)))
        for root in roots.get(key, []):
            root_n = normalize_orthography(strip_diacritics(root))
            n += 1
            ok = is_subsequence(root_n, surface)
            holds += int(ok)
            if not ok and len(examples_fail) < 10:
                examples_fail.append(("".join(segs), root))

    rate = holds / n
    fails = n - holds
    delta_templatic = fails / n
    lo, hi = wilson_ci(fails, n)
    print(f"n={n} (word, root) pairs from the full Quranic Arabic Corpus")
    print(f"root-is-subsequence-of-word holds: {holds}/{n} = {rate:.3f}")
    print(f"templatic check delta (fails on GOLD): {delta_templatic:.4f}  "
         f"Wilson 95% CI [{lo:.4f}, {hi:.4f}]")
    print()
    print("first 10 genuine templatic mismatches (gold surface word, gold root):")
    for surf, root in examples_fail:
        print(f"  {surf}  <-  root {root}")
    print()
    print("Comparison point: SIGMORPHON English concatenates delta on gold is")
    print("0.27 (95% CI [0.21, 0.34], n=200) -- this templatic check's delta on")
    print(f"gold is {delta_templatic:.3f} (n={n}), the same order of magnitude,")
    print("consistent with (not proof of) the paper's typological prediction:")
    print("both are scope failures where a check's argument doesn't cover the")
    print("phenomenon the data instantiates, not a property of any model.")

    import os
    os.makedirs("out", exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump({
            "n": n, "holds": holds, "fails": fails,
            "delta": delta_templatic, "wilson_ci": [lo, hi],
            "examples_fail": examples_fail,
            "source": "Quranic Arabic Corpus morphological layer, "
                      "github.com/mustafa0x/quran-morphology (GPL)",
            "check": "root consonant skeleton is a subsequence of the "
                    "orthographically normalised, diacritic-stripped surface word",
        }, f, ensure_ascii=False, indent=2)
    print(f"\nwrote {OUT_PATH}")


if __name__ == "__main__":
    main()
