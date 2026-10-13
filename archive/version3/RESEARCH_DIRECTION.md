# RESEARCH_DIRECTION.md

An assessment of the idea itself, not the manuscript. Written after eleven
passes over the paper, which is exactly when it is hardest to say this: **the
theorem cannot carry the paper, and the measurement can.**

---

## 1. Assessment of the current direction

### The theorem is the weak point

Corollary 3(a), the paper's headline object, says: conjoining every sound check
gives the lowest ε, and the gain falls as ε rises, so the full conjunction
dominates every subset. The complete proof is four steps: set inclusion,
monotonicity, one derivative, compose.

Read plainly, it says **"using all your checks beats using some of them."**

That is true, worth stating once, and not a result. The paper's own Limitations
already concedes "the theory is elementary." A reviewer who holds that a short
corollary cannot carry a main-conference paper will not be argued out of it, and
they will be right.

Corollary 3(b), which turns the ordering into a number, is the part that is not
trivial — and it assumes homogeneous rates, which the paper itself shows is
false and understates the truth by up to 1.7×. So the framework offers a bound
that is either assumption-free and obvious, or informative and known to be wrong
in the direction that matters.

### The measurement is the asset, and it is currently scaffolding

Buried under the theory is a striking empirical fact. On text-to-SQL, across
four models spanning 8.5 accuracy points:

| model | base acc | ε | verifier power (1−ε) |
|---|---|---|---|
| Llama-3.1-8B | 0.635 | 0.693 | 0.307 |
| Llama-3.1-70B | 0.680 | 0.776 | 0.224 |
| GPT-4o-mini | 0.705 | 0.928 | 0.072 |
| GPT-4o | 0.720 | 0.988 | **0.012** |

**Base accuracy rises 8.5 points; the verifier's power to catch a wrong answer
collapses 26-fold.** A log-linear fit gives R² = 0.74 and implies each accuracy
point costs about 29% of the remaining structural signal.

Nearly every wrong query GPT-4o writes still parses, type-checks and executes.
Its errors have left the form of the output entirely.

### The trap this creates, which the field is walking into

The two things a practitioner can measure move in **opposite directions**:

- **Precision** — how often an accepted output is correct — *rises* with model
  strength (0.680 → 0.730 on SQL).
- **Power** — how often the check catches a wrong output — *collapses*
  (0.307 → 0.012).

Someone monitoring a structural filter sees its precision improving and
concludes it is working better. Its discriminative value is going to zero at the
same time. **The field reports precision.** That is a real, consequential
measurement error, and this work is positioned to name it.

### Verdict

Novel: partly. Significant: yes, but not where the paper puts the emphasis.
Technically strong: the theory is weaker than the measurement, and the paper
leads with the theory. As framed, this is a borderline paper carrying a strong
result in its appendix.

---

## 2. The most important unresolved gap

Nobody has measured **how much of a structured task's well-formedness constraint
carries semantic information, or how that changes as models improve.**

The neighbours each stop short:

- **Stroebl et al.** show a verifier's false-acceptance rate bounds resampling,
  and note that accepted-candidate accuracy correlates with generator strength.
  They treat this as a caveat on scaling, not as an object to characterise, and
  they measure code unit tests — behavioural checks, not structural ones.
- **Dorner et al.** characterise selection accuracy for a *given* verifier's ROC
  geometry. Where that ROC point sits, and how it moves, is outside their scope.
- **Constrained decoding** work assumes well-formedness is worth enforcing and
  asks how to enforce it. Nobody asks what enforcing it is worth, or whether
  that worth is decaying.

The gap is a **measurement gap**, not a theory gap. That matters, because
computational linguistics rewards measurement contributions and this one is
CL-native: ε is a quantity about the relationship between the form of an output
space and the meanings it can express.

---

## 3. The redesign

### One research question

> **Does ε — the probability that a semantically wrong output is nonetheless
> well formed — increase systematically as models improve, and is the rate
> governed by the task's structure or by the model?**

### One central insight

**Well-formedness is a decaying proxy for correctness.** ε measures how tightly
a task's structure constrains its meaning, it is directly measurable without
labels beyond the task metric, and it rises as models improve because model
errors migrate out of the form and into the meaning. Everything that uses
structure as a stand-in for correctness — verifiers, constrained decoding,
reward shaping, synthetic-data filtering, agentic self-checks — inherits this
decay, and the standard metric (precision) hides it.

### One technical direction

Measure ε along a **capability ladder** crossed with **structurally diverse
tasks**, and test whether the decay rate is a property of the task or of the
model.

That is one experiment repeated, not a new method:

1. **Capability ladder.** Eight to twelve models spanning a wide accuracy range,
   including several within one family so capability varies with architecture
   held fixed. The current four models become the pilot.
2. **Structural diversity.** Tasks whose well-formedness conditions differ in
   how much they constrain meaning: a formal grammar plus schema (SQL), a record
   schema over natural-language spans (IE), a string-identity condition
   (segmentation), and ideally one where the constraint is *tight* — a
   well-formed output is nearly forced to be correct — as the contrast case.
3. **The prediction that makes it falsifiable.** If decay is task-governed,
   curves for the same task across model families should collapse onto one line
   when plotted against accuracy, and differ across tasks. If it is
   model-governed, they will separate by family. **These are distinguishable
   with the data the design already collects**, and the paper is interesting
   either way.
4. **The trap, demonstrated.** Report precision and power side by side across
   the ladder. One rises, one collapses. That figure is the paper.

The theory shrinks to a single line of motivation — gain ∝ (1−ε), so ε is the
quantity that matters — stated in the setup and never again. Corollaries 1 and 2
survive as the reason ε is the right thing to measure. **Corollary 3 goes.** Its
ordering claim is obvious once stated, and its number depends on an assumption
known to be false.

### What the title becomes

Roughly: *Well-Formed but Wrong: Structural Verification Decays as Language
Models Improve.* A claim about a trend, not a bound.

---

## 4. What this costs, stated plainly

**It is more expensive than finishing the current paper.** Eight to twelve
models instead of four, plus a fourth task. Against that: no new method, no new
theory to verify, and the harness in `code/` already computes ε per
(task, model) — the ladder is the same command over more cells.

**The five blocking findings do not go away.** B7 (no per-instance records) is
still the root cause of B2, B3 and B6, and the redesign needs those records
just as much. **X1 in `EXPERIMENTS.md` is the first step under either plan.**

**Honest risk.** Stroebl et al. observed a related correlation on code. If a
reviewer reads the decay as their result re-measured, the paper is in trouble.
The defences are real but must be argued explicitly: they measured behavioural
checks and we measure structural ones; they measured precision (which rises) and
we measure power (which collapses); they reported a correlation and we
characterise a rate and test what governs it. **Read their §4 and Appendix D in
full before committing** — that check has been open since the first pass and it
is now decision-relevant rather than merely prudent.

---

## 5. The decision

| | finish the current paper | redesign around the decay |
|---|---|---|
| effort | close 5 blockers | close 5 blockers + 8 models + 1 task |
| ceiling | borderline; theory too light | a measurement contribution with a figure that carries it |
| main risk | "the theorem is a lemma" | "Stroebl already showed this" |
| venue fit | COLING main, borderline | COLING main, strong; also ACL/TACL |

**My recommendation: redesign.** The current paper's best material is its
measurement, and the measurement is being asked to support a theorem that does
not need supporting. Turning ε from a means into the object gives a paper whose
central claim is something nobody has measured, whose evidence is a curve rather
than a bound, and whose practical warning — *you are watching the metric that
rises while the one that matters collapses* — is the kind of finding people
cite.

The cheapest way to test this before committing: **run the existing harness over
four or five more models on SQL alone.** If the decay curve holds and tightens,
the redesign is right. If ε scatters, it is not, and finishing the current paper
is the correct call. That is a day of API time and it decides the direction.
