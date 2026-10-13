# EXPERIMENTS.md

Everything still to run, in priority order. Priority is by **how much
acceptance probability it buys per hour of work**, not by how interesting it is.

Every entry names the claim it tests, so nothing here is an experiment for the
sake of a table.

---

## P0 — blocking. The paper cannot be submitted without these.

### X1. Ship the per-instance records (closes **B7**, and with it B2, B3, B6)

| | |
|---|---|
| **Claim tested** | all of them, indirectly: no number is currently reproducible |
| **Input** | your existing run logs |
| **Output** | `data/records.jsonl` in the schema of `code/soundver/records.py` |
| **Command** | export, then `python3 -m soundver.reconcile --records data/records.jsonl --out out/ --all` |
| **Effort** | hours, if the logs exist. If they do not, this is a re-run. |

This is the root cause of four of the five blocking findings. The schema is one
JSON object per `(task, model, instance, candidate)` with `correct`, the
per-check verdicts, and the scorer value. The `correct` field must satisfy the
circularity condition: test-suite accuracy for SQL, never execution match; gold
segmentation match for morphology, never a conjunction with `concatenates`.

**Do this first.** X2, X3 and X4 are then a single command.

### X2. Reconcile every table cell (closes **B2** and **B3**)

| | |
|---|---|
| **Claim tested** | δ = 0 for all four SQL models; every Δ and Floor entry |
| **Command** | `python3 -m soundver.reconcile --records data/records.jsonl --out out/` |
| **Output** | `out/rates.json`, `out/rules.json`, `out/tab_ceiling.tex` |
| **Effort** | minutes once X1 is done |

Table 4's δ column reads 0.005 / 0.002 / 0.017 / 0.022 while Table 2 and
Section 7 both say δ = 0 for the same four models. Both cannot be true, and a
reviewer opening Table 4 sees the paper's headline soundness claim contradicted
on the same page. The recomputed `delta` column settles it; whichever printed
table disagrees is the wrong one. Paste `out/tab_ceiling.tex` into the paper
rather than hand-editing numbers.

### X3. Mark the degenerate rows (closes **B6**)

| | |
|---|---|
| **Claim tested** | Cor. 1, safe composition |
| **Command** | same as X2; the driver prints `DEGENERATE` per rule |
| **Effort** | minutes |

Seven gated rows carry a paired bootstrap CI of exactly [0, 0], which means the
gate never changed an outcome on those instances. Those rows are not evidence
for Cor. 1. `simulate_rules` returns `gate_fired` per instance so you can say
what fraction of the time the mechanism engaged, and `degenerate()` flags rows
where it never did. Report the two cells where an ungated scorer degraded and
gating recovered it as the mechanism evidence, and mark the rest.

### X4. Seed replication (closes **B4**)

| | |
|---|---|
| **Claim tested** | every reported rate and every CI |
| **Datasets** | all three, unchanged |
| **Config** | `seeds: [0,1,2,3,4]` in `config.yaml` |
| **Command** | re-generate, then `--seeds` |
| **Output** | `out/seeds.json`: per-seed ε and ceiling, with across-seed SD |
| **Effort** | ~2 GPU-days plus API spend |

Every cell is currently one draw at seed 0. The morphology greedy baseline
already moved 43.0 / 44.0 / 45.5 across three nominal "seed 0" draws, because
candidates are freshly sampled rather than cached. Report the across-seed SD
next to every headline number. **If the ceiling's SD exceeds the ceiling, it is
not a result** and the framing has to change.

---

## P1 — strongly recommended. These are what a sharp reviewer will ask for.

### X5. Label validation on ε events (closes **B8-V1**)

| | |
|---|---|
| **Claim tested** | ε is high; therefore the ceiling is small |
| **Design** | 150 ε events per task, stratified by model; 2 blind annotators; 3rd adjudicates |
| **Commands** | `python3 -m soundver.validity sample --records ... --out out/` → annotate → `python3 -m soundver.validity score --annotations out/annotations.jsonl --records ...` |
| **Output** | Krippendorff's α, label-error rate λ̂, corrected ε and ceiling |
| **Effort** | ~1 day of annotation |

The bias is one-directional and runs **toward** our conclusion: a correct output
mislabelled incorrect joins the incorrect pool, passes the checks because it is
well formed, and is counted as a false acceptance. That inflates ε and
understates the ceiling.

**Pre-registered:** α below 0.67 voids the exercise rather than being reported
as weak. The conclusion survives if the corrected ceiling for both OpenAI models
stays under one point; otherwise withdraw near-exhaustion for that task rather
than rescoping it. IE is highest-risk, since exact match on field values
penalises span-boundary and normalisation variants a human would accept.

### X6. Prompt sensitivity (closes **B8-V2**)

| | |
|---|---|
| **Claim tested** | the 0.25-point ceiling |
| **Design** | five variants fixed in advance (see `config.yaml`) |
| **Command** | generate with `prompt_id` set, then `python3 -m soundver.validity prompts --records ...` |
| **Output** | ceiling per variant, and the **maximum** across variants |
| **Effort** | 5× the E2 generation cost; no annotation |

ε is a property of an error distribution the prompt shapes, so a bound computed
under one prompt is a bound under one prompt. The `format_reminder` variant is
**adversarial to our claim** — it should lower ε by removing malformed outputs —
and is included for exactly that reason.

**Pre-registered:** report the range, not the mean. The headline survives if the
*maximum* ceiling stays under one point for both OpenAI models.

### X7. Exhaustive sub-conjunctions (closes **B11**)

| | |
|---|---|
| **Claim tested** | Cor. 3(a), the paper's main object |
| **Command** | `python3 -m soundver.reconcile --records ... --exhaustive` |
| **Cost** | **none** — re-scores candidates that already exist |
| **Effort** | minutes |

Cor. 3(a) quantifies over all 2ᵏ−1 sub-conjunctions; E4 walks one chain of
three. Since the corollary is a proof, a violation means a *measurement*
problem: a check that is not actually sound, or a correctness label that
presupposes one of the checks. E4 has already found one ε-monotonicity
violation on morphology, and this run is what separates an artifact from a
systematic effect.

### X8. Model snapshots and versions (closes **B9**)

Record the OpenRouter snapshot strings actually served (`openai/gpt-4o-2024-11-20`,
not `openai/gpt-4o`) and the access date for every run, plus `sqlglot`'s version.
These are moving endpoints; without the snapshot, nothing here is reproducible,
and ARR's checklist asks for them. `sqlglot`'s version matters specifically
because two parsing defects in the schema-validity checker are reported in
Section 7 and their behaviour is version-dependent.

---

## P2 — improves the paper, not required for submission.

### X9. Heterogeneity-robust ceiling

Cor. 3(b)'s figures assume homogeneous rates, and Cor. 5 shows the plug-in at
pooled rates **understates** the heterogeneous gain — by a factor above 1.7 in
the released checker. Bin instances by difficulty, re-estimate ε per bin, and
report E[gain] rather than the plug-in. This converts a disclosed weakness into
a measured quantity. It is the first thing to run after the P0 items.

### X10. Multilingual test of the typological prediction

The paper predicts δ for a concatenation check is near zero for agglutinative
languages under surface annotation and large for templatic root-and-pattern
morphology, independently of model quality. SIGMORPHON 2022 ships the
languages. Hold the check, models and instance count fixed; vary only the
language; take at least one agglutinative and one templatic case. This is the
natural next paper and the strongest thing the work could add for a COLING
audience.

### X11. Compute accounting

Total spend was never tracked, so the paper reports no figure. Instrument the
harness now so the next version can. This is a checklist answer (C1), not a
scientific claim.

---

## Dependency graph

```
X1 (records) ──┬── X2 reconcile ── X3 degenerate rows
               ├── X7 exhaustive          (free)
               └── X9 heterogeneity       (P2)

X4 seeds  ── independent, needs re-generation
X6 prompts ── independent, needs re-generation
X5 labels ── needs X1 for the sampler
X8 versions ── your logs, no compute
```

**If you can only do one thing: X1.** Four of the five blocking findings close
behind it, and X2, X3 and X7 are then a single command.

---

## X0 — the direction test. Do this before anything in P1 or P2.

`RESEARCH_DIRECTION.md` argues the paper's centre of gravity should move from
the ceiling theorem to the **decay of verifier power as models improve**. That
argument rests on four models on one task. This experiment decides whether it
holds.

| | |
|---|---|
| **Question tested** | does 1−ε decay smoothly with model accuracy, and is the rate a property of the task or of the model family? |
| **Datasets** | Spider dev only, unchanged |
| **Models** | the current four **plus four to six more**, chosen to widen the accuracy range and to give ≥3 models inside at least two families |
| **Command** | `python3 -m soundver.ladder --records data/records.jsonl --out out/` |
| **Output** | `out/ladder.json`; per-task decay fit; per-family slopes |
| **Effort** | ~1 day of API time. No new method, no new task, no annotation. |

**Pre-registered readings, fixed now:**

- **Decay confirmed** if 1−ε falls monotonically in accuracy with R² ≥ 0.7 over
  ≥ 6 models. Then redesign: the decay is the paper.
- **Task-governed** if per-family slopes agree within 30%. The rate is a
  property of the output space, which is the strongest version of the result and
  the most linguistically interesting.
- **Model-governed** if they disagree. Still a paper, a different one: the rate
  depends on how a model family fails, not on the task.
- **Not supported** if ε scatters. Then finish the current paper as it stands
  and drop the redesign.

**One caution the smoke test already exposed.** Resolving ε *differences between
adjacent models* needs more instances than resolving ε itself. Two models 2
accuracy points apart may not separate at n=200. Budget ≥ 400 instances per cell
for the ladder, and report the interval on each ε, not just the point.
