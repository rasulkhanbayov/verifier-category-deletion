# MANIFEST.md — what is in this archive and what each part does

Submission package for *Soundness Is a Measurement, Not an Argument: Auditing
Free Verifiers in Structured NLP*, COLING 2027 Main Conference via ARR.

---

## 1. Manuscript

| file | purpose |
|---|---|
| `soundver_main.tex` | the paper |
| `soundver_main.pdf` | built, 20 pages: 8 body, Limitations/Ethics, references, appendix |
| `soundver_main.bbl` | precompiled bibliography, so one `pdflatex` pass resolves references |
| `soundver_refs.bib` | 24 entries, each verified against a source |
| `soundver.sty` | our macros. Touches no `acl.sty` geometry or font |
| `acl.sty`, `acl_natbib.bst` | official ACL template, unmodified |
| `fig/` | figure assets |

Build: `pdflatex → bibtex → pdflatex → pdflatex`. Needs TeX Live with `tikz`
(incl. `shapes.geometric`), `pgfplots`, `booktabs`, `threeparttable`, `siunitx`,
`multirow`, `xcolor`.

**Before uploading:** delete the red flag block at the head of the appendix and
all `\textcolor{red}` spans, then re-run `measure_pages.py`. They sit in
uncounted sections, so removing them cannot push the body over.

## 2. Documentation

| file | read it when |
|---|---|
| `README.md` | first: what the paper claims, how to build, how to reproduce |
| `REDFLAGS.md` | **before submitting.** Blocking vs optional, with what each needs |
| `EXPERIMENTS.md` | prioritised checklist of experiments still to run |
| `REVIEW.md` | simulated reviewer report with scores and rejection reasons |
| `NOVELTY_AUDIT.md` | closest prior work, read in full, and the exact delta |
| `RESEARCH_DIRECTION.md` | assessment of the idea itself, and one alternative |
| `FINAL_AUDIT.md` | central claim, evidence, weaknesses, priority actions |
| `RESPONSIBLE_NLP_CHECKLIST.txt` | honest draft answers for the ARR form |

## 3. Code

```
code/
  soundver/
    records.py    record schema, loader, synthetic generator
    checks.py     REFERENCE implementations of the three stacks   (see §5)
    generate.py   datasets + models -> records                    (needs a key)
    rates.py      rate estimation, rule simulation, bootstrap, permutation test
    reconcile.py  regenerate every table cell from records
    validity.py   label audit (V1) and prompt sweep (V2)
    ladder.py     the capability-ladder experiment (X0)
  run_all.sh      end-to-end; runs today on synthetic data
  config.yaml     models, seeds, prompts, audit parameters
  requirements.txt
```

Paper-side verification, at the top level:

| script | checks |
|---|---|
| `verify_theory.py` | 9 adversarial checks on every numbered result |
| `verify_ceiling.py` | Cor. 3 symbolically, exhaustively, and against a control |
| `verify_layout.py` | line-number collisions, column overflow, margins |
| `verify_consistency_final.py` | cross-references, citations, stale material |
| `measure_pages.py` | column-aware main-body page count |
| `prose_audit.py` | sentence length, tics, repeated phrasing |
| `claim_coverage.py` | maps each claim to the experiment testing it |

## 4. Dependencies, hardware, seeds

**Python** 3.10+. `numpy>=1.24` is the only requirement for the harness.
Optional: `pymupdf` (layout checks), `sympy` (symbolic theory check), `sqlglot`
(SQL parsing; `checks.py` falls back to a regex without it).

**Hardware.** None of this needs a GPU. All model access in the paper was
through hosted APIs; the constrained-decoding reference row is the one exception
and ran a 1.5B model locally.
`\textcolor{red}{[MISSING: the local machine's CPU/GPU and RAM, for the
reproducibility checklist]}`

**Seeds.** `config.yaml` sets `seeds: [0,1,2,3,4]`. The shipped numbers are
**seed 0 only** — this is B4, a blocking finding, not a configuration choice.

**Model snapshots.** `generate.py` refuses moving endpoints such as
`openai/gpt-4o`. The original runs did not record snapshots (B9), which is why
they are not reproducible.

## 5. What this archive does **not** contain

**The checkers that produced the paper's numbers.** `spider_task.py`,
`ie_task.py` and `morphology_task.py` are cited in the manuscript and are not
here. `code/soundver/checks.py` is an **independent reference implementation
from the paper's written specification (Table 8)**, not those files.

Two consequences, both stated plainly:

- It will not reproduce the paper's δ exactly, and any difference is a finding
  rather than a bug to tune away.
- It is precisely the second implementation **B17** asks for. Running it beside
  the originals and reporting the δ difference is the cheapest robustness result
  available to this paper.

**Per-instance records.** This is **B7**, the root cause of B2, B3 and B6. No
number in the paper can currently be regenerated from this archive.

## 6. Commands and expected outputs

```bash
cd code
./run_all.sh                       # synthetic smoke test, no data needed
```
Expected: rate table, rule comparison with `DEGENERATE` markers, exhaustive
subset scan, seed spread, and `out/tab_ceiling.tex`.

```bash
python3 -m soundver.checks --selftest
```
Expected: `13/13 passed`, including a regression case for each of the two SQL
parsing defects the paper reports, and a case confirming that canonical
segmentation fails `concatenates` — the paper's benchmark finding.

```bash
python3 -m soundver.generate --task sql --dry-run
```
Expected: the plan and an API-call count. With no key it exits 2 and generates
nothing.

```bash
./run_all.sh data/records.jsonl out/     # once B7 is closed
```
Expected: closes B7, B2, B3, B6 and B11 in one command, and writes
`out/tab_ceiling.tex` to paste into the paper. **Do not hand-edit table
numbers** — that is how the Table 3 / Table 7 contradiction arose.

```bash
python3 verify_theory.py && python3 verify_consistency_final.py
```
Expected: `VERDICT: all claims verified` and `CLEAN`.

## 7. Anonymity

Ship software as one archive and data as a separate one, both anonymised.
Anonymous GitHub is acceptable; Dropbox and Google Drive are not. All
`\textcolor{red}` spans and the appendix flag block must be removed first.
