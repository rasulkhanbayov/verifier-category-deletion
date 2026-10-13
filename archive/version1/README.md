# AV-TTS: Anatomy-Verified Test-Time Scaling — student bundle

This bundle contains a **submission-shaped but results-pending** paper, the
analysis/metrics code, a runnable experiment harness, and a style file. The
research idea is carved and the draft is written; **the experiments are yours to
run**, and every number in the paper is a placeholder until you produce it.

> One-line idea: medical-image segmentation gives a *sound, label-free* verifier
> (containment, connectivity, Euler characteristic), so generate-many-and-select
> (test-time scaling) can work reliably under domain shift, unlike the learned
> verifiers that bottleneck the same recipe in language models. We never update
> weights, and a safeguard guarantees we never return a mask the verifier ranks
> below the base prediction.

---

## 1. What is in this bundle

| File | What it is |
|---|---|
| `avtts_main.tex` | The paper source (generic two-column build). |
| `avtts.sty` | Shared style file: packages, integrity macros (`\rp`, `\torun`), theorem envs, line-number fix. `\usepackage{avtts}`. |
| `avtts_refs.bib` | Bibliography. Entries flagged `VERIFY` need their full author lists confirmed before submission. |
| `avtts_main.bbl` | Pre-built bibliography so the paper compiles without re-running BibTeX. |
| `avtts_main_lncs.tex` | Single-column **LNCS-geometry preview** for the MICCAI page budget (approximation, not the official class). |
| `avtts_analysis.py` | Reference implementation of the verifiers, selection, safeguard, bootstrap CI. numpy-only. Has a synthetic smoke test. |
| `avtts_experiments.py` | Runnable harness for the two gating experiments (E1 oracle headroom, E2 soundness isolation). Runs on synthetic data now; you plug in your model/data. |
| `avtts_runbook.txt` | The full experiment protocol: datasets, baselines, metrics, flag-back triggers, integrity rules. **Read this before running anything.** |
| `README.md` | This file. |

---

## 2. Compile the paper

You need a TeX distribution (TeX Live / MiKTeX) with `pdflatex` and `bibtex`.
`avtts.sty` must sit in the same folder as the `.tex`.

```bash
pdflatex avtts_main
bibtex   avtts_main
pdflatex avtts_main
pdflatex avtts_main
```

A pre-built `avtts_main.bbl` is included, so if you do not want to run BibTeX,
two `pdflatex` passes alone will resolve all citations.

**For MICCAI submission:** this draft is venue-neutral. Download the official
`llncs.cls` from the MICCAI author kit and paste the content into it. The
included `avtts_main_lncs.tex` is only a geometry approximation to gauge length —
it currently runs to ~11 pages, and MICCAI allows **8 pages of content + up to 2
pages of references**, so plan to trim roughly one page (tighten the method
prose; move per-benchmark verifier definitions and a minor figure to the
supplement).

---

## 3. Run the code

Python 3.9+ with `numpy` (and `scipy` for the significance test).

```bash
python3 avtts_analysis.py       # smoke test: verifiers, safeguard, selection behavior
python3 avtts_experiments.py    # E1 + E2 on synthetic data (a BEHAVIOR check, not results)
```

The synthetic output demonstrates the intended pattern (oracle headroom is
positive; the anatomy verifier recovers most of it; entropy selection can be
worse than base). **These synthetic numbers are not paper results and must never
be reported as such.** They only prove the harness is correct.

---

## 4. Plug in your model and data (to get real numbers)

Open `avtts_experiments.py` and implement the two hooks marked `TODO: REAL DATA`:

1. **`generate_candidates(image, model)`** — run your *frozen* segmenter with `N`
   label-free perturbations (flips, multi-scale, gamma jitter, MC-dropout) and
   return the candidate masks plus a per-candidate predictive-entropy value.
   `candidates[0]` must be the unperturbed (base) prediction.
2. **`load_cases(dataset, split)`** — yield `Case` objects from your benchmark
   (prostate / optic cup-disc / cardiac). Pick the verifier per dataset:
   `verifier_single_blob` (prostate), `verifier_containment` (optic cup/disc),
   or an annulus/Euler verifier (cardiac).

Everything else — the four selectors (base / entropy / anatomy / oracle), the
oracle, headroom accounting, bootstrap CIs, Wilcoxon significance, per-seed
variance — is already implemented.

---

## 5. Recommended workflow (do these in order)

1. **Run E1 (oracle headroom) on one dataset first.** If the oracle barely beats
   the base, there is no headroom and no verifier can help — **stop and re-scope**
   before investing further. This is the cheapest experiment and the real gate.
2. **Run E2 (soundness isolation).** The whole thesis is that the anatomy verifier
   recovers the headroom while entropy (an unsound proxy) does not. If anatomy ≈
   entropy, your verifier is not discriminative as built — fix it before scaling up.
3. **Then** run the full comparison, the Assumption-1 audit, and the compute-scaling
   study (E3–E5 in the runbook), with ≥3 seeds and paired significance tests.
4. Replace every `[RP: ...]` placeholder with measured values; reconcile the
   abstract, title, and contributions with what you actually found. If gains are
   small, reframe toward the no-degradation guarantee and plausibility rather than
   overclaiming Dice.

---

## 6. Integrity (non-negotiable)

- Labels are used **only** by the oracle control and for evaluation, never inside
  the method. Check your pipeline for label leakage before trusting any number.
- AI assisted the drafting of the method, proof, and text. **You** must
  independently verify Proposition 1, the empirical status of Assumption 1, and
  every claim. The human authors are the only authors and take full responsibility.
- Confirm the `VERIFY`-flagged citations against their sources; re-run the arXiv
  novelty check right before submission (this area moves monthly).
- Keep the submission anonymous (double-blind); comply with the venue's AI-use policy.
- Get **2–3 independent human mock reviews** and resolve every issue before
  submitting. Treat unresolved findings as blocking.

---

## 7. Venue and timeline

MICCAI 2026 is closed. Primary target: **MICCAI 2027** (LNCS, 8+2 pages,
double-blind; confirm dates when posted). Method-framed alternatives: **ICLR 2027**
or **CVPR 2027** (verify each deadline). The draft and code are identical across
these; only the template and page limit change.
