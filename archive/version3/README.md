# Soundness Is a Measurement, Not an Argument — COLING 2027 submission package

**Title.** Soundness Is a Measurement, Not an Argument: Auditing Free Verifiers
in Structured NLP

**Venue.** COLING 2027 Main Conference, via ACL Rolling Review, October 2026
cycle. ARR deadline **12 October 2026**; commitment 23 December 2026.

**Status.** The manuscript is finished. The *submission* is not: five blocking
findings remain, all of which need your data rather than more editing. See
`REDFLAGS.md`, then `EXPERIMENTS.md`.

---

## What the paper claims

Structured NLP tasks hand you a verifier for free: a gold SQL query parses and
executes, a gold record validates against its schema. A check built from those
conditions cannot reject a correct output, which is why such checks are trusted
without examination as selectors in test-time scaling, as rewards in RLVR, and
as filters for synthetic data.

That argument is about a task. The check runs against an implementation and a
dataset. The paper measures the gap, and shows that measuring it needs care: a
correctness label that entails a check cannot estimate that check's error rate,
a circularity that holds silently for text-to-SQL under its standard metric.

Audited across three tasks and four models, two tasks have a check that rejects
correct outputs. Separating failures a better implementation would avoid from
those none can, one is confirmed of the second kind and belongs to the benchmark:
28% of SIGMORPHON 2022 English gold segmentations do not concatenate to their own
surface form. Where soundness survives, a wrong output is well formed 61-99% of
the time, which bounds what any such check can add.


---

## Where to start

`MANIFEST.md` lists every file and what it is for, with dependencies, hardware,
seeds, commands and expected outputs. `REDFLAGS.md` lists what must be resolved
before submitting. Read those two first.

## Project structure

```
soundver_main.tex             the paper
soundver_refs.bib             24 references, each verified against a source
soundver.sty                  our macros; touches no acl.sty geometry or font
acl.sty, acl_natbib.bst       official ACL template, unmodified
fig/                          figure assets

REDFLAGS.md                   blocking vs optional, with what each needs
EXPERIMENTS.md                prioritised checklist of what still has to run
RESPONSIBLE_NLP_CHECKLIST.txt draft answers for the ARR form (a desk-reject surface)

code/                         harness for the missing experiments
  soundver/records.py         record schema, loader, synthetic generator
  soundver/checks.py          reference check stacks (NOT the originals; see MANIFEST S5)
  soundver/generate.py        datasets + models -> records (needs an API key)
  soundver/rates.py           rate estimation, rule simulation, bootstrap, tests
  soundver/reconcile.py       regenerate every table cell from records
  soundver/validity.py        label audit and prompt sweep
  run_all.sh                  end-to-end; runs today on synthetic data
  config.yaml                 models, seeds, prompts, audit parameters
  requirements.txt

verify_theory.py              9 adversarial checks on every numbered result
verify_ceiling.py             Cor. 3 three ways: symbolic, exhaustive, control
verify_consistency.py         internal number consistency across the manuscript
claim_coverage.py             maps each claim to the experiment testing it
prose_audit.py                sentence-length, tic, and repetition diagnostics
measure_pages.py              column-aware main-body page measurement
```

---

## Building the paper

```bash
pdflatex soundver_main
bibtex   soundver_main
pdflatex soundver_main
pdflatex soundver_main
```

Requires TeX Live with `tikz`, `pgfplots`, `booktabs`, `threeparttable`,
`siunitx`, `multirow`, `xcolor`.

**Always verify the page limit after any edit.** ARR desk-rejects overlength
submissions, and reflow means a one-word change can push the body over.

```bash
python3 measure_pages.py     # main body must be <= 8.00
```

Page 9 must begin with `Limitations`. That is the check; the reported
"OVER by 0.04" is measurement granularity, not an overflow.

### Before you upload

1. Delete the red banner at the top of the appendix and all red-flag spans.
   They live in Limitations and the appendix, both excluded from the page
   count, so removing them cannot push the paper over.
2. Re-run `measure_pages.py`.
3. Software as **one** `.tgz`/`.zip`, data as a **separate** archive, both
   fully anonymised. Anonymous GitHub is acceptable; Dropbox and Google Drive
   are not.
4. Diff `acl.sty` against the current `acl-org/acl-style-files` release. Ours
   carries the official header and our `.sty` touches no geometry, but the
   byte comparison was blocked by the sandbox network.
5. All authors register as reviewers within 48h of the deadline.

---

## Reproducing the experiments

### Environment

```bash
cd code
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Only `numpy` is needed for the harness. The paper-build checks additionally use
`pymupdf` and `sympy`.

### Smoke test — runs today, no data required

```bash
cd code
./run_all.sh
```

This synthesises records with **known** rates, so every estimator is checked
against ground truth. Nothing it produces may appear in the paper; it exists to
prove the harness executes before the real records do.

### The real run

Export your per-instance records to the schema in `soundver/records.py`: one
JSON object per `(task, model, instance, candidate)`, base output at
`cand_idx = -1`. The loader validates the schema and fails loudly on a missing
check rather than silently treating it as passing.

```bash
./run_all.sh data/records.jsonl out/
```

That single command closes **B7, B2, B3, B6** and **B11**, and emits
`out/tab_ceiling.tex`. Paste that file into the paper; do not hand-edit table
numbers, which is how the Table 2 / Table 4 contradiction arose.

### Per experiment

| Experiment | Command | Closes |
|---|---|---|
| Rates, ceiling, rule comparison | `python3 -m soundver.reconcile --records R --out out/` | B2, B3, B6, B7 |
| All 2ᵏ−1 sub-conjunctions | `... --exhaustive` | B11 |
| Seed replication | `... --seeds` | B4 |
| Label-audit sampling | `python3 -m soundver.validity sample --records R --out out/` | B8-V1 |
| Label-audit scoring | `python3 -m soundver.validity score --annotations A --records R` | B8-V1 |
| Prompt sweep | `python3 -m soundver.validity prompts --records R` | B8-V2 |

`sample` writes two blind, independently shuffled annotation sheets plus a key
that annotators must not see. The automatic label is deliberately absent from
the sheets: an annotator who can see it is not blind, and catching cases where
the automatic label is *wrong* is the entire point.

### Theory checks — no data needed

```bash
python3 verify_theory.py      # 9 checks; all must pass
python3 verify_ceiling.py     # symbolic + exhaustive + a control
```

`verify_theory.py` contains the check that found the heterogeneity defect:
4000/4000 heterogeneous populations exceed the plug-in at pooled rates, which
is why Cor. 3 is split into assumption-free dominance (a) and model-dependent
evaluation (b).

---

## Two things worth knowing before you edit

**A terminology collision.** Stroebl et al., our closest antecedent, call
1−ε *soundness* and 1−δ *completeness*. Their "soundness" is our specificity,
and our "sound" (δ = 0) is their "complete". A footnote in Section 3 states
this. Do not remove it; a reviewer who knows that paper would otherwise read
this one exactly backwards.

**Four defects have been found in sentences defending the headline** — the
heterogeneity plug-in, the contamination direction, the abstract's soundness
assertion, and a "frontier models" generalisation from n = 2. Two were sign
errors, two were scope errors. Treat any sentence of the form "X cannot affect
our conclusion" as unverified until checked. Those get written when an author
is reassuring themselves, which is when care lapses.
