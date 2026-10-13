# REDFLAGS.md

Everything still requiring author attention, split into **blocking** (the paper
should not be submitted with these open) and **optional** (it would be better
with them closed).

The full audit history, including every defect found and how, is in
`REDFLAGS.txt`. This file is the actionable summary.

---

## BLOCKING — five open, and four share one root cause

### B7 — no per-instance records shipped *(root cause of B2, B3, B6)*

**Nothing in the bundle regenerates any number in the paper.** Not one table
cell, not the headline 0.25, not a single confidence interval.

This is the finding that has appeared in every audit of this project, and it is
the one that matters. A reviewer who asks "can I check this?" currently cannot,
and ARR reviewers increasingly do ask.

*Needs:* export to the schema in `code/soundver/records.py`, then one command.
*See:* EXPERIMENTS.md X1.

### B2 — Table 4 contradicts Table 2 on the paper's own headline claim

Table 4's δ column reads 0.005 / 0.002 / 0.017 / 0.022. Table 2 and Section 7
both state δ = 0 for the same four SQL models after the checker fixes. Both
cannot be true, and a reviewer opening Table 4 sees the soundness claim
contradicted on the same page.

The recomputed δ from records settles it. Whichever printed table disagrees is
the wrong one. *See:* EXPERIMENTS.md X2.

### B3 — Δ and Floor columns are not reproducible from the printed baselines

Six of twelve SQL rows have Δ ≠ (Acc − the greedy baseline named in that row's
own note), and no single baseline makes the column consistent. For the IE block,
all eleven rows are consistent with a 45.5% baseline and none with the 44.0%
that note (s) states. Three Floor entries also disagree with their own rule.

Recompute every Δ and Floor entry from records against **one stated baseline per
block**. *See:* EXPERIMENTS.md X2.

### B4 — no seed replication

Every cell is one draw at seed 0. The morphology greedy baseline already moved
43.0 / 44.0 / 45.5 across three nominal "seed 0" draws, because candidates are
freshly sampled rather than cached.

At minimum five seeds, with the across-seed SD reported next to every headline
number. **If the ceiling's SD exceeds the ceiling, it is not a result.**
*See:* EXPERIMENTS.md X4.

### B6 — seven gated rows are degenerate, not confirmatory

Seven gated rows carry a paired bootstrap CI of exactly [0, 0]. A zero-width
paired CI means the gated rule produced the same outcome as the reference on
every instance and every resample: **the gate never fired**. Those rows are not
evidence for Cor. 1.

Report the two cells where an ungated scorer degraded and gating recovered it —
the LLM judge on SQL (71.5→73.5) and the reward model on IE (43.0→45.5) — as
the mechanism evidence, and mark the rest as degenerate. `degenerate()` in
`soundver/rates.py` flags them. *See:* EXPERIMENTS.md X3.

---

## OPTIONAL — worth closing, not submission-blocking

### B12 — the closest related work is cited unverified, and it is load-bearing

`variationverif2026` (*Variation in Verification*, ICLR 2026, arXiv 2509.17995)
reports that a verifier's true-negative rate — exactly our 1−ε — **falls as
generator capability rises**, explained by strong generators producing
"well-structured but incorrect solutions." That is the closest published work to
this paper's central measurement, and the phrasing is close to our title.

It was located by search and **not read in full**; the author list in the `.bib`
is a placeholder. Read it, fix the entry, and confirm the positioning in Related
Work survives. If it does not, the framing changes before submission.

See `NOVELTY_AUDIT.md` for the full assessment, including the correction to the
recommendation in `RESEARCH_DIRECTION.md`.

### B8 — label validation and prompt sweep designed but not run

Both are specified in Appendix C with pre-registered readings, and the harness
is written. The label-audit bias runs **toward** our conclusion, so a reviewer
may reasonably ask. *See:* EXPERIMENTS.md X5, X6.

### B9 — no model snapshot strings

`openai/gpt-4o` is a moving endpoint. Record the snapshot OpenRouter actually
served and the access date for every run, plus `sqlglot`'s version — the two
reported checker defects are version-dependent. ARR's checklist asks for these.

### B10 — two datasets uncited

Spider is now cited (Yu et al., EMNLP 2018, verified against the ACL Anthology,
dblp, and two further sources). **CoNLL2003 and SIGMORPHON 2022 have no
bibliography entry**, which fails checklist item B1. I did not add them from
memory: ARR screens every reference and this project has a prior incident of
plausible-looking unverified author lists. Add both, verify each against the ACL
Anthology, and add their licences, which item B2 also wants.

### B11 — Cor. 3(a) tested on one chain, not the design space

The corollary quantifies over all 2ᵏ−1 sub-conjunctions; E4 walks one chain of
three. The exhaustive run costs **nothing** — it re-scores existing candidates.
It matters because E4 already found one ε-monotonicity violation on morphology.
*See:* EXPERIMENTS.md X7.

### R1–R8 — smaller items

- **R2** Leaderboard access date is 2026-08-06; re-check before 12 October.
- **R3** `dorner2025rocnreroll`: the given-name expansion "Florian E." →
  "Florian Eddie" is unverified, and `pages={150895--150936}` looks like a
  Scholar auto-export artifact.
- **R4** `gradesql2026`: two arXiv IDs exist (2606.30851, 2509.01308); confirm
  which version you cite.
- **R7** `cotterell2016canonical` author list and page range were read from
  third-party sources, not the paper's own title page. Three adjacent Cotterell
  segmentation papers are easy to confuse. Verify against the ACL Anthology.
- **R8** All three tasks are English. Stated as the first limitation with a
  typological prediction attached, which is the honest handling, but it remains
  the sharpest weakness for a COLING audience.

---

## Verification claims that must be true before you file

The Ethics section and checklist item E1 both state that **the human authors
independently re-derived every numbered result**. The handover notes still list
that re-derivation as outstanding.

Filing E1 with an untrue verification claim is precisely the "misleading filing"
that carries desk rejection under ARR, and it is worse than the gap it would
conceal. Either do the re-derivation or change the sentence.

`verify_theory.py` machine-checks all nine results and passes, but a machine
check is not a human re-derivation and does not satisfy what that sentence
claims.

---

## The pattern worth naming

Across the audits, **four defects were found in sentences whose job was to
defend the headline**:

| defect | kind |
|---|---|
| plug-in at pooled rates called an upper bound | sign error |
| contamination said to bias the ceiling the safe way | sign error |
| abstract asserting checks "never reject a correct output" | scope error |
| "current frontier models" from n = 2 | scope error |

All four are now fixed. Before submission, treat every remaining sentence of the
form "X cannot affect our conclusion" as unverified until checked the same way.
Those sentences get written when an author is reassuring themselves, which is
exactly when care lapses.

---

## Note on the theory (simplification pass, 2026-08-30)

The theory section was cut from 2.10 to 1.93 pages for a COLING audience.
Nothing load-bearing was removed, and all nine machine checks still pass.

**Moved to the appendix:** Theorem 1, the general accuracy formula for any δ.
It is the one result the paper never uses directly — it exists to parent Cor. 2
and Cor. 4, and its display carried the most notation in the paper (q, r, β,
(1−q)^N and two p₀δ terms). Corollary 2, the δ = 0 case, is what every finding
actually cites, and it now stands alone. Because each environment has its own
counter, **nothing renumbered** and every cross-reference stayed valid.

**Removed:** all four proof sketches. Each restated in prose what the appendix
proves properly, so a pointer does the same work in one line.

**Compressed:** the assumption block from a seven-line description list to three
sentences keeping the (A1)(A2)(A3) tags the rest of the paper cites; Definition 2
from argmax-over-a-set notation to plain English.

**Added:** a worked example of the ceiling arithmetic —
0.280 headroom × 0.012 caught × 0.730 replacement = 0.25 points — which shows at
a glance that the middle factor does all the work; and a one-sentence
plain-language statement of the ceiling before its formal claim.

**Fixed in passing:** `r = p/q` appeared in Related Work, roughly ten pages
before either symbol was defined. Now stated in words. Moving Theorem 1 also
left `r` undefined in Cor. 4, which is now defined inline.

Net effect: 10 numbered results in the body → 9, six displayed equations in the
theory → four, four proof sketches → zero, and **0.20 pages of headroom**, the
first slack this manuscript has had.

---

## Note on length (trim pass, 2026-08-30)

The body was already at 8 pages, which is the limit and the norm; a shorter body
signals a thin paper, not a disciplined one. The length problem was the
appendix: 13 pages for an 8-page body. It is now 8, and the appendix source went
from 72.6k to 45.3k characters.

**Cut whole (about 19k chars):**

- *The operating regime*, a full-page three-panel figure that was 24% of the
  appendix. Its own caption read "Every curve on this page is a formula
  evaluated exactly; none is measured." It illustrated Cor. 2 and Cor. 4, which
  the body states in two lines each, and the worked example added in the
  previous pass does the same job in one sentence.
- *Consequences of heterogeneity*, two sentences Limitations already made, one
  verbatim. The single useful line moved beside the result it follows from.
- *Reported verifier error rates* (Table 7), other authors' numbers whose own
  caption had to spend two sentences warning that its first row is a different
  conditional from ours. A table needing a disclaimer against being misread is
  not motivating anything; the one figure that does work (38.5%) is cited in
  the introduction.
- *The morphology rule-comparison block* (5.5k chars), a table the paper
  explicitly says tests nothing: "none of the floor outcomes in this block
  should be read as a test of Cor. 1." The morphology rates that DO carry a
  finding stay in Table 6.

**Compressed:** seven paragraph-length table notes. Two were blocking-finding
essays duplicating REDFLAGS at length; they are now one-line flags pointing here.

**Fixed:** a near-empty page (18 words) caused by float deferral. The IE
comparison table no longer needs full-column width now that the morphology block
is gone, and the appendix floats were relaxed from `[t]` to `[!htbp]`. Every
appendix page is now dense.

**Verified unchanged:** every headline number, all ten numbered results and
their proofs, all nine machine checks, zero broken references, zero orphaned
table or figure labels, body still 8 pages with 0.20 headroom.

---

## Note on the template (layout pass, 2026-08-30)

The reported line-numbering and text-overlap problems were **ours, not the
venue's**. `verify_layout.py` ships with the bundle and measures all three
failure modes from the rendered PDF; re-run it after any layout change.

### Line numbering: our own package was breaking the template

`acl.sty` loads `lineno` with the `switch` option and sets the numbers in 8pt
Helvetica. `soundver.sty` carried a generic "build standard" fix
(`\leftlinenumbers`, 6pt separation) that its own comment described as a remedy
for "many venue classes." It had been applied blindly to a class that already
handled the problem.

A minimal document against stock `acl.sty` produced **zero** misplaced numbers.
Ours produced **169 line numbers printed on top of body text**, on pages 3–8 of
the submitted eight as well as throughout the appendix, confirmed visually.

Measuring the real geometry rather than assuming it: the page is **A4**
(595×842pt), the columns run 71–289 and 306–524, so the gutter is **17pt**. At
8pt a four-digit number is 13.3pt wide and does not fit with any usable
separation. Options measured against the actual document:

| configuration | overlaps |
|---|---|
| stock `switch` | 169 |
| `\leftlinenumbers` at 8pt | 536 |
| `\rightlinenumbers`, tiny, 3pt | 470 |
| `\leftlinenumbers`, footnotesize, 1pt | 182 |
| **`\leftlinenumbers`, scriptsize, 1pt** | **0** |

Now **0**. At 7pt the numbers stay legible for reviewers citing lines. This sets
`lineno`'s parameters from our own package and does **not** modify `acl.sty`,
which ARR treats as grounds for rejection without review.

### Text overlap: `\resizebox` inside `threeparttable`

Two tables wrapped their tabular in `\resizebox`. `threeparttable` sizes its
notes to the **un-resized** width, so two tables' notes were typeset 61pt too
wide and bled into each other's column. Removing the `\resizebox` and shrinking
the font instead lets `threeparttable` measure a real tabular.

Three displayed equations were also running 55–61pt past the column, straight
into the margin where the numbers sit; they are now broken across lines.

Finally the comparison tables were genuinely too wide, so the row labels were
shortened editorially: the section headings already say "Ungated" and
"Reject-gated", so repeating "BoN," and "Sound stack +" on every row was what
pushed them over.

### Result

    line numbers over text     169  ->  0
    overfull boxes              12  ->  2   (5.4pt and 3.5pt, both cosmetic)
    worst overflow           61.4pt ->  0 on the submitted eight pages
    body pages 1-8                      clean

The 26 gutter and 108 margin items the checker still reports are all in the
appendix and are wide `table*` floats that PyMuPDF splits into several narrow
blocks, so the checker judges them per fragment rather than as one full-width
element. Verified by rendering the pages. No content changed: every headline
number, all cross-references and `acl.sty` itself are untouched.

---

## Note on the story (restructure, 2026-08-30)

`NOVELTY_AUDIT.md` found that the paper led with its two weakest items and
buried its three strongest. The story was inverted.

**Title.** *Well-Formed but Wrong: A Ceiling on What Any Structural Verifier Can
Buy* → **Sound by Definition, Unsound in Practice: Auditing the Free Verifiers
of Structured NLP Tasks**. The old title advertised the demoted contribution,
and "Well-Formed but Wrong" named the ε direction that *Variation in
Verification* got to first. The new title names the gap that unifies both
failure directions: a check that rejects correct outputs, and one that accepts
wrong ones, both follow from the structural property a task appears to guarantee
not being guaranteed.

**Progression, now explicit end to end.** Structured tasks hand you a free
verifier → its soundness is argued from the task definition, never measured,
and prior work sets false rejection aside → soundness is a claim about an
implementation and a dataset, and it cannot be tested with a label that
presupposes the check → so: audit it → δ > 0 on two of three tasks, 28% of
SIGMORPHON gold fails its own constraint, ε runs 0.61–0.99 where soundness
survives → audit before trusting, and state what a benchmark guarantees.

**Contributions reordered by what the audit found unclaimed:**

| | was | now |
|---|---|---|
| (i) | the ceiling | the circularity condition |
| (ii) | the ceiling, measured | the audit, run: δ > 0 on 2 of 3 |
| (iii) | two conditions + SIGMORPHON | a benchmark that fails its own constraint |
| (iv) | — | what soundness buys, crediting `variationverif2026` for the direction |

**Demoted, not deleted.** Cor. 3 is still proved, verified and used; it now
appears as the reason ε is the quantity to measure rather than as the thesis.
Prop. 1 and Cor. 1 keep their two clean supporting cells and are still labelled
in the text as not being findings.

**Every section now serves the same claim.** The Setup's nominal/realised
examples and the Experiments' statement of the circularity condition were
duplicating the Introduction and were cut; the Conclusion ends on the audit
rather than on the bound.

Verified after the restructure: all seven story stages present in the rendered
PDF, all four contributions render, every headline number preserved, 0 broken
references, 0 line-number collisions, body still 8 pages.

---

## Note on the method (audit, 2026-08-30)

The story restructure made an audit protocol the paper's lead contribution, and
then the paper did not contain one. Two defects, both fixed.

**1. There was no method.** Sections ran Setup → Theory → Experiments, with the
audit existing only as scattered prose plus "E1". A reader could not run it
without guessing how to choose a label, or what to do when δ > 0. §3 now states
it as three numbered steps: state the nominal argument and its scope; fix an
admissible label and estimate δ; exclude any cell with δ > 0 from every claim
requiring soundness, and report δ rather than repairing the check silently.

**2. The lead contribution was a slogan.** "A correctness label presupposing a
check cannot measure that check's error rate" never defined *presupposes*, was
not numbered, and could not be applied to a task a reader brings.

Definition 1 already contained the formula: realised soundness **is**
{C=1} ⊆ {V=1}. That is the property under test. If the *label* forces the same
inclusion, δ = 0 comes out whatever the check does — the property under test and
the artefact are the same formula, which is exactly why the trap is invisible.
Now stated as **Def. 2 (Admissible label)**: C is admissible for auditing V if
{C=1} ⊆ {V=1} is not entailed by the definition of C. One line, checkable,
portable.

**A third finding, which strengthens the claim.** The paper said execution match
forces δ = 0 for the *executability* check. It is broader: C = 1 requires the
query to run and match, running requires the schema to resolve, resolving
requires it to parse — so **execution match forces δ = 0 for the entire SQL
stack**. The soundness that benchmark appears to confirm is a tautology for all
three checks, not one. Stating the wider version costs nothing.

**Simplified to pay for it.** "Which checks qualify" asked which checks may
legitimately claim soundness, which is what the audit answers; it is merged in
rather than kept alongside. Cor. 4's statement moved to the appendix beside its
proof, since it supports E5, now a minor experiment; the qualitative prediction
stays in the body and E5 still tests it.

**Verified:** all ten numbered results still defined and proved, all four
contributions present, 0 broken references, 0 line-number collisions, all nine
theory checks pass, body still 8 pages.

---

## Note on the theory (minimisation, 2026-08-30)

Working backwards from the contributions rather than trimming what was there:

| contribution | theory it needs |
|---|---|
| (i) admissible label + audit | Def. 1, Def. 2. No propositions. |
| (ii) δ > 0 on 2 of 3 | none |
| (iii) SIGMORPHON | none |
| (iv) what soundness buys | the gain decomposition and the bound it implies |

Prop. 1 survives on a separate ground: it is *why soundness is worth having at
all*, which is the premise the paper rests on. Without it there is no reason
anyone would assume δ = 0 in the first place.

**Two numbered results were one-line consequences of their neighbours.**
Cor. 1 (Safe composition) read, in full, "under the hypotheses of Prop. 1, the
floor holds for any scoring function S" — a clause, not a result. Prop. 2
(Stacking) is Cor. 3's first proof step, and Cor. 3(a) already stated the same
set inclusion in its own words. Both are folded into the statements they belong
to, so the facts appear where they are used, and both proofs stay in the
appendix under labels that still resolve. All 14 references to `cor:compose`
were redirected to `prop:floor`, not deleted.

**Body theory across this session:** 13 → 9 → **7** environments; displayed
equations in the theory 6 → 4 → **3**; proof sketches 4 → **0**.

**What remains, each with a reason to be there:** Def. 1 (what the audit tests),
Def. 2 (contribution i), Def. 3 (the object the gain formula describes), Prop. 1
(why soundness matters), Cor. 2 (why ε is the quantity), Cor. 3
(contribution iv). Thm. 1, Cor. 4, Prop. 3, Cor. 5 and Lemma 1 are all still
proved, in the appendix.

**Redundancy the fold created, and removed:** "every scoring function S" was
being quantified twice in Prop. 1, the proofs pointer appeared in both the
section preamble and the following paragraph, and Prop. 2's discussion was left
orphaned. All three cleaned.

**Result:** the body now ends with 0.13 pages of headroom, and Conclusion *and*
Limitations both fit on page 8 rather than the body filling it. All nine theory
checks still pass; 0 broken references; 0 line-number collisions.

---

## Note on experimental design (audit, 2026-08-30)

Mapped every experiment to a current contribution. Two gaps and one orphan.

### The headline gap: contribution (i) had no experiment

The paper asserted that execution match is inadmissible for SQL and never showed
it. **E0** now tests it, and the records already exist.

Def. 2 predicts δ = 0 identically under an inadmissible label. Post-fix, both
labels give 0.000 for SQL and the comparison teaches nothing — so E0 uses the
paper's own history. Section 7 reports two parsing defects in the SQL
schema-validity checker, found and fixed across two passes. **Under execution
match those defects were invisible by construction; test-suite accuracy is what
exposed them.** The benchmark's own metric would have certified a checker the
authors had to fix twice.

That is their bug history used as evidence rather than an assertion about
admissibility, and it is falsifiable: any nonzero δ under execution match
refutes Def. 2. **No numbers were invented** — the design is specified and
flagged **B13**.

### The orphan: E3b

E3b compared the gated rule against homogeneous rejection sampling. Since the
story moved, it serves no contribution. It is **not** deleted, because it is a
legitimate power control: the theory predicts the two rules sit within 3.1
points against a 7.5-point MDE, so E3b checks that the design finds nothing
exactly where there is nothing to find. The text now says a separation here
would indicate a confound, not a result.

### The benchmark claim had no protocol

Contribution (iii) rested on "roughly 28% of a 200-word gold sample" with no
stated procedure and no interval. Findings now states that the check is applied
to the **gold segmentations themselves**, on the sample every morphology cell
uses, and **B14** requires the binomial interval and the sample provenance.

### New: B15, no failure cases

For a paper whose finding is that checks reject correct outputs, the paper never
shows one. Two or three rejected-correct examples per affected task, chosen by a
stated rule rather than hand-picked, would be directly on-claim and cheap.

### Verified present

Statistical uncertainty (paired bootstrap), significance test (paired
permutation), power stated before any null is reported (MDE 7.5–9.3), positive
control (oracle, 5.0–18.0 above base), negative control (vacuous check), an
ablation (checks added one at a time), robustness (prompt sweep, designed),
contamination, an efficiency column, and current-practice baselines.

---

## Note on the adversarial audit (2026-08-30)

Two attacks, both serious, both addressable, and both supplied by the paper's
own evidence.

### Attack 1: "your finding is that you write buggy checkers"

Section 7 reports two parsing defects in the SQL schema-validity checker, found
and fixed across two passes. So SQL's δ went from > 0 to 0 because the authors
debugged their own code. The reviewer writes: *"You found two bugs in your SQL
checker and fixed them. You presumably have bugs in your IE and morphology
checkers and did not find them. Your headline finding is indistinguishable from
'we wrote three checkers and debugged one of them.'"*

The paper was conflating two kinds of δ > 0, and only one supports it:

| kind | criterion | example | supports the claim? |
|---|---|---|---|
| **implementation** | some correct implementation would not make it | SQL pre-fix, a quoted literal read as a phantom column | **no** — evidence about the authors |
| **scope** | none avoids it, because the check's argument does not cover the data | SIGMORPHON's canonical annotations | **yes** |

Step (3) of the audit now requires the classification, with that criterion, and
says outright that only scope failures are findings about the check. Findings
classifies SQL as implementation and morphology as scope. **B16** requires IE's
leak to be classified too.

### Attack 2: "certified sound" is a zero count, not a measurement

Worse, and the paper's own numbers expose it. Step (3) certified a cell when
δ = 0 — but δ = 0 on a finite sample bounds δ from above and certifies nothing.
Rule of three, 0 events in n correct outputs:

| cell | n correct outputs | 95% upper bound on δ |
|---|---|---|
| SQL, base outputs only | 144 | **0.021** |
| SQL, base + 32 candidates | 4752 | 0.0006 |
| *IE leak the paper calls a **finding*** | — | *0.002* |

**A cell the paper certified as sound could carry a δ ten times larger than one
it reports as a failure**, and the paper never stated the denominator, so a
reviewer could not tell which regime a cell was in. Step (3) now reports n and
the bound, and says "certified" means δ below B. Costs nothing.

### Also flagged

**B17.** One implementation of each check stack, by one team, no second
independent implementation, no inter-implementer agreement — in a paper whose
finding is about implementations. Re-implementing one stack from the written
specification and reporting the δ difference is the cheapest robustness result
available.

### Checked and found sound

Reward models trained on disjoint splits (no leakage). Positive and negative
controls present. Power stated before any null is reported. Paired bootstrap and
permutation test throughout. Baseline comparison uses a shared candidate pool.

---

## Note on the full manuscript revision (2026-08-30)

Six story changes had landed since the last complete read. A section-by-section
pass found four places where the manuscript still described the paper it used to
be.

**§4 was titled "What the Sound Corner Buys".** Named when the ceiling was the
thesis. The section now exists to explain why ε is the quantity worth measuring,
so it is titled **"Why ε Is the Quantity"**.

**§3 was titled "Setup".** It now contains the paper's method — Def. 2 and the
three-step audit, which are contributions (i) and (ii). A reader scanning
headings could not find the method. Now **"Setup and the Audit"**.

**The red-flag block had eaten Limitations.** 4,160 characters of author
scaffolding against 7,784 of real content — 35% of the section — and it sat
*first*, so a reader met a wall of blocking findings before a single limitation.
The flags are now at the head of the appendix beside the removal banner: still
visible in the PDF, no longer in front of the paper's self-assessment.

**Limitations led with the wrong thing.** It opened on language coverage and
framed its technical content around the ceiling. After the adversarial audit the
sharpest limitation is different, and it now opens on it:

> *One team's judgement decides which failures count.* Step (3) separates
> implementation defects from scope failures, and only the second are findings
> about a check. We made that call on checkers we wrote ourselves, and we had
> already fixed two defects in one of them, so the classification is exactly
> where a reader should be most sceptical of us.

Language coverage and the bound's scope follow, the latter renamed from "what
the ceiling does and does not bound".

**Verified across the whole manuscript:** no stale story language anywhere
(no "Sound Corner", no ceiling-as-thesis, no old contribution ordering); every
section heading names what its section contains; abstract, introduction,
contributions and conclusion state the same problem and the same four
contributions; all scaffolding still visible; 0 broken references; 0
line-number collisions; body still 8 pages.

**Prose drift, also fixed.** Colon-then-reveal had crept from 20 back to 32
across the six story changes; nine were split, bringing it to 24 (3.8 per 1000
words). Mean sentence length 22.7 words, sd 11.9, ten sentences over 45.
Semicolons remain at 38, mostly inside theorem statements where they are
legitimate.

---

## Note on concision (2026-08-30)

Measured before cutting. The body runs **723 words per page** against a typical
ACL density of 800–900, so the problem was never word count. It was
**conceptual load**: a reader had to hold three separate binary distinctions
(nominal/realised, admissible/inadmissible, implementation/scope), **eight**
experiment labels, and ten symbols at once.

**Labels: 8 → 6.** E3b was a variant of E3, not a seventh experiment, and is now
described as one. E6 was two controls that already lived inside E5's paragraph,
so the label is gone and the controls are named rather than numbered. E0–E5
remain.

**Appendix E cut 5,826 → 964 characters.** "Full table notes" restated the
inline notes the tables already carry. What is genuinely not elsewhere — which
of four draws each row came from, and the constrained-decoding row's setup —
survives as "Row provenance". Nothing referenced was lost; 0 broken references
after the cut.

**Duplication removed from the body.** The Stroebl "unclear in practice" quote
appeared in full in both the Introduction and Related Work; the surface/canonical
contrast appeared at full length in both the Abstract and the Introduction. Each
now appears once and is pointed at from the other.

**Result: 14,340 → 13,583 words**, body still 8 pages, appendix lighter.
Everything load-bearing verified present afterwards: all four contributions,
Def. 2, the three-step audit, the rule-of-three bound, the
implementation/scope criterion, E0's falsifiable prediction, every headline
number, and all reproducibility material (protocol, proofs, numerical
verification, row provenance).

---

## Note on title, abstract and introduction (2026-08-30)

### The title could be undermined by the paper's own open item

*"Sound by Definition, Unsound in Practice"* asserts the checks **are** unsound.
The findings do not carry that flatly:

| task | what was found | supports the title? |
|---|---|---|
| SQL | implementation defects, fixed; now measures sound | **no** |
| IE | δ up to 0.025, **unclassified (B16)** | unknown |
| morphology | scope failure, 28% of gold fails | yes |

If B16 resolves IE as an implementation defect, the claim rests on **n = 1**. A
title that a reviewer can undermine using the paper's own flagged open item is
the wrong title.

**Now: "Soundness Is a Measurement, Not an Argument: Auditing Free Verifiers in
Structured NLP."** That is contributions (i) and (ii) together, it is true
whether one task fails or three, and it holds however B16 resolves. Searchable
on *soundness*, *verifiers*, *structured NLP*, *auditing*.

### Abstract: 253 → 219 words, rebuilt on the arc

Three defects fixed. The key insight sat in the **fifth** sentence. *"Answering
in the affirmative a question the closest prior work raises and leaves open"*
was a novelty claim with no content — it named neither the work nor the
question, and is cut. And it ended on *"we give the bound, and a protocol"*, a
deliverable rather than a significance statement; it now ends on **"anyone using
a structural check as a reward, filter or selector is relying on a property
nobody has measured."**

Still above the 150–200 norm, but the arc now runs problem → limitation →
insight → approach → evidence → significance in order.

### Introduction: two missing beats

**The approach was never a beat.** A reader could not see what the paper *does*
between noticing the gap and reporting numbers. Added as "So audit it", three
steps in three lines.

**There was no significance close.** The introduction ended on the contribution
list, leaving "why should I care" to the reader. It now closes on the point that
the same checks gate RLVR reward and filter synthetic training data, where a
check that quietly rejects correct outputs removes exactly the examples a model
has not yet learned to produce.

**Verified:** no hype vocabulary anywhere (*novel*, *state-of-the-art*, *first
to*, *we propose a*), prior work named rather than gestured at, 0 broken
references, body still 8 pages.

---

## Note on narrative flow (2026-08-30)

Twelve revision passes had left the manuscript reading as sections written
independently. Three defects, one of them created by the previous pass.

### The Introduction's arc was inverted

Paragraph order was: **solution first, problem fourth.**

| was | now |
|---|---|
| 1. So audit it *(the solution)* | 1. Soundness has to be measured *(the insight)* |
| 2. Why the two rates have to be separated | 2. So audit it *(the approach)* |
| 3. Where soundness holds, it buys little *(evidence)* | 3. Why the two rates have to be separated |
| 4. Soundness has to be measured *(the problem)* | 4. Where soundness holds, it buys little |
| 5. What is new | 5. What is new |
| 6. Contributions | 6. Contributions |

A reader met "measure δ against an admissible label" 2,800 characters before
learning what makes a label admissible. I introduced this last turn by inserting
the approach beat ahead of the paragraph that motivates it. Reordered at no page
cost.

### Terminology arrived before it existed

"Admissible label" was used 12,500 characters before Def. 2, and "implementation
defect" 13,800 characters before its definition — both in the approach beat. It
now uses plain words: *"a label that does not already assume the check"* and
*"either a bug in the implementation or a limit of the argument's reach"*. §3
supplies the terms when the reader needs them.

### Four sections opened with bookkeeping

Related Work opened on a citation, Setup on "Fix a task instance", the theory
section on "Two results, separated by what they assume", and Findings on which
tables carry the numbers. None connected to what came before. Each now carries
the thread:

- **Related Work** — "The false-acceptance side has been studied carefully and
  the false-rejection side has not, an asymmetry visible in the closest work."
- **Setup** — "This section makes that audit precise."
- **Theory** — "The audit decides which cells we may speak about; this section
  says what there is to say about them."
- **Findings** — "The audit voids more than it certifies."
- **Experiments** — "The design follows the audit" (was "follows the claim").

**Verified:** arc intact end to end, no term used before it exists, 0 broken
references, 0 line-number collisions, all theory checks passing, body still
8 pages.

---

## Note on figures (2026-08-30)

The paper has one figure. It argued against the paper.

### Figure 1 asserted what the paper refutes

The old figure placed "structural check as built" **on the sound edge**, and its
caption read *"a structural check is a point that is already at the top."* The
paper's own Table 3 and Table 5 report δ for twelve cells:

| task | δ | on the edge? |
|---|---|---|
| SQL | 0.000, 0.000, 0.000, 0.000 | yes |
| IE | 0.000, 0.002, 0.025, 0.005 | three are not |
| morphology | 0.120, 0.188, 0.181, 0.164 | none |

**Eight of twelve are off the edge.** A paper titled *Soundness Is a
Measurement, Not an Argument* had a single figure asserting the checks are
sound, and the caption's hedge — "for both OpenAI models on SQL and IE" — was
the four certified cells, selected. That is a misleading visualisation of the
paper's own data.

### Replaced with the twelve measured cells

The gap between the sound edge, where the task argument places every check, and
where each cell actually lands **is** the thesis, and it needs no schematic. The
new figure plots all twelve at their measured (ε, δ), shaped by task. SQL on the
edge, IE just below, morphology far below.

**Verified: 12 points plotted, 12 cells in the tables, ε values match exactly.**
The schematic oracle, reward-model and LM-judge markers were dropped because
they were never measured.

### Layout defects fixed along the way

The old figure occupied **122pt of a 218pt column**, wasting nearly half its
width. The first rebuild had the x-scale wrong — 0.47 units of ε across 0.94cm —
so the tick labels collided into "0.6.07.8.9.0" and the edge label ran off the
column. Corrected to 12.6cm per unit. Three label collisions then remained (edge
label on the line, SQL over the edge label, morphology annotation over the
margin); the explanatory text moved into the caption and only direct labels
remain, which is better practice anyway.

Final: no overlaps, direct labelling rather than a legend, axes labelled with
units, every coordinate traceable to a table, and the caption states the
takeaway rather than describing the axes.

---

## Note on tables (2026-08-30)

### The body's only table showed only the cells that passed

Table 1 listed **7 rows** — the certified cells — with columns
Task | Model | p₀ | ε | Ceiling. The audit measured **12** cells. The five that
failed appeared nowhere in the body.

Contributions (ii) and (iii) **are** those failures. The body table omitted every
one of them and showed only the successes, which is misleading emphasis on the
paper's own finding, and it left the reader unable to see the audit result
without turning to the appendix.

**Replaced with all twelve cells**, δ first, grouped by task, bound withheld
(`--`) wherever the cell was not certified. The reader now sees the audit and its
consequence in one place: five cells on δ = 0, three IE cells just off it, all
four morphology cells far off.

### Two smaller defects

**"Sound?" duplicated δ exactly** — it read *yes* iff δ = 0.000. Removed from
both rate tables.

**δ and ε carried no uncertainty while the secondary "observed" column got a 95%
CI.** The headline quantities were the bare ones. The caption now states that a
measured δ = 0 is a zero count rather than a zero rate and certifies only
δ ≤ 3/n, with **B16** requiring n per cell.

### Layout faults found and fixed along the way

The first rebuild used `\captionof` inside a `table` float, a mismatch that let
the table render **on top of the right column's text**. Then the two-line header
("(reject correct)", "(accept wrong)") made it wider than the column, so it bled
into the gutter; the header is now one row and the two rates are defined in the
caption instead.

**Verified:** all 25 body-table values traced to the manuscript, no vertical
rules in any tabular, booktabs throughout, siunitx decimal alignment, captions
stating takeaways rather than describing columns, one number bolded (the
headline 0.25), 0 broken references, body still 8 pages.

---

## Note on tables and the integrity audit (2026-08-30)

### The body's only table showed only the cells that passed

Table 1 listed **7 rows** — the certified cells — with columns Task, Model, p0,
epsilon, Ceiling. The audit measured **12** cells and five failed. Not one
failure appeared in the body.

Contributions (ii) and (iii) **are** the failures. The body table omitted every
one of them and showed only the successes, which is misleading emphasis on the
paper's own central finding.

Replaced with all twelve cells, delta first, grouped by task, bound shown only
where the cell is certified and (--) where it is not. The reader now sees the
audit result and what survives it in one place.

### Two smaller table defects

**"Sound?" duplicated delta exactly** — it read *yes* iff delta = 0.000. Removed.

**delta and epsilon carried no uncertainty** while the secondary "observed
accuracy" column got a 95% CI: the headline quantities were the bare ones. The
new body table states that a measured zero certifies only delta <= 3/n and
carries B16 for the denominators.

### Defects the integrity audit caught, one of them mine

- **Orphaned note (d)**, created by my own removal of the "Sound?" column in the
  same pass. It also carried the B2 flag, so removing the column would have
  detached the paper's live contradiction from the data it contradicts. **B2 is
  now attached to the delta column**, where the contradiction actually is.
- **Dangling marker (g)** on the IE block, referenced but never defined —
  pre-existing.
- **Orphaned asterisk note**, defined with a marker nothing pointed to — now
  unmarked.

### Checked clean

Every headline number cross-checked against its table (16 of 16 present). No
universal quantifier over models, no "proves" where the paper measures, no
non-statistical "significant". All three thin-evidence hedges present, though
phrased differently than an earlier pass had them: *"if that holds more
widely"*, *"the ordering needs no homogeneity assumption, while these figures
evaluate it under one"*. Every figure coordinate traces to a table, the two
values that did not being label anchors rather than data. Citation claims match
what was read: Stroebl et al.'s Appendix C does fix soundness and completeness
as constants (their Table 3, c = 1, s = 0.75). **No unrun experiment is
described in the past tense anywhere**, and all seven blocking flags remain
visible in the PDF.

---

## Note on writing quality (2026-08-30)

Measured before and after, since drift has been the recurring pattern.

| metric | before | after | note |
|---|---|---|---|
| semicolons | 43 (7.0/1k) | **36 (5.8/1k)** | no longer flagged high |
| "rather than" | 16 (2.6/1k) | **12 (1.9/1k)** | my own accumulated tic |
| "which is/suggests" | 14 (2.3/1k) | **12 (1.9/1k)** | two consecutive uses split |
| colon-then-reveal | 23 | 22 | steady |
| sentences over 45 words | 10 | 9 | worst was 61, now split |
| mean sentence length | 22.6 words | 21.9, sd 11.4 | human range is sd 9–14 |
| LLM vocabulary | none | **none** | |

**Semicolons carrying two full clauses were split into sentences.** Nine of
them, in Related Work, Setup, the Introduction and the audit protocol. The
remaining 36 are mostly inside theorem statements, where they separate
conditions and are correct.

**Two phrases were repeating.** "two of three tasks" appeared five times and
"text-to-SQL's standard [metric]" four; each is now stated once and referred to
after. Three instances of "canonical rather than surface" became "canonical, not
surface", which is both shorter and a sharper contrast.

**The 61-word sentence** in the Introduction's significance close was split into
three.

**Verified afterwards:** every headline number still present (12 of 12 checked),
no claim altered by the "X, not Y" rewrites, 0 broken references, 0 line-number
collisions, all theory checks passing, body still 8 pages.

One measurement note: several exact-string edits failed and needed re-doing by
regex, because LaTeX line-wrapping had broken the phrases across newlines. Any
future prose edit should match on whitespace-insensitive patterns rather than
literal strings.

---

## Note on the reviewer audit (2026-08-30)

Full report in `REVIEW.md`. One substantive fix, plus a scores table.

**The paper introduced a criterion and then did not apply it in its own
abstract.** §3 step (3) says only failures no implementation can avoid are
findings about a check. §6 applies it: SQL's failures were our bugs, morphology's
is a scope failure, IE is unclassified. **One confirmed finding, on one task.**

The abstract counted by δ > 0 — "two tasks have a check that rejects correct
outputs" — inviting a count of two. A reviewer reaching §6 would have found the
real count and read the abstract as overselling.

Abstract, contribution (ii) and the Conclusion now apply the criterion. The
abstract additionally states that applying it to our own text-to-SQL checkers
**reclassified two apparent findings as bugs of ours**. That is a stronger paper:
the criterion earning its keep against the authors' own work is the best
available evidence that it is worth having.

**Heuristic scores:** novelty 3.5/5, significance 3.5/5, technical quality 4/5,
clarity 4/5, empirical strength **2/5**, reproducibility **1.5/5**. Overall
borderline leaning reject as it stands — and the two weak axes are the two that
writing cannot fix.

---

## Note on the final consistency audit (2026-08-30)

Checked mechanically with `verify_consistency_final.py`, which ships with the
bundle. Eighteen passes had moved the title twice, inverted the story, renamed
sections, folded two theorems, replaced a figure and a table and renumbered the
experiments, so stale material was the expected failure mode.

**Five inconsistencies found, all fixed.**

1. **README.md still carried the title from two revisions ago** — *"Well-Formed
   but Wrong: A Ceiling on What Any Structural Verifier Can Buy in Test-Time
   Scaling"* — and described the ceiling-first story throughout. This is the one
   that would actually have shipped: the manuscript was current, the
   supplementary was not. Retitled and re-storied.
2. **`chow1970optimum` was in the .bib but no longer cited**, left behind when
   the cascade citation was tightened. ARR screens every reference; removed.
3. **`app:checks` and `app:lemma` were unreachable** — real appendix content
   with no pointer from anywhere. Both now referenced.
4. **E0 appeared once** and never in Findings, so a reader could not tell whether
   it had been run and produced nothing or had not been run. Now stated in E1's
   opening: contribution (i) is argued rather than demonstrated until E0 runs.
5. **Three dead subsection labels** (`sec:guarantee`, `sec:hetero`,
   `sec:quantity`), unreferenced since the theory fold. Removed.

**Verified clean afterwards:** every `\ref` resolves and no label is orphaned;
every `\cite` has an entry and every entry is cited; no stale title, section
name, folded theorem, removed experiment label, cut appendix section or deleted
table survives anywhere; experiment labels are exactly E0–E5; datasets and
models are named one way each; and all nineteen per-cell rates in the prose match
Table 1 exactly.
