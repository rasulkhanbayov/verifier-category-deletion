# NOVELTY_AUDIT.md

A deep novelty audit against the current literature. It changes the
recommendation I made in `RESEARCH_DIRECTION.md` one step ago, and it should:
that is what an audit is for.

**Headline: the decay framing I proposed is substantially anticipated by a paper
I had not found. The ceiling framing was already weak. What survives is
narrower than either, and it is the part of this work that is genuinely
unclaimed.**

---

## 1. What I read, in full

### Stroebl, Kapoor & Narayanan, *The Limits of Inference Scaling Through Resampling*, ICLR 2026 (arXiv 2411.17501v3)

Read end to end, including Appendix C. This closes a check that had been open
since the first pass of this project.

**They measure a different conditional from ours.** Their Section 3 inequality is

> P_strong(Correct) > P_weak(Correct | Pass Verifier)

and their Figure 3 y-axis is "achievable accuracy given an infinite compute
budget" — that is **P[correct | passes verifier]**, our *r*. Their finding is
that *r* **rises** with model strength. Ours is that ε rises too. These are
different quantities and both can rise; there is no conflict.

**Decisively, their model treats verifier soundness as a constant.** Appendix C
defines Completeness *c* = P[accept | correct] and Soundness *s* = P[reject |
incorrect] — so their *s* is our 1−ε — and Table 3 fits **c = 1, s = 0.75**
once, for Llama-3.1-8B on HumanEval+, and holds it fixed. They never ask whether
*s* varies with the generator. That was the gap.

**They explicitly set aside the false-negative corner:** "False negatives of the
verifier ... are less of a problem ... It is possible that every correct solution
is a false negative of the verifier, but it is unclear if this is a problem that
arises in practice." Our E1 answers it: δ > 0 on two of three tasks.

**Their Limitations name three of our contributions as open:** coding-only
domain, prompt sensitivity, and contamination.

Verdict on this neighbour: **not a scoop.** The delta is precise and defensible.

### Variation in Verification: Understanding Verification Dynamics in Large Language Models, ICLR 2026 (arXiv 2509.17995)

**This one substantially anticipates the redesign.** From the paper:

> "the verifier's **TNR decreases as the generator capability increases**"

TNR is the true negative rate, P[reject | incorrect] — **exactly our 1−ε**. And
their mechanism is ours:

> "Strong generators produce internally consistent reasoning chains where early
> mistakes propagate coherently, yielding **well-structured but incorrect
> solutions** that cause the verifier false positives. Weak generators produce
> surface-level errors such as self-contradictions, facilitating verifier
> rejection."

That is the claim I proposed building a paper on, published, at ICLR 2026, with
a phrase almost identical to our title. They also test robustness to the
verification prompt and scale to Qwen3-235B.

**I was wrong one step ago.** `RESEARCH_DIRECTION.md` recommends redesigning
around this decay and names Stroebl as the risk. The real risk was a paper I had
not surfaced, and it is closer.

### Others located, none of which close our corner

- *Examining False Positives under Inference Scaling for Mathematical Reasoning*
  (arXiv 2502.06217): manual verification of false positives, math, Pass@N vs
  Best-of-N.
- *When to Trust the Cheap Check: Weak and Strong Verification for Reasoning*
  (arXiv 2602.17633): Pareto tradeoffs for routing between weak and strong
  verifiers. A policy question, not a measurement one.
- *Before the Model Learns the Bug: Fuzzing RLVR Verifiers* (arXiv 2606.01066):
  finds structured false-positive regions in math, JSON tool-call and code
  verifiers, and recommends fuzzing verifiers before training. **Closest in
  spirit to our benchmark-integrity finding**, but it targets *verifier
  implementations*, not *gold standards*.
- *RL with Verifiable yet Noisy Rewards under Imperfect Verifiers*
  (arXiv 2510.00915): reports that over 38% of responses a rule-based math
  verifier flagged incorrect were in fact correct — a δ > 0 result of the same
  kind as our E1, in a different domain.

> **All arXiv identifiers and claims above are as returned by search and by
> reading the Stroebl HTML. Only Stroebl et al. was read in full. Verify each of
> the others against its own title page before citing; do not take these
> summaries as sufficient.**

---

## 2. Where this leaves each framing

| framing | status |
|---|---|
| **The ceiling (current paper)** | Weak. Cor. 3(a) is a monotonicity observation; 3(b) assumes homogeneity the paper shows is false. |
| **The decay (my last recommendation)** | **Substantially anticipated** by Variation in Verification for learned verifiers on reasoning. |
| **Structural-verifier decay** | Narrower but open. See below. |
| **Benchmark integrity** | **Genuinely unclaimed.** See §3. |

### What survives of the decay framing

Variation in Verification studies **LLM-as-judge verifiers** on **reasoning**.
Ours are **deterministic structural checks** on **structured output spaces**,
and the difference is not cosmetic: a structural check has **δ = 0 by
construction**, because a correct output satisfies the task's own
well-formedness conditions. An LLM judge has two free error rates; a sound
structural check has one. That makes ε the *only* free parameter and the decay a
cleaner object.

That is a real distinction, and it is a "does the known phenomenon extend to a
qualitatively different verifier class" paper. Publishable; not headline.

---

## 3. The one thing here that nobody has claimed

**A benchmark's gold standard need not satisfy the structural property its own
task definition appears to license, and nobody checks.**

Our instance: concatenation is sound for *surface* morphological segmentation,
SIGMORPHON 2022 English is *canonical* segmentation, and **28% of its gold does
not concatenate to its own surface form**. A check the task appears to license
is unsound on the very data used to evaluate it.

Why this is the strongest remaining position:

1. **Not anticipated.** Stroebl and Variation in Verification both study
   verifier behaviour against a trusted gold standard. Fuzzing RLVR Verifiers
   audits verifier *implementations*. Nobody audits whether the *gold standard*
   satisfies the constraint the task implies.
2. **CL-native.** It rests on the canonical/surface distinction
   (Cotterell et al.), which is a linguistic fact, not an ML one. This is a
   COLING contribution in a way the ceiling never was.
3. **It generalises into a real study.** Take *n* structured CL benchmarks;
   for each, state the well-formedness property its task definition implies;
   measure how often the gold standard violates it. That is a measurement paper
   with a clean protocol and a finding per benchmark.
4. **It is cheap.** No model calls at all. You check gold standards.
5. **It comes with a reusable methodological result** already in the paper: the
   circularity condition — *a correctness label that presupposes a check cannot
   be used to measure that check's error rate*. That condition is what makes the
   audit well posed, and it is not in the literature I found.

**Candidate question:** *Do structured NLP benchmarks satisfy the
well-formedness constraints their task definitions imply, and what breaks when
they do not?*

---

## 4. Revised recommendation

I gave you a redesign one step ago on incomplete evidence. Corrected:

1. **Do not build on the decay as the headline.** It is anticipated. Cite
   Variation in Verification prominently and position the structural case as an
   extension, not a discovery.
2. **Do not keep the ceiling as the headline.** It was already the weak point.
3. **Consider moving the centre of gravity to benchmark integrity.** It is the
   only part of this work I could not find in the literature, it is the most
   CL-native, and it is the cheapest to scale.
4. **Either way, ship the records (X1).** Every version needs them.

**Immediate action, cheaper than the ladder:** read Variation in Verification in
full and decide whether the structural case is a distinct enough contribution.
That is a reading task, not an experiment, and it gates the direction.

---

## 5. Positioning changes made to the paper

Related Work now states the delta against Stroebl et al. precisely, sourced from
their own definitions rather than from their abstract, and flags Variation in
Verification as the closest work on the decay so a reviewer does not find it
first. Both entries carry `% VERIFY` where I have not read the title page.

---

## 6. What I could still be wrong about

- **Confidence that Stroebl et al. do not state the ceiling: high.** Read in
  full, including Appendix C.
- **Confidence in the Variation in Verification summary: medium.** From search
  results, not a full read. Read it before acting on §4.
- **Confidence that the benchmark-integrity angle is unclaimed: medium.** I
  searched for verifier reliability and structured-output work, not for
  annotation-quality or benchmark-audit literature, which is a large field with
  its own vocabulary. Search "annotation guideline violation", "gold standard
  consistency", "benchmark error rate" before committing.
- **What I did not search:** OpenReview submissions under review for 2027, which
  is where the closest concurrent work would sit.
