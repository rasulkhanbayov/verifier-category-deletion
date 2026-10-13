# REDFLAGS.md

Final submission-readiness audit for *Soundness Is a Measurement, Not an
Argument: Auditing Free Verifiers in Structured NLP*, COLING 2027 Main
Conference via ARR (October 2026 cycle, deadline 12 October 2026).

> ## VERDICT: NOT SUBMISSION-READY
>
> **One integrity gate and six blocking scientific issues remain.** The
> manuscript is finished; the evidence is not. Every open item below needs data,
> a decision, or an action by the authors. None can be closed by further
> editing, and none has been closed by writing.

Counts: **1 gating**, **6 blocking**, **4 high**, **6 medium**, **6 submission
hygiene**. Full revision history is in `REDFLAGS_history.md`; this file is the
actionable list.

---

## GATING — resolve before filing, independent of the science

### E1. The paper makes a factual claim about the authors that may not be true

**Where.** Ethical considerations: *"AI tools assisted drafting and the
derivations; the human authors verified every proposition independently."* Now
flagged in red in the PDF.

**Why it gates.** This is a statement filed with ARR about what the authors did.
The project handover notes have listed that independent re-derivation as
**outstanding** throughout. Filing an untrue verification claim is the
misleading-filing case that carries desk rejection, and it is worse than the gap
it would conceal.

**Action.** Either complete an independent human re-derivation of all ten
numbered results, or change the sentence to say what was actually done.
`verify_theory.py` passing is **not** a human re-derivation and does not satisfy
this sentence.

---

## BLOCKING — the paper is not scientifically sound until these close

### B7. No per-instance records *(root cause of B2, B3, B6)*

Nothing in the archive regenerates any number in the paper. Not one table cell,
not the headline 0.25, not a single interval.

**Action.** Export to the schema in `code/soundver/records.py`, then
`./run_all.sh data/records.jsonl out/`. That single command closes B7, B2, B3,
B6 and B11. **Effort:** hours if the run logs exist, otherwise a re-run.
**Do this first — four of the six blocking items close behind it.**

### B2. Two tables contradict each other on the headline claim

Table 3 reports δ = 0.000 for all four SQL models; Table 7 reports 0.005–0.022
for the same cells. A reviewer opening Table 7 sees the soundness claim
contradicted on the page. Flagged at the δ column.

**Action.** Recompute δ from records. The `delta` column from `reconcile.py` is
the only measured one; whichever printed table disagrees is wrong.

### B3. Δ and Floor columns are not reproducible from the printed baselines

Six of twelve SQL rows have Δ ≠ (Acc − that row's own stated baseline), and no
single baseline makes the column consistent. Three Floor entries disagree with
their own rule.

**Action.** Recompute every Δ and Floor entry against **one stated baseline per
block**.

### B4. No seed replication

Every cell is one draw at seed 0. The morphology greedy baseline already moved
43.0 / 44.0 / 45.5 across three nominal "seed 0" draws.

**Action.** Five seeds minimum (`config.yaml`), reporting the across-seed SD
beside every headline number. **If the bound's SD exceeds the bound, it is not a
result** and the framing must change. **Effort:** ~2 GPU-days plus API spend.

### B6. Seven gated rows are degenerate, not confirmatory

Seven rows carry a paired bootstrap CI of exactly [0, 0]: the gate never changed
an outcome. They are not evidence for Prop. 1.

**Action.** `degenerate()` in `rates.py` flags them. Report the two cells where
an ungated scorer degraded and gating recovered it as the mechanism evidence,
and mark the rest.

### B16. The classification the finding depends on is incomplete

The paper's own criterion says only failures no implementation can avoid are
findings about a check. SQL's were bugs; morphology's is a scope failure; **IE
is unclassified.** The confirmed finding is therefore currently **n = 1**.

Separately, every cell certified at δ = 0 needs its denominator *n* and the
rule-of-three bound 3/n. On base outputs alone that bound is ≈ 0.021 for SQL,
**ten times the 0.002 IE leak the paper reports as a failure**, so without *n* a
reviewer cannot tell whether a certified cell is tighter than a reported one.

**Action.** Classify IE by the §3 criterion, and report *n* and 3/n per certified
cell. **This decides whether the finding is n = 1 or n = 2.**

### B13. E0 is specified but not run, so contribution (i) is argued not shown

E0 tests Def. 2 against the pre-fix SQL checker: execution match certifies that
checker, test-suite accuracy does not.

**Action.** Run it. The records exist because that checker was run. Any nonzero
δ under execution match refutes Def. 2, so the prediction is sharp enough to
fail. **Effort:** minutes once B7 is done.

---

## HIGH — a sharp reviewer will ask for these

| id | issue | action |
|---|---|---|
| **B12** | `variationverif2026` is the closest work to the paper's ε result and is cited from a search result; the author list is a placeholder | Read arXiv 2509.17995 in full, fix the entry, confirm §2's positioning survives. **Load-bearing for contribution (iv).** |
| **B8** | Label validation (V1) and prompt sweep (V2) designed, not run | `validity.py` implements both with pre-registered readings. The label bias runs *toward* our conclusion, so a reviewer may reasonably ask. ~2 days. |
| **B17** | One implementation of each stack, one team, no inter-implementer agreement — in a paper whose finding is about implementations | Run `checks.py` (independent reference implementation from the written spec) beside the originals and report the δ difference. **Cheapest robustness result available.** |
| **B15** | No failure cases anywhere | The paper finds that checks reject correct outputs and never shows one. Two or three rejected-correct examples per affected task, chosen by a stated rule, not hand-picked. |

---

## MEDIUM

| id | issue | action |
|---|---|---|
| **B11** | Cor. 3(a) quantifies over all 2ᵏ−1 sub-conjunctions; E4 walks one chain of three | `reconcile.py --exhaustive`. Costs nothing: re-scores existing candidates. Matters because E4 already found one ε-monotonicity violation on morphology. |
| **B9** | No model snapshot strings recorded | `openai/gpt-4o` is a moving endpoint. Record what OpenRouter actually served, plus access dates and `sqlglot`'s version. `generate.py` now refuses moving endpoints. |
| **B10** | CoNLL2003 and SIGMORPHON 2022 have no bibliography entry; licences unstated | Add both and verify each against the ACL Anthology (checklist B1/B2). ARR screens every reference. |
| **B14** | The 28% SIGMORPHON figure has no interval and unstated sample provenance | Report the binomial CI and say whether it is the E1 sample or an independent draw. |
| **B5** | DPC (ACL 2026), the strongest training-free SQL selection method found, was not run | Either run it or keep the current framing, which takes its reported ordering as the phenomenon to explain rather than a baseline to beat. Leaderboard access date 2026-08-06; re-check before the deadline. |
| **R7** | `cotterell2016canonical` read from third-party sources, not its title page; three adjacent Cotterell segmentation papers are easy to confuse | Verify against the ACL Anthology. |

Also: the hardware spec for the constrained-decoding row is marked
`[MISSING: ...]` in `MANIFEST.md` §4 and is needed for the reproducibility
checklist.

---

## SUBMISSION HYGIENE — mechanical, do all six

1. **Delete the 26 `\textcolor{red}` spans and the appendix flag block.** They
   sit in uncounted sections, so removal cannot push the body over.
2. **Re-run `measure_pages.py`.** Page 9 must begin with *Limitations*.
3. **Diff `acl.sty`** against the current `acl-org/acl-style-files` release.
   Ours carries the official header and `soundver.sty` touches no geometry, but
   the byte comparison was blocked by the sandbox.
4. **Two archives:** software as one `.tgz`/`.zip`, data separate, both
   anonymised. Anonymous GitHub is acceptable; Dropbox and Google Drive are not.
5. **Complete the Responsible NLP checklist** from
   `RESPONSIBLE_NLP_CHECKLIST.txt`. Several answers are *partially*, not *yes* —
   do not upgrade them.
6. **All authors register as reviewers within 48h** of the deadline.

---

## Verified — no further attention needed

Build: 0 errors, 0 undefined citations, 20 pages, body exactly 8. Theory: all
ten numbered results machine-checked; `verify_theory.py` and `verify_ceiling.py`
pass. Layout: 0 line-number collisions. Consistency:
`verify_consistency_final.py` reports CLEAN — every `\ref` resolves, every
`\cite` has an entry, every entry is cited, and no stale title, section,
theorem, experiment label or table survives. Figure 1 plots 12 measured cells
whose coordinates all trace to Tables 3 and 5. Prose: no LLM vocabulary, mean
sentence 21.9 words (sd 11.4). Code: `run_all.sh` runs end to end on synthetic
data; `checks.py` self-test 13/13.

---

## Shortest path to submittable

1. **Ship the records** (B7) → closes B2, B3, B6, B11; enables B13 and B16
2. **Classify IE** (B16) → decides whether the finding is n = 1 or n = 2
3. **Resolve the ethics sentence** (E1) → do the re-derivation, or change it
4. **Read *Variation in Verification*** (B12) → confirms the positioning holds
5. **Five seeds** (B4) → the last blocking item
6. **Strip the red flags** and re-check the page count

Steps 1–4 are days. Step 5 is the expensive one. **Nothing on this list is
writing.**
