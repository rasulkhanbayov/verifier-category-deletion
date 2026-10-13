# Claim–Evidence Ledger (version4 / v4.1 paper), 2026-10-13

Format: **Claim** · location · required evidence · available evidence (file) ·
support · gap · action. Numbers come from `gen/numbers.tex` (generated from
`../code/out/`). Support: Strong / Moderate / Weak.

## A. Diagnosis (contribution 1)

| # | Claim | Location | Required evidence | Available evidence | Support | Gap | Action |
|---|---|---|---|---|---|---|---|
| A1 | F1 selection deletes a category on CoNLL in 69% of resampled selections (AutoPyVerifier objective 69%) | Abstract, Intro, C1, §6.1, Tab 1 | Resampling over A and candidate pool; deletion measured on B | `out/robust_ie.json` (200 replicates) | Strong | RESOLVED by E1: the 69% is exactly the availability rate of the deleting check (138/200); F1 and APV delete in 100% of those, 0% otherwise | Text restated (abstract, C1, §6.1) |
| A2 | The deleted group is the miscellaneous category; on the fresh draw, the F1 filter loses 37/44 such inputs vs 1/44 for certified | §6.1 | Per-subgroup filter loss on untouched data | `out/report_ie_fresh.json` | Strong | — | — |
| A3 | The deleting check is LLM-written ("else field should not include proper nouns") | Intro | Candidate source | `out/candidates/ie_*.jsonl` (id ie-r0-84f7d14832) | Strong | — | — |
| A4 | F1 takes a check iff rejected-output precision < F1/2 (Prop. 2) | §4, App. A | Proof | Proof (known result, attributed) | Strong | — | — |
| A5 | Prop. 2 predicts which tasks delete: only CoNLL has a below-threshold group plus an isolating candidate | §6.1 | Per-task group precision vs threshold; isolating candidates | `out/f1rule.json` | Moderate | One natural deletion out of six initial pools; E5 adds a natural partial loss (29.5%) | Reported as consistent with the rule, not a validated predictor |
| A6 | Few-NERD stress test: F1 takes the 4/8 injected checks with lowest rejected precision (≤ 0.18), deletes in 99.5%; budgeted, F1-constrained and group selection take none and delete 0% | §6.1 | Controlled injection + resampling | `out/robust_fewnerd_inject.json`, `out/f1rule.json` | Strong (mechanism) | Injected checks written by us | Stated in Limitations; E1 on the inject run gives availability-conditional rates |
| A7 | SQL control check (precision 0.65 > threshold 0.43) is never selected | §6.1 | Same | `out/robust_sql_inject.json` | Strong | — | — |

## B. Consequence (contribution 2)

| # | Claim | Location | Required evidence | Available evidence | Support | Gap | Action |
|---|---|---|---|---|---|---|---|
| B1 | Students trained on F1-filtered CoNLL data recall 0.08 of misc. entities vs 0.31 with certified filtering, at similar accuracy (50.4 vs 48.0) | Abstract, C2, §6.2, Tab 3 | Several training seeds; same student; same test | `out/distill_ie_seeds.json` (3 seeds) | Strong | — | — |
| B2 | Not a data-size effect: size-matched certified set keeps recall 0.29 | C2, §6.2 | Subsample to F1 set size | `out/distill_ie_matched.json` (3 subsamples) | Strong | — | — |
| B3 | Same at 1.7B: recall 0.39 vs 0.10 | C2, §6.2 | Larger student | `out/distill_ie_1p7b.json` | Moderate | One seed | E4 (optional, GPU) |
| B4 | GRPO with the F1-gated reward unlearns the category (0.37 → 0.13 / 0.09); certified gate keeps it (0.32 / 0.44); label reward 0.42 / 0.55 | Abstract, C2, §6.2 | Several seeds; label-reward control; same start | `out/rl2_ie.json` (2 seeds each) | Strong | RESOLVED by E3: 4 seeds each. F1 gate 0.11±0.04 (max 0.15) in every seed; certified 0.40±0.08 (0.32–0.49); accuracy flat | Text and Tab 3 updated (`out/rl2_ie_seeds.json`) |
| B5 | Few-NERD distillation: certified beats hand-written +3.5 [+1.5, +5.6] (one seed), level with F1 over 3 seeds | §6.2 | Seeds | `out/distill_fewnerd.json`, `out/distill_fewnerd_seeds.json` | Moderate | Hand-written has one seed | Low priority (stated as one seed) |

## C. Remedy (contribution 3)

| # | Claim | Location | Required evidence | Available evidence | Support | Gap | Action |
|---|---|---|---|---|---|---|---|
| C1 | Budgeted selection never deletes a category in 6×200 resamples or in the stress test | Abstract, C3, Tab 1 | Resampling on all tasks | `out/robust_*.json`, `out/robust_*_inject.json` | Strong | RESOLVED by E2: a per-output (SPADE-style) budget also deletes 0% on all six tasks and the stress test, with similar catch (CoNLL 49.5 vs 49.0%) | Remedy narrowed: protection comes from budgeting false rejection at all; per-input form adds the certifiable quantity and Prop. 1 guarantees (intro, C3, §6.1) |
| C2 | Prop. 1(c): a budget τ rules out deleting any group holding > 2τ of inputs | §4 | Proof + empirical consistency | Proof; τ=2% selections have γ̂_B ≤ 20/1000 | Strong | — | — |
| C3 | Certified bound covers the mean test γ on all six tasks; single 200-input draws exceed it on Few-NERD, SQL and GSM8K | §6.4, Tab 4 | Like-with-like test pools | `out/robust_*.json` (test_bstruct) | Moderate | Only 3 draws per task; dev draws for 4 tasks | Wording already precise |
| C4 | Coverage over resamples 100/100/100/93/100/73% (CoNLL/Few-NERD/FC/GSM8K/morph/SQL); SQL below nominal under database shift | §6.4, Limitations | Resampling coverage | `out/robust_*.json` | Strong (as a limitation) | — | — |
| C5 | Average accuracy level with or slightly below F1: fresh CoNLL Llama −2.5 [−5.6, +0.5]; dev −2.9 [−4.8, −1.0]; ties elsewhere | Abstract, C3, §6.3 | Paired bootstrap on fresh data | `out/report_*_fresh.json`, `out/report_ie_multi.json` | Strong | — | — |
| C6 | Certifying on gold alone claims 5.19% on SQL (Bonferroni-corrected, as for the main certificate; 4.84% uncorrected); test rate 13.38% (2.6-fold) | Intro, §6.4 | Ablation | `out/ablate_sql_multi.json` | Moderate | One task (CoNLL gold-only did not fail) | Stated for SQL only (already) |
| C7 | Certified vs hand-written gains: CoNLL +6.2/+5.4/+3.6; Few-NERD +1.6/+0.9/+0.7 | §6.3 | Paired bootstrap | `out/report_*_fresh.json` | Strong | — | — |
| C8 | On weaker SQL models the certified verifier's δ̄ is 0.71/0.49% (no formal claim) | §6.4 | Fresh weak-model outputs | `out/report_sql_fresh_weak.json` | Moderate (descriptive) | — | — |

## D. Side claims (appendix)

| # | Claim | Evidence | Support |
|---|---|---|---|
| D1 | Synthesis raises catch mainly where the output format carries content (CoNLL 13.4→52.5%, Few-NERD 14.5→28.2%) | `out/robust_*.json` | Strong (descriptive) |
| D2 | Opus candidates catch far more than GPT-4o's on CoNLL (50.2 vs 23.3%) | `out/ablate_ie_multi.json` | Strong (descriptive) |
| D3 | Hand-written morphology concatenation check deletes every canonical-segmentation word (80/80); GSM8K "####" check keeps 0.70 of weak models' correct outputs | `out/report_morph_fresh.json`, `out/report_math_fresh_weak.json` | Strong |

## E. Missing experiments (design audit)

| ID | Experiment | Hypothesis | Protocol | Baseline / control | Metric | Claim tested | Interpretation | Priority |
|---|---|---|---|---|---|---|---|---|
| E1 | Deletion conditional on isolating-check availability | F1 deletes in ~100% of replicates where the isolating check is in the candidate subsample and ~0% otherwise | Replay robust.py's RNG; record availability and selection per replicate | Same selectors | Deletion rate given available / not | A1, A5, A6 | If ~100%/0%: restate A1 as "whenever available, F1 takes it" (stronger, matches Prop. 2). If well below 100%: deletion depends on the sample too; keep 69% as is | **Done**: 138/200 available; F1/APV 100% / 0% |
| E2 | Output-level (SPADE-style) false-failure budget | A per-output budget also prevents deleting large groups (Prop. 1(c) analogue), but differs from the per-input budget in catch and in the guarantee | Greedy max-catch s.t. FFR over correct model outputs ≤ 1% on A, in the same replicates | Input-level budget, F1, F1-constrained | Deletion rate, catch | C1, novelty vs SPADE | If it also gives 0%: the protection comes from any false-rejection budget; our distinct parts are the per-input/per-group certificate and its guarantees (Prop. 1). If it deletes: per-input measurement matters | **Done**: 0% everywhere, similar catch -> remedy claim narrowed |
| E3 | RL seeds 2–3 for F1 and certified gates | F1 gate unlearns (recall < 0.2) in every seed; certified stays ≥ 0.3 | `train_grpo.py`, same start and settings, seeds 2, 3 | Label reward (existing) | Misc. recall, accuracy | B4 | Consistent: B4 → Strong. Mixed: report per seed, narrow to "in k of 4 seeds" | **Done** |
| E4 | 1.7B student, second seed | Same gap | `train_sft.py --model Qwen/Qwen3-1.7B --seed 1` for both filters | — | Misc. recall | B3 | Confirms or narrows B3 | Low (free, ~1.5 h GPU) |
| E5 | Natural isolating checks on Few-NERD | A feedback round produces an isolating check | One Opus + GPT-4o round with standard split-A feedback (63 checks, $0.29), resampling with them added | Existing pool | Per-group wiped fraction | A5 | **Done**: casing check (rejects all-lowercase entities) -> F1 removes 29.5% of 'other' on average (p90 40%), short of deletion; budgeted 2.2%, per-output 7.6%, group 1.0%. APV deletes 4+-entities in 71% via two buggy reject-almost-all checks (macro-F1 failure, different mechanism). Added to §6.1, C1, Limitations | Done |
| E6 | Binomial 95% intervals for deletion and coverage rates | — | Wilson intervals over 200 replicates | — | — | A1, C1, C4 | Reporting only | Low (free) |

Not needed for this paper type: efficiency and memory scaling (selection is a greedy loop over cached verdicts; the cost is the API generation, reported as $73).

## F. Adversarial audit (2026-10-13)

Class: A = new experiment, B = analysis of existing outputs, C = text/claim calibration.
Ordered by likely impact on reviewer confidence.

| # | Skeptic's alternative explanation / issue | Class | Resolution | Status |
|---|---|---|---|---|
| F1 | Downstream gap comes from other differences between the F1 and certified check sets, not the deleting check | A + B | B: F1-filtered training data keeps 612 misc entities, 0% title-case, 8% correct (certified 58%, 26%; oracle 222, 100% correct, student recall 0.37 → quantity is not the cause) (`out/adversarial_ie.json`). A (decisive): distil on F1 selection minus ONLY the deleting check, 3 seeds (`logs/run_ablate_deleter.sh` → `out/distill_ie_f1minusdel.json`). Tests C2 "the deletion is learned". If recall recovers to ~0.3 → the check causes it; if not → other checks matter, narrow C2 | B done; A done: F1 minus only the deleting check -> recall 0.34 (0.33–0.35 over 3 seeds; acc 50.1) vs F1 0.08, certified 0.31, similar accuracy -> the check causes the downstream loss. In §6.2 |
| F2 | Certified CoNLL/Few-NERD verifiers use τ=5%, but resampling deletion was only measured at τ=2% | B | Resampling at τ=1% and 5% for all selectors and tasks (`logs/run_budget_sens.sh` → `out/resample_detail_*_b0.0{05,25}.json`). Prop 1(c) allows deleting groups < 2τ = 10% at τ=5% | Done: 0% deletion for every budgeted variant on all 6 tasks at τ=1% and 5% (12 runs); worst group loss ≤ 18%. In §6.1 |
| F3 | Rejected outputs are label errors, not correct answers | B | Deleting check rejects the GOLD answer for 86% (A) / 81% (B) of misc sentences | Done, §6.1 |
| F4 | 50% deletion threshold is arbitrary | B | Mean worst-group loss over resamples: F1 57% vs budgeted 4% (CoNLL) | Done, §6.1 |
| F5 | No uncertainty on resampling rates | B | Wilson 95%: CoNLL F1 deletion 69% [62, 75]; budgeted 0/1,200 (95% upper 0.25%); SQL coverage 73% [66, 79] | Done (deletion in §6.1; SQL coverage macro available) |
| F6 | Unequal labelled data: certification uses B (extra 1,000 inputs) | B | F1 selection on A+B still takes the check; 78–85% of misc sentences in test pools lose every correct output | Done, §6.1 |
| F7 | Gold-defined groups chosen post hoc | B + C | Gold-free k-means clusters richest in misc sentences lose 28–29% under F1, others ≤ 4% | Done, §6.1 |
| F8 | Distillation provenance: the training sets were built from selections BEFORE the last CoNLL proposer round | B + C | Reconstructed exactly (`out/distill_ie_selections_pre_repair.json`; rebuilt sets identical: 2,705 / 3,448 rows). Final selections add 1 (F1) / 2 (certified) repair-round checks, none the deleting check. Disclosed in App. Implementation | Done |
| F9 | "SPADE-style" is not SPADE's exact objective; APV's LLM critic might have filtered its faulty checks | C | Stated in Limitations | Done |
| F10 | Validity check reuses development draws (4 tasks); English only; possible pretraining contamination | C | Stated in Limitations (contamination affects accuracy levels, not the comparison between selectors on the same outputs) | Done |
| F11 | Insufficient seeds (RL 2, 1.7B 1) | A | RL now 4 seeds (E3, done). 1.7B: one seed, stated; second seed optional (E4) | RL done; 1.7B stated |
| F12 | Data leakage / train–test overlap | — | Checked: A/B/proposal/distillation are disjoint slices of training sets; test and fresh draws from evaluation sets; fresh disjoint from development draws; FC test = every 10th Glaive example, excluded from training slices | No issue |
| F13 | Unequal compute / hyperparameter advantage | — | All selectors use the same candidate pool and outputs; students share hyperparameters; no tuning per selector | No issue |

## G. Scientific integrity audit (2026-10-13)

Line-by-line check of every substantive statement; corrected directly.

| # | Location | Statement (before) | Problem | Correction (evidence) |
|---|---|---|---|---|
| G1 | Abstract | "a check is accepted exactly when …" | Overclaim: the condition decides whether a check raises F1 (eligibility); greedy takes the best eligible one | "adding a check raises F1 exactly when …" (Prop. 2) |
| G2 | Abstract | "predicts which injected checks F1 selects" | Three other injected checks were below the initial threshold but not taken | "F1 selects the injected checks whose rejected outputs fall furthest below it" (`f1rule.json`) |
| G3 | Abstract, C1 | "five other tasks are unaffected" / "F1 deletes on none of the five tasks" | False: F1 deleted in 0.5% (1/200) of morphology resamples; the rounded macro printed "0" | "almost never affected" / "at most 0.5%"; new `rate()` formatter prints sub-1% rates with one decimal (Table 1 morphology F1 now 0.5) |
| G4 | Intro | "an error … removes that kind of answer from what models learn" | General causal claim from one task | "can remove" |
| G5 | Intro | "checks fail on correct answers that differ from the reference" | Shown on SQL only (CoNLL gold-only did not fail) | "can fail"; SQL-specific number kept |
| G6 | §7.2 | "the student learns that the category never holds a proper noun" | Student outputs not measured; F1 student's misc predictions are 21% title-case, not 0% | Measured: F1 student predicts 78 misc entities (certified 190), 21% title-case (certified 49%) |
| G7 | §7.2 | RL "at unchanged overall accuracy" | 62.8 vs 63.6 | "similar overall accuracy (62.8 vs 63.6 at the start)" |
| G8 | §7.2, App. RL | base model "almost never produced correct misc entities" | Unquantified | recall 0.11; correct on 2.9% of misc sentences (`rl2_ie.json`) |
| G9 | §7.4 | "every Spider gold query uses table aliases in joins" | Absolute; measured 818/819 | "818 of the 819 gold queries with joins in our splits" |
| G10 | §7.3 | "the worst group lost at most 18%" | Measured for budgeted selection only | "under budgeted selection" |
| G11 | Intro | "small exactly for categories models rarely get right" | Rhetorical "exactly" | removed |

Verified unchanged: all citations used were checked against their sources in the novelty audit (or earlier verified entries); Prop. 1 and 2 statements and proofs (math audit); "never deletes" for budgeted variants (0/1,200 per variant, plus τ = 1% and 5%); "in all four seeds" (RL); causal "the cause is the deleting check" (intervention: ablation, 3 seeds).

## H. Simulated ARR review (2026-10-13; independent agent, review in session scratchpad)

Scores: Soundness 3, Excitement 3, Overall 3 (Findings), Confidence 4. Props and all CP bounds recomputed correct.

| # | Class | Objection | Resolution | Status |
|---|---|---|---|---|
| C1 | Critical | One natural instance; framing reads general | Reframed: abstract "We document this failure", C1 "in one natural case", conclusion "observed naturally on one of six tasks; how often it arises elsewhere remains open". **Needs new evidence to resolve fully:** natural proposer rounds (with standard feedback) on additional NER/classification datasets with rare categories (e.g. OntoNotes, WNUT, CoNLL++), several proposer models, measuring how often an isolating check appears and is selected | Text done; experiment specified |
| M1 | Major | Prediction circular (Prop. is an identity); Few-NERD threshold missing | §4 states the proposition needs no test and §7.1 tests whether the ingredients occur and finite-sample selection behaves as implied; Few-NERD threshold 0.27 added | Done |
| M2 | Major | Missing baseline: gold admission + F1 | Run (`out/redteam.json`): it never takes the casing check and deletes no group on any task; reported in §7.3 with its limitation (no guarantee; gold-only certification fails 4.5× on SQL); contribution (3) now says simpler safeguards also prevented deletion | Done |
| M3 | Major | Little novelty over SPADE | Contribution (3) states per-output budget and gold admission also prevented deletion; certificate is what is added; E5 2.2 vs 7.6% kept as the only evidence for per-input | Done (claim narrowed) |
| M4 | Major | Small groups weakly protected; group certificate unreported | §5 states τ=5% guarantees only groups > 10%; §7.4 reports group certificate: 5/6 tasks pass, CoNLL worst-group bound 20.5% | Done |
| M5 | Major | CIs treat dependent bootstrap replicates as independent | Removed Wilson/rule-of-three intervals on resampling rates and coverage; §7.3 explains replicates share B | Done |
| M6 | Major | Validity check on inspected dev draws; GSM8K hand-written failure undiscussed; "bounds held" overstated | Fresh draws restructured like B: holds on CoNLL 1.00%, GSM8K 0.33%, morph 0.67%; FAILS on SQL 2.33% vs 1.91% (reported); GSM8K hand-written failure discussed; abstract calibrated | Done |
| M7 | Major | Possible adaptive reuse | Data-usage protocol paragraph (App. Implementation) | Done |
| M8 | Major | Table 1 rows missing spacer cells (Hand showed 178) | make_numbers emits spacer cells (15 cells/row) | Done |
| M9 | Major | Certified not uniformly safer (Few-NERD 29 vs 7, morph 8 vs 1) | §7.3: "a budget is spent, not saved" sentence | Done |
| M10 | Major | RL unlearning near-mechanical; "similar" accuracy undersells | §7.2 states it is the expected mechanism, experiment measures size; accuracy F1 62.8 vs start 63.6 vs certified 65.0 | Done |
| m1–m18 | Minor | definitions, numbers, wording | lost/deleted defined precisely; Few-NERD distill reported as 3-seed means; identical-recall note; ablation pool provenance in caption (52.0 vs 52.5); "level with" → "trails by up to 2.9"; gold-only on matching quantity (23.3% vs 5.19%, 4.5×); test sizes and set sizes as macros; F1 without gold selects same check; F_β break-even remark; MISC annotation noise in Limitations; Table 1 caption defines all columns and budgets; no-τ-certifies rule; morphology concatenation example in intro; single-split note in ablation caption | Done |
