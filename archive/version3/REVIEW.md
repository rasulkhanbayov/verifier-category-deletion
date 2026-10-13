# REVIEW.md — simulated reviewer report

Written as a demanding ARR reviewer reading the paper cold. Scores are heuristic
and the reviewer draw at this venue is noisy; treat them as a prioritisation
tool, not a prediction.

---

## Summary

The paper argues that the soundness of a structural verifier is an argument
about a task, while the check runs against an implementation and a dataset, and
that the gap is measurable. It gives a condition a correctness label must meet
to audit a check at all, a three-step audit, and results on three tasks and four
models.

## Scores (heuristic)

| axis | score | reason |
|---|---|---|
| Novelty | 3.5/5 | The admissibility condition and the benchmark finding are unclaimed. Contribution (iv)'s direction is anticipated by Variation in Verification, which the paper credits. |
| Significance | 3.5/5 | The same checks gate RLVR reward and filter synthetic data, so the audit generalises past test-time scaling. |
| Technical quality | 4/5 | Theory is elementary but correct and machine-verified. The measurement design is careful: controls, power stated before nulls, non-circular labels. |
| Empirical strength | **2/5** | See R1 and R2. This is where the paper is weakest. |
| Clarity | 4/5 | One argument end to end; the figure now shows the finding. |
| Reproducibility | **1.5/5** | No per-instance records, no seed variation, one table contradicts another. |
| **Overall** | **borderline, leaning reject as it stands** | Fixable, but not by writing. |

---

## R1. The confirmed finding is n = 1 *(addressed in this pass)*

The paper's own criterion says only failures no implementation can avoid are
findings about a check. Applying it: SQL's failures were our bugs, morphology's
is a scope failure, IE is unclassified (B16). **One confirmed finding, on one
task.**

The abstract previously counted by δ > 0 and said "two tasks have a check that
rejects correct outputs", inviting a count of two. A reviewer reaching §6 would
have found the count is one confirmed plus one pending and read the abstract as
overselling.

**Fixed.** Abstract, contribution (ii) and the Conclusion now apply the paper's
own criterion, and the abstract states that applying it to our own SQL checkers
reclassified two apparent findings as bugs. That is a stronger paper, not a
weaker one: the criterion earning its keep on the authors' own work is the best
evidence that it is worth having.

**Still open:** classify IE. If IE is scope, the finding is n = 2 and the paper
is materially stronger. If IE is a bug, n = 1 and the framing should say so.

## R2. Reproducibility *(not addressable by writing)*

No per-instance records; no number in the paper can be regenerated. Table 3 and
Table 7 report different δ for the same SQL cells (B2, flagged in the paper).
One draw per cell, no seed variation. A cell "certified" at δ = 0 is a zero
count whose rule-of-three bound is not reported (B16).

This is the strongest reason to reject and it needs data, not editing.

## R3. Contribution (iv) is anticipated

Variation in Verification (ICLR 2026) reports a verifier's true-negative rate
falling as generator capability rises. The paper cites it and positions the
deterministic-structural case as the extension, which is honest. A reviewer may
still read (iv) as replication in a different setting. **The citation is
unverified (B12) and load-bearing; read it before submitting.**

## R4. Scope

Three tasks, one language, four models. Stated as the first technical
limitation with a typological prediction attached, which is the right handling.

## R5. "Is a definition and a checklist a paper?"

Contribution (i) is one line. The paper's defence is that the line is checkable,
portable, and catches a real trap in a standard benchmark metric — and E0 is
designed to demonstrate rather than assert it. That defence rests on E0 being
run (B13).

---

## What would move this from borderline to accept

1. **Ship the records** (X1). Closes R2, the strongest objection.
2. **Classify IE** (B16). Decides whether R1 is n = 1 or n = 2.
3. **Run E0** (B13). Turns contribution (i) from asserted into demonstrated.
4. **Read Variation in Verification** (B12). Confirms R3's positioning holds.

None of these is writing. The manuscript is in good shape; the evidence is not
yet.
