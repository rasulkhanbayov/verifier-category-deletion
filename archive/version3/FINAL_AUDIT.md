# FINAL_AUDIT.md

A reviewer-style assessment of the complete package. Written to be useful rather
than reassuring.

---

## 1. Central claim

For a task whose outputs carry hard well-formedness constraints, the accuracy
gain achievable by **any** verifier assembled from those constraints is bounded,
and the bound is computable from a single measured rate before any verifier is
built or any selection run.

Conjoining every sound check a task supplies minimises the false-acceptance rate
ε among all conjunctions of them, and the gain is strictly decreasing in ε.
Measured across three tasks and four models, ε runs 0.61–0.99 and the bound is
0.25 accuracy points for GPT-4o on text-to-SQL.

## 2. Main novelty

**The quantifier.** Every prior bound in this literature evaluates a *given*
verifier. Cor. 3(a) maximises over the verifiers a task admits, which is a
different kind of object: a constraint on a design space rather than the score
of a design.

Two properties make it worth having. It is **assumption-free** — the dominance
holds instance by instance, whatever the rates do across instances, using only
δ = 0 and set containment. And it is **estimable in one shot**, from three rates,
with no verifier trained and no selection run.

Secondary and genuinely CL: ε has a linguistic reading as the rate at which a
semantically wrong output is still well formed, so measuring it measures how far
the structure of an output space constrains its meaning. The SIGMORPHON finding
is the concrete instance — 28% of English gold segmentations do not concatenate
to their own surface form, because the annotations are canonical rather than
surface, so the check that task appears to license is unsound on the very data
used to evaluate it.

## 3. Closest competing work, and the delta

**Dorner et al. (ICLR 2026).** Characterise the accuracy of best-of-N and
rejection sampling for a given verifier across the whole ROC curve. More general
than our result along their axis. Their characterisation is an *input* to ours,
not a competitor: we take a maximum over a design space.

**Stroebl, Kapoor & Narayanan (ICLR 2026).** Bound achievable accuracy by a given
verifier's false-acceptance rate, and set false rejection aside as a nuisance one
can sample around. We show false rejection carries the guarantee, measure that it
is violated on two of three tasks — answering a question they raise and leave
open — and turn the false-acceptance side into a design-space bound.

*A terminology collision worth restating:* they call 1−ε "soundness" and 1−δ
"completeness". Their soundness is our specificity. Without the footnote in
Section 3, a reviewer who knows that paper reads this one backwards.

**Constrained decoding and format restriction** (Geng et al., Park et al., Tam
et al.). Study how to *enforce* well-formedness and what enforcing it costs. We
measure what having it is worth.

We claim no new selection algorithm: the gated rule is rejection sampling with
the greedy output as first draw.

## 4. Strongest evidence

1. **Cor. 3 verified three ways** — symbolically, by exhaustive enumeration over
   4,000 random sound-check systems × every sub-conjunction × seven budgets, and
   by a control confirming the bound needs soundness. Zero violations.
2. **ε measured high across every cell**, 0.61–0.99, on three tasks whose
   well-formedness conditions differ in kind. At n = 200 a rate is resolved to
   well within an accuracy point, so this is the well-powered part of the design.
3. **Cor. 2's prediction inside the observed 95% interval in 24/24 SQL and 4/4
   IE cells**, and *outside* for three of four morphology models — in the
   direction the theory flags, since morphology's stack is measured unsound.
   A theory that also predicts its own failures is stronger than one that only
   confirms.
4. **The SIGMORPHON finding**, which is concrete, checkable, and about a
   benchmark rather than a model.

## 5. Remaining weaknesses, in the order a reviewer will hit them

**W1. Nothing is reproducible from the bundle.** No number in the paper can be
regenerated. Two tables contradict each other on the headline soundness claim.
This is the reason the paper is not ready, and it is entirely fixable with data
you already have or can re-run.

**W2. The theory is elementary.** Cor. 3 follows from Cor. 2 and Prop. 2 in a few
lines. The paper says so in Limitations and rests its case on the object being
new and measurable rather than on difficulty. A reviewer who holds that a short
corollary cannot carry a main-conference paper will not be moved, and then the
measurement and the SIGMORPHON finding must carry it.

**W3. One draw per cell.** No seed variation anywhere. The paper does not claim
otherwise, but a reviewer will notice.

**W4. All English.** Stated as the first limitation with a typological prediction
attached, which is the honest handling. It remains the sharpest weakness for a
COLING audience specifically.

**W5. The gate is not shown to beat its closest neighbour.** At the measured
rates the theory *predicts* no separation from homogeneous rejection sampling —
at most 3.1 points against a 7.5-point MDE — and predicts the gate trails
slightly in four of seven cells. The paper now says this plainly and rests the
gate's value on scorer-independence (Cor. 1) instead. Honest, and weaker than
what an earlier draft implied.

**W6. The ceiling's numbers are model-dependent.** Cor. 3(b) assumes homogeneous
rates; Cor. 5 shows the plug-in understates the heterogeneous case, by a factor
above 1.7 in our checker. The dominance in 3(a) is unaffected. Disclosed in four
places.

## 6. Honest acceptance assessment

**Readiness as a document: 8/10.** Claims reconciled to evidence, theory
machine-verified, novelty explicit and defensible, prose measured and repaired,
format compliant, checklist drafted.

**Readiness as a submission: 5/10.** Five blocking findings, all needing data.

**If B2, B3, B4, B6 and B7 close and the numbers hold**, this is a credible
COLING main-conference submission — a real open question, an assumption-free
result, a measurement across three tasks and four models, and a benchmark-level
CL finding. Competitive, not a lock: the theory is short, and reviewer variance
at these venues is large.

**If they do not close**, the most likely outcome is a reviewer asking for the
raw numbers, finding the Table 2 / Table 4 contradiction, and rejecting on
reproducibility regardless of the theory's quality. That failure mode is
entirely avoidable and is the reason this audit exists.

I will not put a probability on acceptance. The distribution is dominated by
reviewer draw and by results not yet reconciled, and a number here would imply
precision that does not exist.

## 7. Highest-priority actions

| # | action | closes | effort |
|---|---|---|---|
| 1 | **Ship the per-instance records** | B7 → B2, B3, B6 | hours if logs exist |
| 2 | `run_all.sh data/records.jsonl` and paste `out/tab_ceiling.tex` | B2, B3, B6, B11 | minutes |
| 3 | Re-run with 5 seeds; report across-seed SD | B4 | ~2 GPU-days |
| 4 | Human re-derivation of all nine results, or change the sentence claiming it | ethics/E1 | 1 day |
| 5 | Add and verify CoNLL2003 + SIGMORPHON citations and licences | B10 | 30 min |
| 6 | Record model snapshots and `sqlglot` version | B9 | your logs |
| 7 | Label audit and prompt sweep | B8 | ~2 days |
| 8 | 2–3 independent human mock reviews | — | 1 week |

**Item 1 is the whole game.** Four of five blocking findings close behind it, and
items 2 and the B11 run are then a single command.

## 8. What I could be wrong about

- **Novelty (medium-high confidence).** Searched for design-space bounds,
  saturation results and recent structured-output work. Nothing bounds what the
  best verifier constructible from a task's sound checks can buy. But Dorner et
  al. §4 and Appendix D remain unread in full, and the ceiling follows from their
  framework plus soundness plus closure. **Confirming they do not already state
  it is the highest-value check still open.**
- **Proof validity (high confidence).** All nine results machine-checked. But a
  machine check tests the algebra, not whether the modelling assumptions
  describe reality, and it is not the human re-derivation the Ethics section
  claims.
- **Baseline currency (medium).** DPC (ACL 2026) is the strongest training-free
  SQL selection method I found and was not run. Leaderboard access 2026-08-06;
  re-check before the deadline.
- **Numbers taken on trust (low confidence in them).** Every experimental figure
  in the paper came to me as text. I verified internal consistency and found
  contradictions; I could not verify correctness against data that was never
  provided. Treat every headline number as unverified until item 1 is done.
