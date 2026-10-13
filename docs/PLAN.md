# version4 plan: Certified Verifier Synthesis

## 0. HANDOVER: read this first (written 2026-10-09)

### 0.0 STOP POINT (2026-10-10, user asked to stop and record) — READ FIRST

**Nothing is running.** No background jobs, drivers or training processes.
**Spend:** version4 $37.49 (OpenRouter key usage $367.29; baseline $327.70,
$2.10 of that spent outside this work). Cap $100 (user-approved).

**What exists and is final:**
- 4 tasks x 3 models (GPT-4o-mini, Llama-3.1-70B, Qwen2.5-72B): proposal,
  admit (A), certify (B) pools in code/data/pools/ (multi-model; mini-only
  copies in code/data/pools_mini_only/); test grids in code/data/test/ (200
  inputs x 3 draws x 33 outputs per model); test pools restructured like B
  in code/data/test_bstruct/ (for the like-with-like check, not yet used).
- Candidates: code/out/candidates/ (sql 134, ie 48 + 20 repair, morph 49,
  math 107 incl. a GUIDED round `math_round2_opus_guided`).
- Results: code/out/report_{ie,sql,morph,math}_multi.json,
  curve_*_inst_multi.json, curve_*_dense.json, ablate_*_multi.json,
  subgroup_{ie,math}.json, distill_ie.json, distill_ie_seeds.json,
  report_ie_multi_r2.json (repair round), admit_ie_multi.json.
- Downstream (IE): code/data/distill/ (sft sets, student generations),
  seeds in code/data/distill/seeds/. Training venv: version4/.venv_train
  (torch 2.5.1, transformers 4.53.3, peft 0.15.2; fp32 only on the P100).
- Paper draft: paper/main.tex + paper/gen/ (make_numbers.py, 540 macros).
  NOT compiled. It still contains the overclaims the review found (0.10.1)
  and does NOT yet use the 3-seed distill numbers or the v4.1 changes.

**Headline numbers (all from the files above):**
- IE best-of-32, certified minus hand-written: +3.9 to +6.1 pts (CIs > 0).
- Certified vs F1-selected: average accuracy equal or slightly worse (IE
  Llama -2.9 [-4.8,-1.0]); worst group (has_else) +2.9 to +9.0 (CIs > 0).
- Downstream student (3 seeds): has_else acc 17.6+-0.0 (certified-filtered)
  vs 5.6+-0.6 (F1-filtered); misc recall 0.310 vs 0.085+-0.026; overall
  48.0+-1.5 vs 50.4+-1.0.
- Gold-only validation (SQL): claims 4.84% at its certified budget (tau=5%),
  measures 13.38% on test (reviewer's figure; use certified rows).
- GSM8K: null (models 91-95% accurate); hand-written "####" check unsound
  under our lenient label (gamma 455/1000 on B).

**Where the plan stands (section 0.10):** approved by the user, including
the optional RL experiment. Done: plan written; distill seeds; B-structured
test pools. NOT started: W1 text fixes, W2 group-conditional selection, W3
like-with-like check + resampling study, W4 strong hand-written / F1-
constrained baselines, W5 new data (needs budget approval above the cap),
W6 robust downstream + RL, W7 related work and rewrite.

**Next step when resuming:** write `certver/robust.py` (designed but not
written): groups = pre-registered gold subgroups (certver/filtering.py) +
char-n-gram TF-IDF k-means clusters of inputs (k~8, fit on A); selectors =
hw, F1, F1 s.t. gamma_A<=tau/2, budgeted (existing select_inst),
group-constrained (gamma_A,g<=tau/2 for every group with n>=50); budgets
{1,2,5}% with Bonferroni (level 1-0.05/3, and /G per group); like-with-like:
test gamma on data/test_bstruct vs U_B for every verifier; resampling: ~200
replicates of (bootstrap of A instances x random 70% candidate subset),
rate of "a group with n>=30 loses >=50% of its instances entirely" on B and
test_bstruct, and coverage of U_B. Verdicts are cached in code/out/verdicts/.


This file is the single source of truth for version4. A new session (or a
new Claude account) should read section 0 in full, then section 10 (progress
log) for the history. Sections 1-9 are the original plan; where they
conflict with section 0, section 0 wins.

### 0.1 Where things stand

- **Week 1-3 work is done, ahead of schedule.** Pipeline built and run end to
  end on all three tasks, full test grid collected (200 instances x 3 seeds
  x 3 models x 3 tasks), final reports produced. Nothing is running.
- **Spend:** about $19.47 of the $100 cap (OpenRouter key usage $349.27 on
  2026-10-10; baseline $327.70, of which $2.10 was spent outside this work).
- **2026-10-10: ablations (E4) done**, see 0.2b (`certver/ablate.py`). No API spend.
- **2026-10-10: multi-model A/B pools done**, see 0.2c; these are now the
  headline numbers. Nothing is running.
- **2026-10-10: full first draft written: `paper/main.tex`** (see 0.9). Not
  compiled (no LaTeX here): user must compile, check the 8-page limit, and
  read it.
- **2026-10-10: independent review done; deadline dropped by the user. CURRENT PLAN = section 0.10.**
- **The paper is not written yet.** (superseded, see line above) Next phase is: decide the framing
  (0.4), the remaining experiments (0.6), then write.
- **User decisions so far:** (1) skip ARR Oct 2026 with version3, reframe as
  version4; (2) API budget cap $100; (3) certified false-rejection BUDGET
  instead of zero tolerance; (4) certify at the INSTANCE level and measure
  coverage / data-filtering harm (option 1 of 2026-10-08).
- **Deadline still unknown.** Fill in `DEADLINE` below from
  aclrollingreview.org (next ARR cycle after Oct 2026).

### 0.2 Final results (full test grid; source files in version4/code/out/)

Files: `out/report_{sql,ie,morph}.json` (test, all seeds, produced by
`python -m certver.report`), `out/curve_{task}_inst.json` (selection on A,
certification on B). Gated best-of-32 accuracy, n = 600 (instance, seed)
units per model, paired bootstrap 95% CI. "certified" = smallest budget in
{1%, 2%, 5%} whose instance-level certificate holds on B (pre-specified).

| task | certified selection | model | base | hand-written | certified | F1 baseline | certified - hw |
|---|---|---|---|---|---|---|---|
| IE | itau=5% (13 checks; B gamma 19/1000, U95 2.78%) | Llama-3.1-70B | 39.0 | 43.6 | 49.6 | 48.6 | +5.9 [+4.1, +7.8] |
| | | GPT-4o-mini | 33.8 | 33.8 | 38.7 | 38.7 | +4.9 [+3.3, +6.6] |
| | | Qwen2.5-72B | 47.7 | 49.1 | 53.0 | 52.8 | +3.9 [+2.5, +5.5] |
| SQL | itau=2% (5 checks; B gamma 5/1000, U95 1.05%) | Llama-3.1-70B | 68.7 | 74.1 | 74.1 | 74.1 | +0.1 [+0.0, +0.3] |
| | | GPT-4o-mini | 73.3 | 74.1 | 74.2 | 74.6 | +0.2 [+0.0, +0.5] |
| | | Qwen2.5-72B | 74.8 | 75.7 | 76.1 | 75.7 | +0.3 [+0.0, +0.8] |
| morph | itau=2% (5 checks; B gamma 5/1000, U95 1.05%) | Llama-3.1-70B | 36.3 | 35.4 | 36.4 | 36.4 | +1.0 [-0.5, +2.6] |
| | | GPT-4o-mini | 39.3 | 39.2 | 39.5 | 39.5 | +0.3 [-0.7, +1.3] |
| | | Qwen2.5-72B | 38.5 | 37.2 | 38.7 | 38.7 | +1.5 [+0.3, +2.9] |

Certified minus F1 baseline: IE Llama +0.9 [+0.2, +1.8], others within
[-1.2, +1.2], i.e. **no accuracy advantage over uncertified F1 selection**.

**Does the certificate hold on test?** Instance-averaged false-rejection rate
on test vs the bound from B:
- SQL: certified 0.12-0.44% <= 1.05% for all models. **F1 baseline
  1.7-2.9%**, above what our bound would allow.
- IE: certified 0.56-1.59% <= 2.78% for all models; F1 0.56-1.32%.
- morph: certified 0.0% <= 1.05%; hand-written 14-19% (unsound
  `concatenates`).

False acceptance (eps) on test, hand-written -> certified: IE 0.72-0.96 ->
0.47-0.62; SQL 0.77-0.85 -> 0.76-0.82; morph ~0.95-0.99 (nothing to catch).

**Data-filtering experiment** (keep accepted outputs as training data, all
seeds and models pooled; "lost" = instances whose every correct output is
filtered out; subgroups defined from gold only):

| task | selection | precision | recall | lost | worst subgroups |
|---|---|---|---|---|---|
| SQL | hand-written | 0.757 | 0.999 | 1/1502 | |
| | certified | 0.762 | 0.999 | 1/1502 | |
| | F1 baseline | 0.777 | 0.981 | **23/1502** | group_by 15/400, order_by 10/349, nested 7/172 |
| IE | hand-written | 0.432 | 0.999 | 0/1003 | |
| | certified | **0.552** | 0.994 | 8/1003 | plain 5/551 |
| | F1 baseline | 0.546 | 0.994 | 7/1003 | |
| morph | hand-written (v3) | 0.418 | 0.880 | **151/933** | canonical-differs-from-surface **151/154 (98%)** |
| | certified | 0.381 | 1.000 | 0/933 | |
| | F1 baseline | 0.380 | 1.000 | 0/933 | |

### 0.2b Ablations (E4), done 2026-10-10 (`out/ablate_{sql,ie,morph}.json`, `python -m certver.ablate`)

Every variant selects on A (instance-level rule), then: the bound it would
CLAIM, and the test grid (seeds 0-2, 3 models pooled; "test inst-delta" =
instance-averaged false-rejection rate). Budget tau = 2% unless noted.

| ablation | task | claimed bound | test inst-delta | holds? | B catch | test gated acc (base) |
|---|---|---|---|---|---|---|
| main | SQL | 1.05% | 0.22% | yes | 21.0% | 74.8 (72.3) |
| **gold-only admission + certification (HardTests-style)** | SQL | 1.81% | **12.1%** | **VIOLATED (7x)** | 41.5% | 74.1 (72.3) |
| main | IE | 2.30% | 0.89% | yes | 56.4% | 46.8 (40.2) |
| gold-only | IE | 2.06% | 0.89% | yes | 56.4% | 46.8 (40.2) |
| single split (bound computed on A) | SQL / IE | 1.57% / 1.44% | 0.22% / 0.89% | yes / yes | same as main | same as main |
| proposer = GPT-4o only | IE | 1.31% | 0.89% | yes | **18.3%** | 42.7 (40.2) |
| proposer = Claude Opus only | IE | 1.81% | 0.41% | yes | **54.9%** | 46.7 (40.2) |
| proposer = GPT-4o only | SQL | 2.78% | 0.58% | yes | 16.1% | 74.6 |
| proposer = Claude Opus only | SQL | 0.77% | 0.22% | yes | 21.0% | 74.8 |

Candidate-pool size (B catch, mean over 5 random draws, tau 2%): IE 10% of
candidates 0.217, 25% 0.341, 50% 0.424, 100% 0.564; SQL flat (0.155, 0.174,
0.171, 0.210). Morphology: every variant identical (nothing to catch).

Reading:
- **Gold-only validation is the failure mode certification guards against.**
  On SQL it admits `check_alias_usage_in_complex_queries` (Spider gold always
  aliases joins as T1/T2; models often do not), `order_by_for_sorting_questions`
  and `group_by_for_aggregation_with_multiple_columns`; it certifies itself at
  1.8% and rejects 12.1% of correct outputs on test. Strongest evidence so
  far that certification must use correct MODEL outputs, not gold alone. On
  IE gold and model outputs look alike, so gold-only happens to be safe.
- **Single split did not break here**: A and B come from the same
  distribution, so the A-computed bound was optimistic (IE: A 8/1000 vs B
  15/1000) but still held on test. Report honestly; do not claim the second
  split is empirically necessary on this data (it is necessary for validity
  in principle, because selection on A biases A's count downward).
- **The proposer matters a lot**: Opus 3x GPT-4o's catch rate on IE; most of
  the IE gain comes from Opus's checks.
- **More candidates help on IE**, not on SQL.

**0.2b re-run on the multi-model pools (2026-10-10, out/ablate_{t}_multi.json;
use THESE in the paper):** tau 2%. SQL gold-only claims 2.66%, test 12.1%
(VIOLATED, 4.6x; B gamma 241/1000); main claims 1.69%, test 0.62% holds.
IE gold-only claims 2.54%, test 0.99% (holds). Single split: SQL claims
1.57%, IE 1.69%; both hold on test. Proposer, IE B catch: Opus 0.502 vs GPT-4o
0.220 (test gated 46.8 vs 42.7, base 40.2); SQL: Opus 0.204 vs GPT-4o 0.136.
Candidate fraction 10/25/50/100% -> IE B catch 0.217/0.241/0.424/0.512;
SQL 0.152/0.164/0.176/0.204. Morphology: no differences.

### 0.2c Multi-model admission/certification pools, done 2026-10-10

A and B now hold GPT-4o-mini + Llama-3.1-70B + Qwen2.5-72B outputs (1000
instances x 4 outputs x 3 models each); mini-only pools kept in
data/pools_mini_only/. Files: out/curve_{t}_inst_multi.json,
out/report_{t}_multi.json. Same test grid as 0.2. **These are now the
headline numbers** (the more realistic setting: admission sees the outputs
of every model the verifier will be used with).

| task | selection | test acc Llama / mini / Qwen | cert - hw | test inst-delta (bound) | filter precision / recall / lost |
|---|---|---|---|---|---|
| IE | hand-written | 43.6 / 33.8 / 49.1 | | 0.00-0.29% | 0.432 / 0.999 / 0 of 1003 |
| | **certified** itau=5% (16 checks, B gamma 26/1000, U95 3.59%) | 49.7 / 38.7 / 53.0 | +6.1 / +4.9 / +3.9 (all CIs > 0) | 0.56-1.59% (3.59%) holds | 0.555 / 0.994 / 8 |
| | **F1 baseline** (11 checks) | 52.7 / 39.8 / 53.1 | (cert - F1: -2.9 [-4.8,-1.0] / -1.0 / -0.1) | **6.1-9.0%** | 0.611 / 0.948 / **72**, incl. **has_else_type 64/77 (83%)** |
| SQL | hand-written | 74.1 / 74.1 / 75.7 | | 0.12-0.44% | 0.757 / 0.999 / 1 of 1502 |
| | certified itau=2% (6 checks, B gamma 10/1000, U95 1.69%) | 74.0 / 74.2 / 76.1 | -0.1 / +0.2 / +0.3 | 0.50-0.86% (1.69%) holds | 0.761 / 0.994 / 7 |
| | F1 baseline (10 checks) | 74.1 / 74.2 / 76.0 | | 0.89-1.48% | 0.762 / 0.991 / 13 |
| morph | certified itau=2% (7 checks, U95 1.44%) | unchanged from 0.2 | | 0.0% | 0.381 / 1.000 / 0 of 933 (hw: 151, F1: 0) |

**Key new finding (IE).** With multi-model admission data, F1 selection
admits GPT-4o's `else_field_should_not_include_proper_nouns` ("proper nouns
belong in person/location/organization"). That is false for CoNLL, whose
MISC/"else" category IS proper nouns (German, Euro 96), but Llama and Qwen
put so many wrong entities in "else" that rejecting them raises F1. Result:
F1 gets slightly HIGHER best-of-N accuracy (Llama +2.9) while, as a training
-data filter, deleting every correct example for 83% of instances with an
"else" entity. Certification rejects the check (it fails on correct
outputs). This is the clearest demonstration in the project that accuracy
can look better while a whole category silently disappears, and that the
certificate is what catches it.

SQL: still no gain from synthesis over hand-written; F1 is milder here.

### 0.3 Honest reading (what the data supports)

1. **Synthesis vs hand-written checks: strong.** IE +3.9 to +5.9 accuracy
   points (all CIs exclude 0), filter precision 0.43 -> 0.55. Checks were
   selected on GPT-4o-mini's training-split outputs only, and gains transfer
   to Llama and Qwen.
2. **Hand-written "free" verifiers are unsafe:** morphology's v3 stack deletes
   98% of one subgroup when used as a data filter and lowers best-of-N
   accuracy (Qwen -1.3 [-2.6, -0.1]); SQL's `schema_valid` rejects a gold
   query; v2/v3's SQL label itself was broken (Finding 1 in section 10).
3. **Certification vs uncertified F1 selection (AutoPyVerifier-style): weak
   on accuracy, clear on guarantees.** Accuracy is the same. But (a) our
   bounds held on test for every model and task, including two models never
   used for selection; (b) on SQL the F1 baseline's false-rejection rate
   (1.7-2.9%) is far above our certified 1.05%, and as a data filter it
   loses 23 instances concentrated in GROUP BY / ORDER BY / nested queries vs
   1 for ours. On IE with mini-only admission data F1 happened to be safe;
   with multi-model data (0.2c) it deletes 83% of the "else"-entity category
   from filtered data while gaining accuracy, and certification prevents it.
4. **SQL synthesis adds almost nothing on test** (catch rose on B, did not
   transfer to the dev split). Morphology: nothing to catch at all.

### 0.4 Recommended framing (not yet confirmed by the user)

"Certified verifier synthesis": (i) hand-written structural verifiers are
unsafe and weak (audit evidence: broken label, gold-rejecting checker,
subgroup deletion); (ii) LLM-synthesised checks are much stronger where
output constraints carry content information (IE); (iii) an instance-level
certificate, computed on a held-out split, is what tells you whether a
synthesised verifier is safe, and it holds on new models and test
distributions, whereas F1 selection can silently delete question types
(SQL). Do NOT claim an accuracy win over F1 selection. Honest venue
estimate: borderline main / likely Findings unless (0.6) adds a strong
result.

### 0.5 How to run (all from version4/code; Python 3.10; key in ../../.env)

```
python -m certver.pool --task {sql,ie,morph} --split {proposal,admit,certify,test} \
    --models <ids> --seeds 0 1 2 --instances 200 --candidates 32 --max-cost <usd> --out-dir data/test
python -m certver.propose --task ie --round 1 --n 25 --calls 1 \
    --proposer anthropic/claude-opus-5.5 --tag _opus --reasoning-effort low --max-tokens 20000
python -m certver.admit admit --task sql --candidates out/candidates/sql_round0.jsonl \
    --pool data/pools/pool_sql_admit_seed0.jsonl --out out/admit_sql_round0.json   # per-check report + feedback
python -m certver.curve --task ie --candidates "out/candidates/ie_*.jsonl" \
    --admit data/pools/pool_ie_admit_seed0.jsonl --certify data/pools/pool_ie_certify_seed0.jsonl \
    --test data/pilot/pool_ie_test_seed0.jsonl --taus 0.01 0.02 0.05 --out out/curve_ie_inst.json
python -m certver.report --task ie --out out/report_ie.json        # final test analysis, all seeds
python -m certver.filtering ...   python -m certver.ci ...          # older single-pool analyses
python -m certver.relabel <pool.jsonl>                              # re-apply the corrected SQL label
```

### 0.6 Next steps (in order)

1. **User: confirm framing (0.4) and fill DEADLINE.**
2. ~~Ablations (E4)~~ **DONE 2026-10-10**, see 0.2b, and re-run on the
   multi-model pools (results under 0.2b; use those). Gold-only
   certification fails 7x on SQL (key result); single split did not fail on
   this data; Opus >> GPT-4o as proposer; more candidates help on IE.
3. ~~Multi-model A/B pools~~ **DONE 2026-10-10** (about $4), see 0.2c. Produced
   the IE "else"-category result. Note: the 0.2b ablations were run on the
   mini-only pools; re-run on the multi-model pools DONE (0.2b).
4. ~~IE repair round~~ **DONE 2026-10-10** ($0.20): 20 Opus checks from split-A
   feedback (out/candidates/ie_round2_opus.jsonl). Catch on B 0.520 -> 0.525;
   test accuracy unchanged (out/report_ie_multi_r2.json). Diminishing returns;
   report as such. Headline IE numbers can use either report (identical).
5. Decide on E5 (RL): 2026 literature says false rejections mostly delay
   GRPO; only worth it if framing needs it. `trl`/`peft` not installed.
6. Re-run the novelty search (AutoPyVerifier follow-ups); read every cited
   paper before it enters the .bib (the 2026 arXiv ids in section 2 are
   unverified).
7. Write the paper (reuse version3 theory sections; do NOT reuse version3's
   SQL numbers).

### 0.7 Gotchas learned the hard way

- **Background jobs die when the Claude session ends.** Launch long runs with
  `setsid nohup python3 -m ... > log 2>&1 < /dev/null &`. `certver.pool` is
  resumable (skips finished instances), so just re-run the same command.
- **The sandbox uses multiprocessing `forkserver`**: never run sandbox code
  from `python3 - <<EOF` (stdin); put it in a module (e.g. `tests/*.py`) and
  run `python3 -m tests.x`.
- **Claude Opus 5.5 via OpenRouter**: reasoning cannot be disabled and
  `reasoning.max_tokens` is ignored; without `--reasoning-effort low` it
  spends the whole budget thinking and returns empty text (cost ~$1.4 wasted).
- **Proposer output format**: Python inside JSON breaks (escaping); use the
  `### CHECK` delimited format (already implemented).
- **`pkill -f <pattern>` can kill your own shell** if the pattern appears in
  the command line; use pgrep first.
- **SQL label**: always `certver/sqllabel.py`, never version2's
  `test_suite_accuracy`. All pools in data/ are already relabelled (old label
  kept as `correct_v2label`; backups in data/backup_v2label/).
- **gamma depends on outputs per instance** (4 on A/B, 33 on test); compare
  test's instance-averaged delta, not test gamma, against the B bound.
- **Verdict cache** lives in out/verdicts/<pool-signature>/; it is keyed by
  pool content and check source, so it is safe to keep.

### 0.8 File map (version4/code)

- `certver/`: data.py (splits), pool.py (generation), sandbox.py, propose.py,
  admit.py, curve.py (selection, F1 baseline, certification, trade-off),
  report.py (final analysis), ablate.py (E4 ablations), ci.py, filtering.py, sqllabel.py, relabel.py.
- `soundver/`: copy of version3's harness (checks, prompts, loaders, labels
  for IE/morph). Do not edit version3 itself.
- `data/pools/`: proposal/admit/certify pools (GPT-4o-mini, train splits).
- `data/pilot/`: 100-instance seed-0 test pilots; `data/test/`: full test
  grid, seeds 0-2 (seed-0 rows include the pilot rows).
- `out/candidates/`: all candidate checks + raw proposer responses
  (`*.raw*.txt`). Synthesised candidates: SQL 134 (rounds 0-3), IE 48, morph 49; curve.py adds version3's hand-written checks as `hw:*` candidates.
- `out/`: admit_*.json, curve_*.json, report_*.json, filter_*, ci_*.
- `logs/`: every run's log. `tests/`: inspection scripts.

### 0.9 The paper (version4/paper/)

- `main.tex`: complete draft (abstract, intro, related work, setup, method
  with 2 propositions, experimental setup, results with 3 tables + 1 figure,
  ablations, audit, conclusion, limitations, ethics; appendix: proofs,
  per-task certificates, implementation). About 3,200 words of body text.
- **Every number comes from macros** in `gen/numbers.tex` and tables in
  `gen/*.tex`, produced by `python3 make_numbers.py` from `code/out/`. After
  any re-run of experiments, re-run make_numbers.py; never hand-edit gen/.
- Headline sources: report_{ie,sql,morph}_multi.json, curve_*_inst_multi.json,
  ablate_*_multi.json, curve_*_dense.json (figure), admit_ie_multi.json (the
  "else" check), report_ie_multi_r2.json (repair round), relabelled SQL pools
  (label audit: 3.7% false-correct, 10.4% false-incorrect on 18,346 outputs).
- Bibliography: 11 new citations verified against arXiv (paper/new_refs.bib);
  corrected facts: HardTests' oracles compute expected outputs (inputs are
  validated by an LLM-written validator); "Pitfalls..." is now "From Accuracy
  to Robustness" (EMNLP 2026); the fuzzing paper is "Before the Model Learns
  the Bug". EMNLP/COLM venues come from arXiv comments only.
- Structural checks pass (braces, $ parity, refs, cites, macros). NOT
  compiled. To do by the user: compile, check page count and overfull boxes,
  read for tone; decide anonymity details; ARR checklist.
- Claims deliberately NOT made: accuracy gain over F1 selection; transfer to
  a model absent from B (all three models are in the multi-model B).

### 0.10 POST-REVIEW PLAN (v4.1), written 2026-10-10 — current plan

**Decision (user, 2026-10-10): the 12 Oct deadline no longer matters.** Aim
for a strong main-conference paper at a later ARR cycle (check
aclrollingreview.org for the next deadline and write it here: ________).
The current draft (paper/main.tex) is a snapshot, not the submission.

#### 0.10.1 Independent review (subagent, 2026-10-10), summary

ARR-style scores of the current draft: soundness 3, excitement 2.5, overall
2.5 (borderline Findings). After its top-3 fixes: 3-3.5. No leakage found.
- **Attribution:** the bad "else" check is blocked by the false-rejection
  BUDGET at selection on A, not by the certificate on B (single-split and
  output-level selections also exclude it). The draft credits the
  certificate; wrong.
- **M1 overclaims:** abstract says we "match" F1 on average, but IE Llama is
  -2.9 [-4.8,-1.0]; Table 1 bolds our column even where F1 is higher; the
  largest IE subgroup ("plain", n=316) loses -7.1 [-10.0,-4.5] for Llama.
- **M2 "every certificate holds" cannot fail:** gamma >= mean delta by
  construction; F1's own B bounds also hold on test. Need a like-with-like
  test (test gamma on B-structured subsamples vs U_B).
- **M3 our certificate is an average too:** a category smaller than the
  budget can be deleted with the certificate intact.
- **M4 test exposure:** seed-0 pilot results were seen before the switch to
  instance-level certification, F1 baseline, multi-model pools and the IE
  repair round. Disclose; use a fresh disjoint test draw.
- **M5 strawman-ish baselines:** IE hand-written stack lacks substring and
  capitalisation checks (entity_capitalized_in_text alone catches 26.2%;
  with no_overlap 38.8% of our 52.0%); morphology "concatenates" is unsound
  by design; GSM8K "####" is only unsound under our lenient label.
- **M6 the F1 failure is one case** (one GPT-4o check, one pool config; with
  mini-only pools F1 loses 0/77). Needs a rate over resamples.
- **M7 F1 baseline is a weak AutoPyVerifier stand-in;** add "F1 subject to
  recall >= 1-tau" to separate objective from constraint.
- minor: Bonferroni over the 3 budgets (guarantee ~85% not 95%; corrected
  bounds IE 3.89, SQL 1.91, morph 1.64, math 0.60%, all still certified);
  ablation "4.6x" uses an UNCERTIFIED row (use SQL gold-only at tau=5%:
  claims 4.84%, measures 13.38%); test draws overlap (497/555/524 unique
  inputs of 600) so cluster the bootstrap by input; gold-only certifies a
  different quantity; distill data sizes differ; guidance under-reported
  (math "internal consistency" sentence sits in TASK_SPECS for every round
  after it was added; SQL/morph specs encode lessons from split A).
- **Missing related work:** Learn-then-Test, Conformal Risk Control,
  Conformal Language Modeling (Quach et al.), conformal factuality (Mohri &
  Hashimoto), data programming (Ratner et al.). Verify before citing.

#### 0.10.2 Revised thesis

"Selecting LLM-written verifiers by agreement with labels can silently
delete whole categories of correct outputs, and a model trained on the
filtered data never learns them. Selection under group-conditional
false-rejection constraints, certified on held-out MODEL outputs (gold-only
validation is unsafe), prevents this at little cost in average accuracy."
The certificate is the honest held-out number and the deployment guarantee;
the protection comes from constrained selection. Position the statistics as
Learn-then-Test-style risk control applied to verifier synthesis; novelty is
the problem, what is certified, and the evidence, not the bound itself.

#### 0.10.3 Workstreams

**W1. Text integrity ($0; first).** Fix every M/m item above in
paper/main.tex: honest average comparison ("matches or trails"), no bolding
by column, full subgroup trade-off table, correct attribution (budget vs
certificate), disclose test exposure and all proposer guidance, Bonferroni
or fixed-sequence correction over budgets, certified ablation rows, claim
the mini-only transfer result (certified on GPT-4o-mini pools only, held for
Llama and Qwen: section 0.2), clustered bootstrap.

**W2. Method: group-conditional certified selection ($0, cached verdicts).**
- Groups: (a) the pre-registered gold-defined subgroups in
  certver/filtering.subgroups (fixed 2026-10-08, before the "else" finding);
  (b) a task-agnostic family so unknown categories are covered too, e.g.
  k-means clusters of input embeddings or of gold-output features, fixed
  before looking at results; min group size on B (e.g. >= 50 inputs).
- Selection on A: maximise catch s.t. gamma_g(A) <= tau/2 for every group g.
- Certification on B: Clopper-Pearson per group with Bonferroni (or
  Learn-then-Test fixed-sequence over budgets); report the worst-group bound.
- Theory: per-group versions of Prop. 1-2 (lost fraction in every group <=
  its bound); proof is the same, with a union bound.
- Expected: protects every group (incl. "else") with a small loss in average
  catch. This is the new method component; implement as `select_group` in
  certver/curve.py and a `--groups` option in report/subgroup_acc.

**W3. Statistics that can fail ($0).**
- Like-with-like validity: subsample test pools to B's structure (gold +
  greedy + 3 samples per model), compute test gamma (overall and per group),
  compare with U_B for EVERY verifier (hand-written, F1, budgeted,
  group-certified, dense curve). Report coverage and tightness.
- Resampling study: ~200 replicates of (bootstrap of A x random candidate
  subset) per task: rate at which F1 vs budgeted vs group-certified selection
  deletes > 50% of any group on B and test; coverage rate of U_B. Turns the
  single "else" case into a rate (answers M6).
- Cluster bootstrap by input everywhere; Bonferroni/LTT over budgets.

**W4. Stronger baselines.**
- Strong hand-written stacks: IE + substring + capitalisation (and whatever
  an expert would write in 30 min, written BEFORE seeing which synthesised
  checks win); SQL + value-exists-in-DB for quoted literals; GSM8K with the
  standard "####" evaluation (re-run the math label without the last-number
  fallback as a sensitivity check). Report marginal catch of synthesis over
  the strong stack.
- F1 subject to recall >= 1-tau ("F1-constrained") and F1 with validation /
  regularisation; check whether AutoPyVerifier code is public and run it if
  so.
- An LLM-as-judge verifier (GPT-4o-mini judging correctness) as a non-
  programmatic baseline: higher catch, no guarantee, cost.

**W5. Evaluation where verification matters (API spend).**
- Fresh, disjoint test draws for all tasks, never looked at before the final
  analysis; analysis script frozen first (pre-registration note in PLAN).
- Weaker generators (Llama-3.1-8B, Qwen2.5-7B) on SQL and GSM8K: more errors
  to catch.
- New tasks whose output constraints carry content (pick 2):
  function calling / tool arguments (e.g. BFCL: types, enums, required
  params, values grounded in the request); relation extraction (CoNLL04 or
  similar: entity-type constraints on relations); schema-rich document
  extraction (receipts/invoices: totals add up, dates valid); harder math
  (MATH / competition subsets, where the arithmetic-check idea may pay off).
- Estimated API: fresh tests ~$2/task/draw x 4 tasks x 3 draws ~ $25; weaker
  generators ~ $5-10; 2 new tasks (A, B, test, 3 models) ~ $25-35. Likely
  exceeds the remaining ~$60 of the $100 cap: **ask the user before raising
  the cap.**

**W6. Downstream, made robust (local GPU, version4/.venv_train).**
- Distillation on >= 2 tasks (IE + one new task), 3 training seeds, and
  size-matched training sets (subsample every filter's set to the smallest
  size) to remove the data-size confound; also a 1.7B student.
- Optional: RL (GRPO on Qwen3-0.6B) with the verifier as a reward gate on IE:
  does the F1 verifier's category-systematic false rejection stop the policy
  from producing that category? (Prior work says random false negatives only
  slow RL; ours are systematic per category, which is untested.)
  Needs `trl` in the venv only.

**W7. Related work and paper.** Verify and cite LtT, CRC, Quach et al.,
Mohri & Hashimoto, Ratner et al. (read each). Rewrite around the revised
thesis; move secondary tables to the appendix; compile and check 8 pages.

#### 0.10.4 Order, gates and timeline (about 4-6 weeks)

| week | work | gate |
|---|---|---|
| 1 | W1, W3 (like-with-like, resampling), W4 strong hand-written + F1-constrained | Does budgeted selection still beat F1 on deletion RATE across resamples? If not, the paper's core claim is in doubt: stop and rethink. |
| 1-2 | W2 group-conditional selection on existing data | Does it protect every group at < 2 pts average cost? This decides whether there is a method contribution. |
| 2-3 | W5 data (fresh tests, weaker generators, 2 new tasks); user approves budget first | Synthesis must beat the STRONG hand-written stack on >= 2 tasks for a "synthesis helps" claim; otherwise drop that claim and lead with the deletion/coverage finding. |
| 3-4 | W6 downstream on 2 tasks, 3 seeds, size-matched (+ optional RL) | Deletion -> student failure replicates on a second task. |
| 5 | W7 write; independent review again (same prompt as 2026-10-10); compile | Reviewer overall >= 3.5 or keep iterating. |

#### 0.10.5 Pending from before the review

- Training seeds 1-2 for certified vs F1 (logs/run_distill_seeds.sh) and
  their auto-scoring (logs/run_seeds_eval.sh -> out/distill_ie_seeds.json).
  Fold into W6 (they vary training noise only, not the filtered data).

Decision (2026-10-08): version3 is NOT submitted to the ARR October 2026
cycle. Its material is reused here, reframed from an audit (a negative,
"checks buy little" result) into a method with a guarantee. Target: the next
ARR cycle feeding ACL/NAACL main track. Confirm that cycle's exact deadline on
aclrollingreview.org and write it here: `DEADLINE = 2026-10-12 (ARR October cycle; NAACL or COLING), set by the user on 2026-10-10`.

## 1. The paper in one paragraph

(Original plan text. Superseded where section 0 differs: admission is now a certified budget at the instance level, and the "F1 breaks the floor" claim did NOT hold on accuracy; see 0.3.)

Rule-based verifiers for structured outputs (SQL, schema-constrained IE,
morphological segmentation) are written by hand and trusted as sound on faith.
version3 showed that faith is misplaced: hand-written checks leak on all three
tasks, and the sound ones that survive are weak (false acceptance 0.81-0.92).
We propose **certified verifier synthesis**. An LLM proposes many candidate
checks; each is admitted only if it rejects no correct output on a held-out
certification set, measured with a label that does not presuppose the check;
the admitted checks are conjoined, and the conjunction is re-certified on a
separate split, giving a distribution-free bound on its false-rejection rate.
The result can gate best-of-N with a no-harm floor and drop into an RLVR reward.
The headline claim to test: certified synthesised verifiers catch
substantially more wrong outputs than hand-written ones at the same certified
soundness, while F1-optimised synthesis (the closest prior work) buys its extra
catch rate by breaking soundness, and with it the floor.

## 2. Novelty position (from the 2026-10-08 search; verify every citation
## by reading the paper before it goes in the .bib)

- **AutoPyVerifier** (arXiv 2604.22937): LLM proposes verifier functions,
  selection maximises F1 on labelled data. Closest work. Differs: no soundness
  constraint, no certificate, no no-harm guarantee. This is our main baseline.
- **HardTests** (arXiv 2505.24098): synthesised tests filtered against gold
  programs. Code only, no statistical bound, no admission rule.
- **ScriptoriumWS / DataSculpt**: LLM-written labeling functions filtered by
  validation accuracy. Methodological ancestor from weak supervision.
- **Conformal LLM validity** (arXiv 2406.09714), **When to Trust the Cheap
  Check** (arXiv 2602.17633): finite-sample guarantees, but not for synthesised
  programmatic checks.
- **RLVR noise:** Rate or Fate? (2601.04411) and Delay/Plateau/Collapse
  (2605.02909) find false negatives mostly DELAY GRPO, while false positives
  are what break it. TinyV (2505.14625) and Pitfalls (2505.22203) find false
  negatives do hurt. Mixed evidence, so RL is a secondary test (E5), never the
  headline.
- Gap claimed: soundness-certified admission of synthesised checks
  (rule-of-three bound + conjunction preserving it + no-harm floor), for
  non-code structured NLP outputs. Nothing found for IE or morphology.

## 3. Contributions (target)

1. **Method.** Propose, admit, compose, re-certify: a synthesis loop whose
   output carries a stated false-rejection bound.
2. **Theory (reused from version3, now load-bearing).** Admissible labels;
   conjunction never raises false acceptance; reject-gating cannot fall below
   the base output; the full conjunction bounds every subset. New piece: the
   two-split certification, which keeps the bound valid after selecting from
   many candidates.
3. **Empirical.** On three tasks and several models: more wrong outputs caught
   at certified soundness than hand-written checks; F1-selected synthesis
   breaks soundness and the floor in measured cells.
4. **Evidence for why certification is needed (reused from version3).**
   Hand-written checks leak on all three tasks; 27% of SIGMORPHON gold
   segmentations fail their own concatenation check; a single seed falsely
   certified one cell.

## 4. Method details

**Splits, per task.** Never touch the test split until final evaluation.
- *Proposal pool:* about 50 training instances shown to the proposer LLM.
- *Admission split A:* training instances with gold, plus model outputs on
  them labelled with the admissible label (test-suite accuracy for SQL,
  field-value match for IE, gold match for morphology).
- *Certification split B:* disjoint training instances, same construction.
- *Test split:* Spider dev, CoNLL test, SIGMORPHON test, as in version3.

**Why model outputs, not just gold.** version3's lesson: a check can pass every
gold output and still reject correct model outputs that are written
differently (equivalent SQL, reordered JSON). Admission and certification use
both gold outputs and correct model outputs.

**Admission rule: certified false-rejection budget (user decision
2026-10-08).** For a budget tau, select greedily on split A: add the check
that catches the most additional incorrect outputs, as long as the
conjunction's false-rejection rate on A stays at or below tau/2. tau = 0 is
the strict zero-tolerance endpoint. Sweep tau in {0, 0.25%, 0.5%, 1%, 2%, 5%}
to get a trade-off curve (catch rate vs certified false-rejection rate);
this curve is the main figure. Implemented in `certver/curve.py`.

**Certification.** Count rejections of correct outputs by the selected
conjunction on split B (k of n). Upper bound U = 3/n if k = 0, else the 95%
one-sided Clopper-Pearson bound. Certified at tau iff U <= tau. Because B
played no part in selection, the bound holds despite selecting from hundreds
of candidates.

**What the guarantee becomes.** At delta = 0, reject-gating can never fall
below the base output (version3's floor). At a certified delta, the worst
case loss is at most p0 * delta (a correct base output rejected and replaced
by a wrong one), and the exact accuracy is version3's Thm. 1 / Cor. degrade.
Report both the closed form and the empirical gated best-of-N accuracy.

**Proposer.** (Actually used: GPT-4o and Claude Opus 5.5 with reasoning effort low; Opus writes far better, database-grounded checks.) GPT-4o and Qwen2.5-72B write checks as sandboxed Python
functions, given the task definition, the output schema and the proposal pool.
Refinement loop: rejected-correct examples are fed back to the proposer for up
to 3 rounds. Run the checks with a time limit and no network or file access.

## 5. Experiments

- **E1, synthesis vs hand-written.** False acceptance, certified
  false-rejection bound, gain at N in {1,...,32}, and ceiling. Compare against
  version3's hand-written stacks on all three tasks.
- **E2, the main baseline: F1-selected synthesis (AutoPyVerifier-style).** Same
  candidate pool, selected by F1 on split A. Prediction: lower false acceptance
  but measured false rejections above 0, with the floor violated in some cells.
  This is the result that makes the method necessary.
- **E3, other baselines.** Accuracy-filtered labeling functions; LLM-as-judge
  gate; DPC for SQL (harness in version3/code/dpc_repo); oracle upper bound.
- **E4, ablations.** No refinement loop; gold-only admission (no model outputs:
  predicts leaks, version3's lesson); single split (no re-certification:
  predicts a bound that does not hold on test); number of candidates.
- **E5, RLVR (secondary; kill if infeasible).** GRPO on Qwen3-0.6B / 1.7B
  (cached locally), text-to-SQL on Spider train. Rewards compared: execution
  match alone; execution match AND certified checks; execution match AND
  leaky checks (hand-written or F1-selected). Question asked neutrally: do
  false rejections hurt or only delay? Either answer is reportable.
- **Robustness.** 3 seeds minimum for headline cells; check whether a verifier
  synthesised with one model transfers to another model's outputs.

**Models.** GPT-4o-mini, Llama-3.1-70B, Qwen2.5-72B via OpenRouter, plus one
local model. Drop GPT-4o from generation unless budget allows (cost).

## 6. Resources and budget

**Budget cap: $100 total API spend (user-approved 2026-10-08).** No GPT-4o as
an output generator (that alone would add about $150); GPT-4o is used only as
the check proposer (a few hundred calls). Estimated ~$60-100 for the full plan.
Track spend from the OpenRouter key's `usage` field before and after every run;
the starting usage is $327.70 (2026-10-08), so the cap is reached at $427.70.

- OpenRouter: $372 left of $700 (checked 2026-10-08). version3 used about $328
  in total. **Run a pilot first (one task, one model, 100 instances) and
  measure cost before committing to the full grid.** If the projection exceeds
  about $300, cut models before cutting instances.
- **Records must store raw output text this time.** version3's records hold
  only booleans, so new checks cannot be evaluated on them; candidate pools
  must be regenerated.
- GPU: one P100 16 GB (shared, about 3.5 GB in use), with no bf16, so fp16 only.
  RL is limited to 0.6B-1.7B models with LoRA. Need to install `trl` and
  `peft`.
- Code: start from version3/code/soundver (checks, rates, records, reconcile).
  Do not modify version3 in place; copy into version4/code.

## 7. Timeline (about 8 weeks; compress if the deadline is earlier)

| Week | Work | Exit criterion |
|---|---|---|
| 1 | Copy harness; raw-text records; splits; sandboxed check runner; pilot on SQL | Pilot cost measured; budget decision made |
| 2 | Proposer + refinement loop; admission + certification; SQL end to end | One certified synthesised SQL verifier with a measured bound |
| 3 | Extend to IE and morphology; generate candidate pools for all models | All 3 tasks certified on split B |
| 4 | E1, E2 on test | **Go/no-go:** does synthesis beat hand-written false acceptance at certified soundness? |
| 5 | E3, E4; seeds | Tables reproducible from saved outputs |
| 6 | E5 RLVR (or drop) | RL result or a documented decision to cut it |
| 7 | Write the paper; reuse version3 theory and audit sections | Full draft within 8 pages |
| 8 | Internal review, verify every citation, compile, page count | Submission-ready |

## 8. Risks and kill criteria

- **Synthesis does not beat hand-written checks (E1 negative).** Possible: the
  ceiling result says false acceptance may be structurally high. Fallback:
  the paper becomes "certification is necessary", with E2's leaks and the
  floor violations as the main result, plus version3's audit. Decide at the
  week 4 go/no-go, not later.
- **Certified checks are trivial** (they restate parses/executes). Mitigation:
  report how many admitted checks are semantic rather than syntactic, with
  examples chosen by a fixed rule (first N in order).
- **Overlap with AutoPyVerifier grows** (follow-up work appears). Re-run the
  novelty search at week 4 and week 7.
- **Budget runs out.** Pilot first; local Qwen3-8B / Qwen2.5-7B as fallback
  generators.
- **RL infeasible on the P100.** Cut E5; the paper does not depend on it.

## 9. Verification discipline (carried over from version3, binding)

Every number in the paper must come from a saved output file, never from
memory or estimation. Every citation must be read in full before it is
written into the .bib; the 2026 arXiv ids above came from a web search and
are unverified.

## 10. Progress log

### 2026-10-08 (week 1, day 1)

**Built** (version4/code/certver): `data.py` (disjoint proposal/admit/certify
splits from training data, 50/1000/1000; test split reproduces version3's
200 instances exactly), `pool.py` (raw-text pools, per-call cost logging,
incremental/resumable, hard cost cap), `sandbox.py` (gold-stripped,
fail-closed, import allow-list, CPU/memory/SQL timeouts, aborts a check after
3 timeouts), `propose.py` (delimited output format, raw responses saved,
contrastive examples, configurable proposer), `admit.py` (admit / certify /
evaluate; gold outputs included as correct examples; hand-written checks go
through the same rule), `sqllabel.py`, `relabel.py`.

**Cost pilot (SQL test, 100 instances x 33 outputs, measured):** GPT-4o-mini
$42 per 1M calls, Qwen2.5-72B $77/M, Llama-3.1-70B $102/M. Full generation
grid projected at roughly $15-20, well under the $100 cap. Spent so far on
version4: about $3.0 (of which about $1.4 was wasted on Claude Opus 5.5
returning empty answers before reasoning effort was set to low).

**Finding 1: version2/3's SQL label is broken.** `test_suite_accuracy` in
version2/spider_task.py compares only on 70%-row subsamples as frozensets
(its own docstring says it must be upgraded before reporting). Measured on
our pools: 3.1-3.8% of "correct" outputs are actually wrong (e.g. empty
result vs gold's rows), and a similar number of "incorrect" ones are correct
(column order). Replaced by `certver/sqllabel.py`: original DB + distilled
copies, multiset, column-permutation tolerant (official Spider semantics).
**Version3's SQL delta/eps numbers were computed with the broken label and
are not trustworthy as published; reuse none of them in version4.**

**Finding 2: version3's `schema_valid` rejects a gold query** (correlated
subquery referencing an outer alias, sqltr-05756); `executes` inherits it.
Only found because admission now includes gold outputs.

**Finding 3 (SQL, admission on split A, 117 candidates, corrected label):**
1 synthesised check admitted (catch 0.4%); about 40 near-misses with 1-25
correct outputs rejected out of 3,774, most catching under 2% of wrong
outputs. GPT-4o as proposer mostly produces "question word implies SQL
keyword" rules (unsound). Claude Opus 5.5 produces database-grounded checks
that come much closer (e.g. literal_case_mismatch: 13 rejections, 6.3%
catch). SQL looks like the hardest task for synthesis; IE and morphology
not yet tried.

**Open decision for the user:** zero-tolerance admission vs. a certified
small false-rejection budget (see report of 2026-10-08).

**SQL trade-off curve (2026-10-08, `out/curve_sql.json`, A/B pools from
GPT-4o-mini on train, test = 100-instance pilot x 3 models, corrected label):**

| selection | checks | B false rej. (k/n) | B U95 | B catch |
|---|---|---|---|---|
| hand-written (parses, schema_valid, executes) | 3 | 5/3824 | 0.27% | 13.8% |
| tau = 0 | 4 | 2/3824 | 0.16% | 0.3% |
| tau = 0.5% | 4 | 34/3824 | 1.18% (not certified) | 16.1% |
| **tau = 1% (certified)** | 5 | 8/3824 | 0.38% | **21.3%** |
| tau = 2% (certified) | 6 | 42/3824 | 1.42% | 22.7% |

- Certification earns its keep: the tau = 0.5% selection looked fine on A
  (0.24%) but rejected 34 correct outputs on B. Only B catches this.
- The certified tau = 1% verifier = hw:executes + Opus's literal_case_mismatch
  and how_many_single_row + two GPT-4o rules. Catch on B rises from 13.8% to
  21.3% (+54% relative) at a certified false-rejection bound of 0.38%.
- Test-set gains are small and noisy at 100 instances: gated best-of-32 vs
  hand-written: Qwen2.5-72B 77.2 vs 76.2, Llama-3.1-70B 81.0 vs 81.0,
  GPT-4o-mini 69.1 vs 69.1. Catch on B (train distribution) is higher than
  on test (dev distribution): watch for train/test shift.
- The hand-written stack is itself not sound (5 false rejections on B,
  including the schema_valid gold-query bug).

### 2026-10-08 (later): first end-to-end results on all three tasks

Pools: A/B from GPT-4o-mini on train (1000 instances x 4 outputs each);
test pilots 100 instances x 33 outputs x 3 models (GPT-4o-mini,
Llama-3.1-70B, Qwen2.5-72B), seed 0. Proposers: GPT-4o and Claude Opus 5.5
(reasoning effort low). Files: out/curve_{sql,ie,morph}.json,
out/ci_{sql,ie,morph}.json. Spend on version4 so far: about $5.4.

Gated best-of-32 accuracy on test, synthesised certified verifier vs
version3's hand-written stack, paired bootstrap 95% CI over 100 instances:

| task (budget) | model | base | hand-written | synthesised | synth - hw |
|---|---|---|---|---|---|
| IE (tau 2%, U95 1.73%) | Llama-3.1-70B | 44.0 | 47.7 | 54.5 | +6.8 [+2.8, +11.5] |
| | GPT-4o-mini | 37.0 | 37.0 | 40.2 | +3.2 [+0.3, +6.9] |
| | Qwen2.5-72B | 55.0 | 56.0 | 58.6 | +2.6 [+0.0, +6.0] |
| SQL (tau 1%, U95 0.38%) | Llama-3.1-70B | 75.0 | 81.0 | 81.0 | +0.0 |
| | GPT-4o-mini | 69.0 | 69.1 | 69.1 | +0.0 |
| | Qwen2.5-72B | 75.0 | 76.2 | 77.2 | +1.0 [+0.0, +3.0] |
| morph (tau 0.5%, U95 0.12%) | Llama-3.1-70B | 34.0 | 30.0 | 34.0 | +4.0 [+0.0, +9.0] |
| | GPT-4o-mini | 33.0 | 31.0 | 34.0 | +3.0 [+0.0, +7.0] |
| | Qwen2.5-72B | 38.0 | 35.0 | 39.0 | +4.0 [+1.0, +8.0] |

Reading:
- IE is the positive result: catch rate on B 6.7% -> 56%; test eps drops
  from 0.70-0.95 to 0.41-0.59; accuracy gains transfer to two models whose
  outputs were never used for selection.
- SQL: certified verifier ties the hand-written stack on test (gains on B
  did not transfer to the dev split at this sample size).
- Morphology: synthesis has nothing to catch, but version3's hand-written
  stack (with unsound `concatenates`) LOWERS accuracy below base by 2-4 pts;
  certification refuses that check, so "synth - hw" is positive only because
  the baseline is harmful.
- All of this is 1 seed x 100 test instances. Must scale to 200 instances
  x 3 seeds before any claim (budget allows: about $15-20).

### 2026-10-08 (later): F1 baseline and concentration of false rejections

**F1-selected synthesis (AutoPyVerifier-style, `selections["f1_baseline"]`
in certver/curve.py)**, same candidate pool, pilot test (100 x 3 models):
- SQL: F1 baseline catches more on B (32.7% vs 21.3%) but rejects 107/3824
  correct outputs (U95 3.3%) vs 8/3824 for certified tau=1%. On test its
  delta is 2.0-2.4% for two models; certified bound 0.38% held on test for
  all three models (0.04-0.31%). Gated best-of-32 accuracy: F1 equal or up
  to +1 pt vs certified. **No accuracy advantage for certification.**
- IE: F1 baseline picks nearly the same verifier; identical test accuracy;
  slightly fewer false rejections than our tau=2% selection.
- Instance-level harm (base correct -> gated wrong): < 1 instance per 100
  for every verifier. Best-of-N averages hide false rejections.

**Concentration (split B, instances where ALL correct outputs incl. gold
are rejected, i.e. made unanswerable under gating):**
- SQL: hand-written 0, certified tau=1% 3, F1 baseline 28 (one HAVING check
  accounts for 72 of its false rejections).
- IE: hand-written 0, certified tau=2% 17, F1 baseline 10 (both driven by
  no_number_only_token_edges, e.g. "Windows 95").

**Strategic reading (go/no-go relevant):** synthesis beats hand-written
checks on IE by a lot, but an uncertified F1 selection gets the same
accuracy. Certification's distinct value is (a) a bound that holds on new
models and splits, (b) fewer wiped-out question types on SQL. Candidate fix:
certify instance-level coverage loss (fraction of instances with every
correct output rejected), not just output-level delta.

### 2026-10-08 (later): instance-level certification + filtering experiment

**Method change (user-approved option 1).** Output-level Clopper-Pearson on
delta treats outputs as independent, but outputs of one instance are
correlated (rejections cluster), so that bound is optimistic. New selection
`itau=` in certver/curve.py constrains and certifies gamma = fraction of
INSTANCES on which the verifier rejects any correct output (binomial over
independent instances, so the bound is valid). gamma upper-bounds the
instance-averaged false-rejection rate and the fraction of instances wiped
out. Caveat: gamma depends on outputs per instance (4 on A/B, 33 on test),
so test gamma is not comparable to B gamma; compare test's
instance-averaged delta against the bound instead.

SQL: certified itau=0.02 verifier gamma_B 5/1000 (U95 1.05%) vs F1 baseline
44/1000 (U95 5.6%). IE: itau selections coincide with the F1 baseline.

**Filtering experiment (`certver/filtering.py`, pilot test pools, 3 models;
keep accepted outputs as training data; subgroups from gold only):**

| task | selection | precision | recall | instances losing all correct data |
|---|---|---|---|---|
| SQL | hand-written | 0.762 | 0.998 | 0/255 |
| | certified (itau 2%) | 0.764 | 0.998 | 0/255 |
| | F1 baseline | 0.794 | 0.985 | 3/255 (order_by subgroup: 3/55) |
| IE | hand-written | 0.459 | 1.000 | 0/174 |
| | certified (tau 2%) | 0.588 | 0.994 | 2/174 |
| | F1 baseline | 0.585 | 0.994 | 2/174 |
| morph | hand-written (v3 stack) | 0.362 | 0.817 | 37/152; canonical-differs-from-surface subgroup: 37/40 lost |
| | certified (itau 2%) | 0.350 | 1.000 | 0/152 |
| | F1 baseline | 0.350 | 1.000 | 0/152 |

Honest reading: certification separates sharply from hand-written checks
(morphology: a whole subgroup deleted) and from F1 selection only on SQL
(small). On IE the F1 objective happens to be safe; certification is how
you would know that, not something that beats it.

Full test grid (200 instances x seeds 0-2 x 3 models x 3 tasks) generating
detached in data/test (logs/test_*.log); about 3-4 h. Re-run every analysis
on it before any claim.

### 2026-10-09: full test grid finished; final reports; handover written

Full test grid complete (200 instances x seeds 0-2 x 3 models x 3 tasks,
0 skipped). `python -m certver.report` run for all three tasks; results and
reading moved to section 0.2-0.3. Morphology's full report: certified
filter loses 0/933 instances vs hand-written 151/933 (canonical subgroup
151/154). Spend to date about $15.42. Section 0 written as a handover for a
new session/account.

### 2026-10-10: ablations (E4)

New module `certver/ablate.py`; results in section 0.2b. A first run scored
the gold-only variant against a bound computed on ALL of B's correct outputs,
which is not what a gold-only procedure would claim; fixed so gold-only's
claimed bound comes from B's gold rows only. With the fix, SQL gold-only
certification claims 1.8% and measures 12.1% on test. No API spend.

### 2026-10-10: multi-model A/B pools (IN PROGRESS when written)

Adding Llama-3.1-70B and Qwen2.5-72B outputs to the admit and certify pools
(1000 instances x 4 outputs each, all 3 tasks; estimated about $4, not the
$2 first quoted). Launched detached; logs/pool_{task}_{admit,certify}_multi.log.
The GPT-4o-mini-only pools that every result above used are preserved in
data/pools_mini_only/ (data/pools/ now gets the extra models appended).
If interrupted, re-run the same command (resumable):
  python3 -m certver.pool --task <t> --split <admit|certify> \
    --models meta-llama/llama-3.1-70b-instruct qwen/qwen-2.5-72b-instruct \
    --candidates 3 --max-cost 2.5 --out-dir data/pools
Then: `certver.curve ... --out out/curve_{t}_inst_multi.json` (taus 0.01 0.02
0.05) and `certver.report --task t --curve out/curve_{t}_inst_multi.json
--out out/report_{t}_multi.json`, and compare with the mini-only results.
Caution: any other script that reads data/pools/*.jsonl now sees 3 models.
Status 2026-10-10 15:00 (superseded: all done, see 0.2c): morph multi-model pools done and analysed
(out/curve_morph_inst_multi.json, out/report_morph_multi.json): unchanged
from mini-only (certified itau=2%, 7 checks, B gamma 8/1000, U95 1.44%;
test results identical; filter loses 0/933 vs hand-written 151/933).
IE and SQL certify pools still generating; `logs/run_multi_analysis.sh`
(detached) waits for them, then writes out/curve_{ie,sql}_inst_multi.json
and out/report_{ie,sql}_multi.json (logs/report_{ie,sql}_multi.log; "ALLDONE"
appended to logs/report_sql_multi.log when finished). Spend ~$18.60.

### 2026-10-10 (later): multi-model pools finished and analysed

All six multi-model pool runs finished (about $4.05 logged); IE and SQL
curves and reports written by logs/run_multi_analysis.sh. Results and
reading in section 0.2c. Spend to date about $19.47.

### 2026-10-10 (later): paper drafted

User confirmed the framing (0.4) and the deadline (2026-10-12, NAACL or
COLING via ARR). Wrote version4/paper/ (see 0.9). Citation verification by a
subagent against arXiv. While drafting, self-check caught and fixed: a claim
that certificates held "for two models never used to select the checks"
(true only for the mini-only pools, false for the multi-model headline
setting), an unmeasured causal claim about why F1 keeps the "else" check
(replaced by its measured catch rate on A, 32.7%), and "stacks used in prior
work" (replaced by "standard well-formedness stacks").

### 2026-10-10 (evening): user asked for all three strengthening experiments

User request: (1) show coverage loss hurts a downstream model; (2) add a task
where synthesis helps a lot; (3) beat agreement-based selection on something
reviewers care about. Deadline still 2026-10-12.

(3) DONE (free): `certver/subgroup_acc.py` -> out/subgroup_ie.json. Gated
best-of-32 accuracy on the IE has_else_type subgroup (n=109 units/model),
certified minus F1: Llama +9.0 [+4.0,+14.5], mini +2.9 [+0.1,+6.5], Qwen
+6.3 [+2.5,+11.0]. F1 pushes that subgroup BELOW base (Llama 16.5 -> 10.6;
certified 19.5). Worst-group accuracy win over agreement-based selection.
Overall accuracy still favours F1 slightly.

(1) IN PROGRESS: downstream SFT.
- New split `distill` (2000 fresh training inputs, disjoint from
  proposal/admit/certify) in certver/data.py. IE distill pool (3 models x
  (1+3) outputs) generating -> data/distill/ (logs/pool_ie_distill.log).
- `certver/distill_sets.py` builds sft_ie_{none,handwritten,f1_baseline,
  certified,oracle}.jsonl + eval_ie_prompts.jsonl (unique test inputs).
- `code/train_sft.py` (runs in version4/.venv_train): LoRA r=16 on
  Qwen3-0.6B, 1 epoch, then greedy decode of eval prompts.
- To do: score generations (field-value match; has_else_type subgroup;
  "else" field recall) with a small scoring module.
- **Environment note:** the global user env has transformers 5.x, which is
  incompatible with torch 2.5.1. A `pip install --user peft` I ran upgraded
  transformers 5.16.1->5.19.0 and huggingface_hub ->2.2.0 (breaking
  datasets); I reverted to transformers 5.16.1 and huggingface_hub 1.33.0
  (exact previous hub version unknown, was <2.0) and uninstalled peft.
  Training uses an isolated venv: version4/.venv_train (pip bootstrapped via
  get-pip.py because ensurepip is missing; torch 2.5.1+cu121,
  transformers 4.53.3, peft 0.15.2; Qwen3-0.6B downloaded). Log:
  code/logs/venv_train.log. NEVER pip-install into the user env again.

(2) IN PROGRESS: new task "math" = GSM8K (openai/gsm8k, downloaded to
1-MICCAI/math_data/{train,test}.json). Wired through soundver/generate.py
(loader, prompt '#### <number>', hand-written checks has_answer_line +
answer_is_number, label = final answer equals gold numerically, with a
last-number fallback so the label does not presuppose the checks),
records.CHECKS, certver data/pool/admit/sandbox (helper final_answer)/
propose/filtering (subgroups by #steps in gold, answer >= 1000). Pools
launched detached: proposal (mini), admit + certify (3 models), test seeds
0-2 (3 models, 32 samples) -> logs/pool_math_*.log, logs/test_math_seed*.log.
Cost about $0.00017/call, about $16 projected. Next: Opus + GPT-4o proposals
for math, curve (taus 0.01 0.02 0.05), report, subgroup_acc, add to paper.

Drivers launched 2026-10-10 evening (detached, survive session end):
- code/logs/run_distill.sh: waits for the IE distill pool, builds sft sets,
  trains 5 students (certified+f1 first, then handwritten+oracle, then none),
  scores -> out/distill_ie.json ("ALLDONE" in logs/eval_distill_ie.log).
- code/logs/run_math.sh: waits for math A/B -> curve (inst + dense;
  "CURVEDONE" in logs/curve_math.log); waits for 3 test seeds -> report,
  subgroup_acc, ablate ("ALLDONE" in logs/report_math.log).
Math proposer note: GPT-4o/Opus round 0 and Opus round 1 (with contrastive
examples) produced answer-level checks (integer, non-negative, bounded,
final answer appears in reasoning) but NOT step-arithmetic verification.
One sentence of task guidance was added for round 1 ("checks may test the
internal consistency of the reasoning"); report it in the paper.

### 2026-10-10 18:00: distill training incidents (fixed)

- Training sets built (code/logs/distill_sets_ie.log): from 2000 fresh
  inputs, correct examples with an "else" entity kept: none 184, hand-written
  184, certified 175, **F1-selected 20**, oracle 184. Precision of kept data:
  none 0.206, hw 0.252, F1 0.468, certified 0.411, oracle 1.000.
- First training attempt (2 students in parallel): 3 of 5 runs hit CUDA OOM
  on the shared P100 (other users hold ~3.5 GB). The fp16 "none" run went
  to NaN loss at step ~400 and emitted "!!!!" (fp16 overflow; Qwen3 is a
  bf16 model and the P100 has no bf16). Outputs moved to
  data/distill/failed_parallel_run/ (do not use).
- Fix: train_sft.py now defaults to fp32 (--fp16 opt-in) and aborts on a
  non-finite loss; logs/run_distill2.sh trains the 5 students one at a time
  (batch 4 x accum 4 = same effective batch 16) then scores ->
  out/distill_ie.json ("ALLDONE" in logs/eval_distill_ie.log).
- Self-inflicted: twice a `pgrep/pkill -f <pattern>` matched my own shell
  (pattern in the command line) and killed it. Kill by numeric PID only.

### 2026-10-10 21:15: results of the three strengthening experiments

**(1) Downstream training, IE (out/distill_ie.json; Qwen3-0.6B LoRA, fp32,
1 epoch, training seed 0; test = 555 unique IE test inputs):**
| training data filter | examples | precision | test acc | has_else acc (n=102) | "else" P/R |
|---|---|---|---|---|---|
| none | 7038 | 0.206 | 33.5 | 9.8 | 0.106/0.254 |
| hand-written | 5709 | 0.252 | 39.3 | 11.8 | 0.120/0.286 |
| F1-selected | 2705 | 0.468 | 49.5 | **4.9** | 0.090/**0.056** |
| **certified** | 3448 | 0.411 | 48.8 | **17.6** | 0.202/0.310 |
| oracle (labels) | 1447 | 1.000 | 63.6 | 25.5 | 0.465/0.365 |
Certified minus F1: overall -0.7 [-3.2,+1.8] (tie); has_else **+12.7
[+6.9,+19.6]**. Certified minus hand-written overall +9.5 [+6.5,+12.6].
The F1 filter kept 20 correct else-examples vs 175 certified (184 exist).
Extra training seeds 1-2 for certified and F1 launched
(logs/run_distill_seeds.sh -> data/distill/seeds/).

**(3) Worst-group best-of-32 (out/subgroup_ie.json):** certified beats F1 on
the IE has_else subgroup for all three models (see earlier entry).

**(2) GSM8K: NEGATIVE for "synthesis helps a lot".** Base accuracy is
91-95% for all three models, so there is little to catch. Certified
(itau=1%, 7 checks, B gamma 1/1000, U95 0.47%) ties F1 selection exactly
and is 1-1.7 pts BELOW the hand-written stack for GPT-4o-mini/Qwen. The
hand-written check "has a '####' line" is badly unsound (rejects a correct
output on 455/1000 B inputs; test inst-avg delta up to 21.9% for Llama)
but correlates with wrong answers, so it raises best-of-N accuracy while,
as a filter, discarding 8.5% of correct data (recall 0.915). Report math
honestly as the case where synthesis does not help (saturated models);
a harder dataset (e.g. MATH) would be needed for a positive result, and
there is no time before 2026-10-12.

### 2026-10-10 21:15: paper updated with the three experiments

paper/main.tex now has: GSM8K as a 4th task in every table and the figure
(reported as a null result), a worst-group accuracy paragraph, a new
subsection + Table "Students trained on filtered data" (sec:distill), new
abstract/contributions/limitations. New citations (classic_refs.bib):
cobbe2021gsm8k, hu2022lora. make_numbers.py regenerates everything (526
macros). Body about 3,750 words + 5 tables + 1 figure: PAGE LIMIT AT RISK,
must compile and check. Pending: training seeds 1-2 for certified and F1
(logs/run_distill_seeds.sh), auto-scored by logs/run_seeds_eval.sh ->
out/distill_ie_seeds.json; then re-run make_numbers.py (it emits
dsAccMean*/dsElseAccMean*/dsElseRecMean* macros when that file exists) and add
one sentence with the 3-seed means to sec:distill.

### 2026-10-10 late: distill seeds done; W1-W4 started

- 3 training seeds (out/distill_ie_seeds.json): certified vs F1, overall acc
  48.0+-1.5 vs 50.4+-1.0; has_else acc 17.6+-0.0 vs 5.6+-0.6; misc recall
  0.310+-0.000 vs 0.085+-0.026. The identical certified has_else numbers
  across seeds were checked: different files, different correct sets, same
  counts by coincidence (39 TP, 18 correct).
- User approved the full v4.1 plan (section 0.10) INCLUDING the optional RL
  experiment (no API cost; ~2-3 days of P100 time).
- data/test_bstruct/: test pools restructured like split B (per input:
  greedy + 3 samples per model; gold added by load_examples), for the
  like-with-like validity check (W3).

### 2026-10-10 late: STOPPED by the user

User asked to stop all work and record everything. State recorded in
section 0.0 (top of this file). No processes left running.

### 2026-10-11: v4.1 plan RESUMED (user: "do all that it planned, also optional RL")

Running (detached) at start:
- Fresh, never-seen test draws (split "fresh" in certver/data.py: test-set
  instances not in draws 0-2; 300 per task) x 3 main models x 32 samples:
  data/fresh/, logs/fresh_{ie,sql,morph,math}.log.
- Weaker generators (Llama-3.1-8B, Qwen2.5-7B) on SQL and math: A/B pools
  in data/pools_weak/, fresh test in data/fresh_weak/, logs/weak_*.log.
Written:
- out/candidates_strong/{ie,morph}.jsonl: expert hand-written checks added
  POST HOC for the strong baseline (IE: entities are substrings; entity
  occurs capitalised somewhere; morph: segments use the word's letters).
  Disclose that they were written after seeing results.
- certver/robust.py: groups = pre-registered gold subgroups + k=8 char-TF-IDF
  k-means clusters of inputs (fit on A); selectors hw / hw_sound / strong_hw
  / f1 / f1_constrained / budgeted / group (all at tau in {1,2,5}%);
  certification with Bonferroni over budgets (and groups); like-with-like
  test gamma on data/test_bstruct vs U_B; resampling study (bootstrap A x
  70% candidates) -> deletion rate, worst-group wiped, coverage.

### 2026-10-11 (cont.): RL running, two new tasks added

**RL (W6 optional), running detached: code/logs/run_rl.sh.**
- trl 0.19.1 installed into .venv_train ONLY (it upgraded the venv's
  transformers to 5.x; re-pinned transformers 4.53.3). User env untouched.
- TRL's GRPOTrainer produced garbage samples (its generation path; plain HF
  sampling is fine in every mode, checked), so code/train_grpo.py implements
  its own on-policy GRPO: 8 prompts x 8 samples per step (T=1.0, KV cache,
  eval mode), group-normalised advantages, one policy-gradient update per
  batch on completion tokens, LoRA r=16, fp32, lr 5e-5, no KL. ~15 s/step.
- Reward = IE label correct AND verifier accepts. Conditions: label,
  certified, f1, handwritten; seeds 0,1; 300 steps; logs per step (reward,
  rate of outputs with a non-empty "else", correct-but-rejected rate) in
  code/data/rl/log_ie_{v}_s{seed}.jsonl; test generations
  code/data/rl/gen_ie_{v}_s{seed}.jsonl; scored to out/rl_ie.json.
- Base Qwen3-0.6B (data/rl/gen_ie_base.jsonl): IE acc 15.5%, has_else 2.9%,
  else P/R 0.023/0.111 (it dumps junk into "else").

**New tasks (W5): "fewnerd" (Few-NERD supervised, 8 coarse types, slot
filling like IE; data 1-MICCAI/fewnerd_data/) and "fc" (Glaive
function-calling v2, first user turn whose first assistant turn is a call;
60,731 usable; deterministic split idx%10==0 -> test; data 1-MICCAI/fc_data/).**
Wired through soundver/generate.py (loaders, prompts, labels, hand-written
checks: fewnerd = IE stack over 8 fields; fc = parses, call_shape,
name_valid, required_present, types_valid, no_unknown_params), records,
certver data/pool/admit/sandbox (helpers parse_json / parse_call)/propose/
filtering (fewnerd: has_<type>; fc: #args, bool/numeric/structured arg,
enum param, multi-function choice)/eval_distill. Smoke: fc GPT-4o-mini 9/9
correct (possible saturation, like GSM8K), $0.00004/call; fewnerd 4/9.
Launched: proposal (mini) + admit/certify (3 models) pools for both.
Still to launch: test draws 0-2 for both (no prior exposure -> all fresh),
fewnerd distill pool (downstream replication).
Spend so far ~$41.84.
- Proposals for new tasks: fc round 0 Opus (25, grounding checks: enum
  membership, emails/URLs/long digit strings copied from the request, etc.)
  and GPT-4o (20); fewnerd round 0 Opus (25) and GPT-4o (48, recovered from
  saved raw responses after fixing the parser to accept "### CHECK_name").
- logs/run_v41_data.sh (detached): when fresh draws for ie/sql/morph finish,
  launches test draws 0-2 for fewnerd and fc (3 models) and the fewnerd
  distill pool; writes logs/run_v41_data.done.
- RL early signal (f1 reward, seed 0): rate of outputs with a non-empty
  "else" field 0.077 in steps 1-10 -> ~0.000 by steps 11-60. NOT yet
  conclusive (base model mostly puts junk in "else"; compare with label and
  certified runs and with test has_else accuracy / else recall).
- robust.py morph smoke test (5 replicates) still computing verdicts after
  36 min (CPU contention with ~16 pool processes).
- **Sandbox fix (2026-10-11):** robust.py hung because the sandbox's 2 GB
  RLIMIT_AS (virtual memory) plus forkserver preloading sklearn/scipy made
  workers fail to start their result-queue thread ("can't start new thread"),
  and the parent then waited out a wall timeout proportional to pool size
  (hours). Fixed: RLIMIT_AS 16 GB; run_check polls every 5 s and returns
  "worker died" as soon as the worker exits. Sandbox self-test still passes.
- **Design change: two-level certificate.** With B = 1000 inputs, groups of
  50-100 inputs and Bonferroni over 3 budgets x ~11 groups, a per-group bound
  is >= ~12% even at zero errors, so per-group certification at 1-5% is
  impossible. Group certificate is therefore: overall gamma <= tau AND every
  group's gamma <= TAU_G = 20% (catches category deletion like F1's 83%).
  Selection on A still constrains every group at tau/2.
- morph smoke result: like-with-like CAN fail — hand-written morph stack
  test gamma 32.0% > its B bound 31.35%.
- logs/run_robust.sh (detached): robust for ie, sql, math, morph with 200
  replicates -> out/robust_{task}.json, logs/robust_{task}.log.

### 2026-10-11 late: results, a credit outage, RL redesign

**OpenRouter ACCOUNT out of credit (user action needed).** /api/v1/credits:
total_credits $13,252.87, total_usage $13,253.10 (the account is shared with
other projects; our key used $382.85 of its own $700 limit; version4 total
$53.05). Every call since then returns 402 Payment Required. Affected and
INCOMPLETE: test draws 0-2 for fewnerd and fc (all 600 instances per draw
skipped), fewnerd distill pool (failed from ~1720/2000). Pools are
resumable: after a top-up, re-run the same commands (logs/run_v41_data.sh
lines) and only missing instances are generated. Done before the outage:
fresh draws (ie, sql, morph, math), weak generators (sql, math), fewnerd and
fc proposal/admit/certify pools.

**robust.py results (out/robust_{ie,sql,math,morph}.json, 200 replicates):**
- IE resampling: F1 selection deletes >=50% of some group in 69.0% of
  replicates (worst-group wiped mean 57.3%); F1-constrained, budgeted and
  group-constrained: 0.0%. Confirms the reviewer: the budget CONSTRAINT is
  what protects (F1 + constraint is also safe).
- Like-with-like CAN fail: F1 IE test gamma 21.5% > its U_B 20.53%;
  hand-written IE 1.00% > 0.93%, hand-written SQL 1.00% > 0.77%,
  hand-written math 57.5% > 48.9%, hand-written morph 32.0% > 31.35%.
  All budgeted/group/F1-constrained certificates hold on IE, math, morph.
- **SQL coverage problem:** over resamples, test gamma <= U_B in only
  73% (budgeted) / 77% (F1-constrained) of replicates, below 95%: Spider
  dev uses databases unseen in train (distribution shift). Report as a
  limitation of the distributional guarantee.
- Costs: group-constrained selection IE catch 46.4% vs budgeted 51.7% (tau
  2%); on SQL it removes almost all catch (0.9%). Strong hand-written IE
  catches 40.7% on B (synthesis adds ~11 pts of catch over it, not ~38).

**RL design 1 (from the base model): uninformative, archived in
data/rl/design1_from_base/.** label, certified and f1 rewards ALL drove
"else" output to 0 (has_else acc 0.0, else recall 0 for all; overall acc
15.5 -> ~45-46). The base model almost never produces CORRECT else entities,
so any reward removes the field; certified and f1 runs were identical
(neither verifier ever rejected a correct output). Stopped after 3 runs.

**RL design 2, running: logs/run_rl2.sh.** Start from the label-filtered
(oracle) SFT student (adapter saved to data/rl/sft_oracle_adapter; it
already has else recall ~0.37), then GRPO 200 steps, lr 2e-5, rewards
label / certified / f1, seeds 0-1 -> out/rl2_ie.json. train_sft.py gained
--save-adapter, train_grpo.py --init-adapter (merge adapter, new LoRA).

### 2026-10-11 late: NO MORE API MONEY (user: "there is no money, act accordingly")

Decision: no further OpenRouter spending. Final version4 API spend ~$53.05.
Everything below uses data already generated + the local P100.
Usable data inventory:
- fresh draws: ie, morph complete (3 models x 300); sql complete except
  Qwen 272/300; math only GPT-4o-mini 300 (+ Llama 38). 
- weak generators: sql A/B/fresh complete (Llama-8B, Qwen-7B); math A/B
  complete, fresh only Llama-8B 245.
- fewnerd, fc: A/B complete (3 models); NO test draws, NO fewnerd distill pool.
Local models: only Qwen3-0.6B and Qwen3-1.7B are cached.
Running (detached):
- logs/run_fresh_reports.sh: certver.report (now takes --pools) on the
  fresh draws for ie/sql/morph/math with the frozen multi-model selections
  -> out/report_{t}_fresh.json; weak-model transfer for sql/math ->
  out/report_{t}_fresh_weak.json.
- logs/run_newtasks.sh: fewnerd/fc curve (dense + inst_multi) and robust
  (B-only; robust.py now skips test analyses when no test pools exist).
- logs/run_rl2.sh: RL design 2 (GPU).
- logs/run_fewnerd_distill.sh: after RL2 and the fewnerd curve, builds
  Few-NERD SFT sets from the CERTIFICATION split B outputs (B never selected
  checks; disclose), trains 5 students, evaluates on Few-NERD test items
  (generated locally) -> out/distill_fewnerd.json.
Dropped for lack of money: new-task test draws with API models; Few-NERD
distill pool. Optional later (GPU only): local Qwen3-1.7B test draws for
fewnerd/fc as a transfer test to a model absent from A/B.

### 2026-10-12 00:30: fresh draws, weak-model transfer, new tasks

**Fresh, untouched draws (out/report_{t}_fresh.json; frozen selections):**
replicate every earlier finding.
- IE cert-hw: +6.2 [+3.8,+8.9] Llama, +5.4 [+3.0,+8.0] mini, +3.6
  [+1.7,+5.7] Qwen; cert-F1 -2.5 / -0.3 / +0.6. Filter: F1 loses 42/516
  inputs incl. has_else_type 37/44 (84%); certified 6/516 (has_else 1/44).
- morph: hand-written filter loses canonical_differs_from_surface 80/80;
  certified 0/452.
- sql, math: ties (math fresh: GPT-4o-mini 300 + Llama 38 only).
**Weak-model transfer (fresh_weak; verifiers selected on 70B-class pools):**
- SQL: certified inst-avg delta 0.71% (Llama-8B), 0.49% (Qwen-7B) <= bound
  1.69%; F1 1.81% / 1.51% (above). Accuracy ties.
- math (Llama-8B, 245): hand-written "####" filter keeps only 38% of
  correct outputs (inst-avg delta 61.9%); certified keeps 100%.

**New tasks (A/B only; robust_{fewnerd,fc}.json):**
- fewnerd: catch on B hw 14.5% -> certified/budgeted ~27% (about 2x) at
  U 1.4-2.3%; F1 does NOT delete any category here (deletion rate 0).
- fc: initially the hand-written schema stack looked unsound (296/1000)
  because the LABEL treated numeric strings as numbers (1,143 "correct"
  outputs passed numbers as strings). Label made type-strict
  (soundver.generate._fc_norm; old label kept as correct_lenient; A/B
  accuracy 0.86 -> 0.755). With the strict label: hand-written stack is
  ~sound (4/1000, U 1.08%) and catches 70.2%; certified 71.7% (tau 2%) to
  77.2% (tau 5%); F1 76.8%; no deletion. Modest gain. Round-0 fc
  candidates were proposed under the lenient label wording (disclose).
"coverage 0.000" in robust logs for fewnerd/fc means no test pools (N/A).

### 2026-10-12 01:10: RL design 2, first run (preview; controls pending)
Start = label-filtered (oracle) SFT student: acc 63.6, has_else acc 25.5,
else P/R 0.465/0.365. After 200 GRPO steps with the F1-gated reward (seed
0): acc 63.6 (unchanged), has_else acc 9.8, else P/R 0.773/0.135; training
"else" output rate 0.119 -> 0.052, correct-but-rejected 2-3% of samples.
Predicted effect, but conclusive only against the label-only and certified
runs (running; logs/rl2_ie_*.log; final scores -> out/rl2_ie.json).

### 2026-10-12 02:35: RL design 2, seed 0, certified vs F1 (label control finishing)
| start / reward | acc | has_else acc | else P/R | train "else" rate | correct-rejected |
|---|---|---|---|---|---|
| SFT init | 63.6 | 25.5 | 0.465/0.365 | | |
| certified | 65.0 | 18.6 | 0.690/0.317 | 0.17 -> 0.15 (stable) | 0.2-0.6% |
| F1 | 63.6 | 9.8 | 0.773/0.135 | 0.12 -> 0.05 | 1.6-3.3% |
The F1 verifier's category-systematic false rejections make the policy
unlearn the category while average accuracy is unchanged. Pending: label-
only control (seed 0) and seed 1 for all three (logs/run_rl2.sh).

### 2026-10-12 04:25: RL design 2, control and second F1 seed
| reward | acc | has_else acc | else recall | train "else" rate (quartiles) |
|---|---|---|---|---|
| SFT init | 63.6 | 25.5 | 0.365 | |
| label s0 | 64.0 | 26.5 | 0.421 | .20 .11 .13 .14 |
| certified s0 | 65.0 | 18.6 | 0.317 | .17 .19 .13 .15 |
| F1 s0 | 63.6 | 9.8 | 0.135 | .12 .06 .06 .05 |
| F1 s1 | 62.9 | 2.9 | 0.087 | .10 .05 .01 .02 |
Label-only RL keeps/improves the category (no generic drift); the F1-gated
reward destroys it in both seeds at unchanged overall accuracy; certified
mostly preserves it (0.317 vs 0.421 label; not identical, say so).
Pending: certified s1, label s1 -> out/rl2_ie.json.

### 2026-10-12 11:30: ALL v4.1 EXPERIMENTS FINISHED (no API since the outage)

**RL design 2 (out/rl2_ie.json), start = oracle-SFT student:**
| reward | acc s0/s1 | has_else acc s0/s1 | else recall s0/s1 |
|---|---|---|---|
| SFT init | 63.6 | 25.5 | 0.365 |
| label | 64.0 / 67.9 | 26.5 / 35.3 | 0.421 / 0.548 |
| certified | 65.0 / 64.9 | 18.6 / 26.5 | 0.317 / 0.437 |
| F1 | 63.6 / 62.9 | 9.8 / 2.9 | 0.135 / 0.087 |
F1-gated RL erases the category in both seeds at flat accuracy; label-only
RL improves it; certified keeps it near/above the start (seed 1 above,
seed 0 somewhat below). Design 1 (from the base model) archived as
uninformative.

**Few-NERD downstream (out/distill_fewnerd.json; training data = B
outputs):** acc certified 31.4, F1 29.9, hand-written 28.7, none 28.5,
oracle 25.0 (only 662 examples). certified - none +2.9 [+0.3,+5.4],
- hw +2.7 [+0.2,+5.2], - F1 +1.5 [-0.7,+3.7] (n.s.), - oracle +6.4
[+3.2,+9.8]. No category deletion on Few-NERD (consistent with robust:
F1 deletion rate 0 there). Per-type recall similar across filters.

**Workstream status:** W2 group-conditional selection DONE (robust.py;
two-level certificate). W3 like-with-like + resampling DONE. W4 strong
hand-written (IE, morph) + F1-constrained DONE; real AutoPyVerifier code
NOT run (not checked whether public). W5 DONE within the money available
(fresh draws, weak generators, fewnerd + fc on A/B; fewnerd/fc API test
draws dropped). W6 DONE (IE distill 3 seeds, Few-NERD distill, RL design
2 with 2 seeds; size-matched distill and 1.7B student NOT done). W1/W7
(text fixes, related work, rewrite) NOT STARTED: next step.

### 2026-10-12: remaining items, one by one (user request)

**1. AutoPyVerifier baseline.** Code is public: github.com/megagonlabs/
AutoPyVerifier (cloned to a temp dir; not vendored). Its pipeline needs LLM
calls (propose/critique/refine DAG search) -> cannot run without credit.
Its SELECTION objective is reproduced exactly on our candidate pool
(certver.curve.select_apv / _apv_stats): macro-F1 over accept/reject;
feasible iff Hoeffding LCBs (delta 0.05) of P(correct|accept) and
P(incorrect|reject) are >= 0.5 (their beta_pp = beta_np = 0.5); greedy
forward selection, highest score then smallest size (their final rule).
Disclose: their LLM refinement loop is not reproduced. Added to curve
(selection "apv_baseline"), report (cert_minus_apv), robust (rows +
resampling). logs/run_apv.sh reruns curve (6 tasks), reports (fresh +
test grid, 4 tasks), robust (6 tasks); writes logs/run_apv.done.

**2. W6 remainder.** logs/run_distill_v41.sh: size-matched IE distillation
(certified set subsampled to the F1 set size 2,705; 3 subsamples/seeds)
and a Qwen3-1.7B student (certified vs F1; batch 2 x accum 8) ->
out/distill_ie_matched.json, out/distill_ie_1p7b.json; writes
logs/run_distill_v41.done.

**3. Paper rewrite (W1/W7):** next.
**AutoPyVerifier-objective results (curve_*_inst_multi.json, apv_baseline):**
- IE: same as F1 (13 checks incl. the "else" check; B gamma 179/1000,
  U95 20.0%); fresh test acc 54.2/42.0/52.4 (= F1), inst-avg delta
  11.9% / 7.3% / 5.1% vs certified 0.6-1.6%.
- SQL: 16 checks, B gamma 152/1000 (U95 17.2%), catch 38.3%: much less
  sound than F1.
- morph, fewnerd: selects 0 checks (their Hoeffding feasibility on
  P(incorrect|reject) cannot be met when checks reject few outputs).
- math: 9 checks, gamma 15/1000; fc: identical to F1.

### 2026-10-12 11:50: paper v4.1 rewrite (item 3) done in draft; item 2 training
**Paper.** `paper/main.tex` rewritten for v4.1 ("When Verifiers Delete
Categories: Constrained, Certified Selection of LLM-Written Checks"). The old
draft is kept as `paper/main_v4.0.tex` + `paper/make_numbers_v4.0.py`.
`paper/make_numbers.py` (v4.1) writes gen/tab_safety, tab_fresh, tab_down,
tab_validity, tab_ablate, fig_tradeoff, numbers.tex (726 macros); run it
from version4/paper after any result changes. `refs.bib` = cat of refs_v3,
new_refs, classic_refs, review_refs (54 entries; all cites resolve).
Structural checks passed (macros defined, braces balanced, refs/labels,
cites). NO local LaTeX: user must compile
(`pdflatex main && bibtex main && pdflatex main && pdflatex main`) and check
the page count (8 pages long-paper limit); fig_tradeoff is generated but not
included in the body (needs log-x axis + space; optional).

**Text corrections made against generated numbers (honesty):**
- Validity table now shows U, test gamma mean AND max over the 3 dev draws;
  "Holds" compares the mean. Means are under the certified bound on all 4
  tasks; single 200-input draws exceed it on SQL (2.00 vs 1.91) and GSM8K
  (1.00 vs 0.60), and F1 on CoNLL (21.5 vs 20.5). Only bound exceeded on
  average: hand-written GSM8K (53.0 vs 48.9). Text says exactly this.
- Deletion: "the other five tasks: at most 3% (APV objective on SQL)".
- Accuracy: added dev-draw cert-F1 for Llama -2.9 [-4.8,-1.0] (significant);
  abstract/intro/conclusion now say "level with or slightly below
  agreement-based selection on average accuracy" (not "matches", not "no cost").
- Abstract: "bounded false-rejection rates hold on fresh test data".

**Item 2 status:** logs/run_distill_v41.sh running (started 11:33; PID 3426948
script). Order: 3 matched 0.6B runs (~15-25 min each incl. generation) then
1.7B certified and F1 (slower). When `code/logs/run_distill_v41.done`
exists: `cd paper && python3 make_numbers.py`, then check the sentence in
sec:downstream ("The gap persists when the certified set is subsampled ...
and with a larger student") against out/distill_ie_matched.json and
out/distill_ie_1p7b.json; rewrite if not supported.

### 2026-10-12 12:20: item 2 progress
Size-matched runs s0, s1 done (s2 generating). Provisional eval (scratch,
not a paper source): certmatched_s0 acc 46.8 / misc-acc 15.7 / misc-recall
0.28; s1 51.4 / 16.7 / 0.30; vs F1 49.5 / 4.9 / 0.06 and full certified
48.8 / 17.6 / 0.31 (seed-0 runs). The minority-category gap is not a
set-size effect so far. 1.7B runs (certified 3,448 ex, F1 2,705 ex) next;
ETA ~14:00-14:30 if no OOM.

### 2026-10-12 14:10: item 2 DONE; all three remaining items done
run_distill_v41.sh finished 13:26 (out/distill_ie_matched.json,
out/distill_ie_1p7b.json). IE misc ("else") recall on CoNLL test (555):
- size-matched certified (2,705 ex, 3 subsamples): acc 49.1+-2.3, misc-acc
  15.4+-1.5, recall 0.29+-0.01 (vs F1 50.4 / 5.6 / 0.08; full cert 48.0 /
  17.6 / 0.31). The gap is not a set-size effect.
- Qwen3-1.7B: certified acc 52.6, misc-acc 25.5, recall 0.39; F1 52.1 /
  6.9 / 0.10. Same pattern at larger scale.
make_numbers.py rerun (735 macros); tab_down has both rows; sec:downstream
sentence now quotes these via macros (dsMatchedRec, dsBig*).
Remaining for the user: compile LaTeX, check page count, final read.

### 2026-10-12 14:30: API credit restored; user approved A+B+C+D (cap $28)
Key check (no cost): key limit $700, key spend $382.85, remaining $317.15;
account total_credits $15,152.87 vs usage $13,253.10. User: "spend as low
as possible, only where needed, tell me cost before spending". Estimates
from logged per-output costs of existing pools:
A Few-NERD + FC test draws (3x200, 3 models, 33 outputs) ~$14;
B GSM8K fresh completion (Llama 262 + Qwen 300) ~$2.8;
C fills: SQL fresh Qwen 28, GSM8K weak fresh Llama-8B 55 + Qwen-7B 300 ~$0.5;
D Few-NERD distill pool (2000 x 3 outputs x 3 models; old file was empty) ~$2.4.
Approved all four. logs/run_paid_oct12.sh (per-run --max-cost sum $26.10,
--global-cap 410.85 checked at start of each run); writes
logs/run_paid_oct12.done. Logs: logs/paid_*.log.
After it finishes (all local, free): fewnerd/fc report over test seeds ->
out/report_{fewnerd,fc}.json (+ _fresh-style rows), test_bstruct pools,
robust_{fewnerd,fc}.json with test; refresh math fresh + weak reports;
redo Few-NERD distillation from the proper distill pool (GPU); make_numbers;
update paper text (tables now 6 tasks).
14:40 status: paid runs launched 14:3x; measured per-input cost matches the
estimate (fewnerd mini $0.0025, fc mini $0.0016); key billing delta equals
logged pool cost exactly ($0.511 after ~3 min). logs/run_paid_post.sh (local
follow-up, see list above; archives old B-based Few-NERD distill as
data/distill_fewnerd_fromB + out/distill_fewnerd_fromB.json) is launched and
waits for logs/run_paid_oct12.done; writes logs/run_paid_post.done.
Then: make_numbers.py needs fewnerd/fc added to tab_fresh/tab_validity and
paper text updated.
18:30 status: spent today $19.07 (key usage $401.93 incl. in-flight).
A done ($13.43). C done (SQL Qwen 300/300; weak GSM8K Llama-8B and Qwen-7B
300/300). D hit its $3.00 run cap with Qwen 1677/2000 (estimate was low);
remainder (323 Qwen, est. $0.17, within the user's $28 total cap) launched as
logs/run_paid_d2.sh -> logs/paid_fewnerd_distill2.done. run_paid_post.sh was
restarted (PID-killed while still waiting) to also wait for that marker.
B (GSM8K fresh): Llama 300/300, Qwen 101/300, still running.

### 2026-10-12 21:30: paid data DONE ($20.20 total today); results in
Final key usage $403.05 (today $20.20 of the approved $28). No more spending.
- Few-NERD final test (3 untouched draws pooled, 600 inputs): cert-hw +1.6
  [+0.6,+2.7] Llama, +0.9 [+0.3,+1.7] mini, +0.7 [+0.0,+1.6] Qwen; cert ~ F1;
  APV selects no check (= base). Test delta-bar cert 1.1-2.5% <= bound 3.93%.
- FC: ties (cert-hw -0.5 [-1.1,0.0] Llama); cert delta-bar <= bound 1.44%.
- GSM8K fresh now 3 models: ties; hand-written delta-bar Llama 17.9% vs cert
  0.34% (bound 0.47%). Weak Qwen-7B: ties.
- Validity (mean over draws) holds on all 6 tasks; single draws exceed the
  certified bound on Few-NERD (5.00 vs 4.25), SQL, GSM8K. Coverage over
  resamples: Few-NERD 100, FC 100, GSM8K 93, SQL 73.
- No deletion on Few-NERD/FC test either.
make_numbers.py: tab_fresh and tab_validity now loop over all tasks with
data (991 macros). Paper text updated (setup, tab:fresh caption, accuracy,
validity, limitations). Few-NERD distillation retraining from the proper
distill pool still running (run_paid_post.sh -> logs/run_paid_post.done);
then rerun make_numbers and check the Few-NERD distill sentence
(fnDiffHw / fnDiffFone) and the "B outputs" disclosure in main.tex.

### 2026-10-12 22:30: "why only CoNLL?" -> F1 deletion rule + stress test (no API)
User asked for a second deletion task with existing data. Finding:
**Rule (exact algebra):** adding a check whose rejected rows have precision p
raises F1 iff p < F1/2 (F1 = 2TP/(2TP+FP+FN)). Verified on all 332
F1-changing candidates over 6 tasks (scratchpad f1rule.py; identity).
So F1/agreement selection deletes a group whenever (i) the group's output
precision is below F1/2 ("deletable") and (ii) some candidate isolates it.
- deletable groups on A (precision incl. gold vs threshold): ie has_else
  0.227 < 0.317; fewnerd 4plus 0.235, building 0.262, event 0.230, product
  0.232 < 0.268; morph 1_morphemes 0.266, canonical 0.257 < 0.291; fc, sql,
  math none.
- isolating candidates (wipe >=30% of a group, scratchpad deleters.py): ie
  yes (else_field_should_not_include_proper_nouns, wipes 86% of has_else,
  solo dF1 +0.051); fewnerd none; fc/sql/morph have some but for groups that
  are NOT deletable (solo dF1 negative), so F1 never takes them.
=> CoNLL is the only task with both ingredients; this predicts the
observed pattern instead of calling CoNLL a quirk.
**Stress test** (logs/run_inject.sh; robust.py gained --inject): add
group-isolating checks (out/candidates_inject/: fewnerd inj:no_<type> for
all 8 types; morph inj:multi_segment; sql inj:no_join as a control where
the rule predicts no deletion) -> out/robust_{fewnerd,morph,sql}_inject.json.
**Stress-test results (out/robust_{fewnerd,morph,sql}_inject.json, out/f1rule.json):**
- Few-NERD: F1 selection took inj:no_{building,event,other,product}
  (rejected-row precision <= 0.18; picked when threshold F1/2 was >= 0.31)
  and none of art/location/organization/person (precision >= 0.24); deletion
  rate 99.5% over 200 resamples; on B wipes 100% of has_building, k=349/1000.
  Budgeted / F1-constrained / group: no injected check at any budget,
  deletion 0%. APV: selects nothing.
- morph inj:multi_segment: rejected rows precision 0.93 (mostly CORRECT
  single-segment outputs) -> not picked; uninformative stress test, not a
  counterexample (rule is about rejected-row precision).
- SQL control inj:no_join: precision 0.65 > 0.43 -> never picked; 0%.
certver/f1rule.py writes out/f1rule.json (rule check 332/332; deletable
groups; wipers; injected precision/steps). make_numbers.py: macros rule*,
thr*, nDeletable*, precIEElse, nIsolating*, inj* (1025 macros).
**Paper:** Proposition 3 (prop:f1, F1 rises iff rejected precision < F1/2)
+ proof in App. A; "When does agreement delete a group?" paragraph in
Method; "why only CoNLL" + "Stress test" paragraphs in sec:deletion;
abstract, contribution (1), limitations (stress-test checks written by us)
updated.

### 2026-10-13 ~00:30: Few-NERD distillation redone from the proper pool
run_paid_post.sh done. New out/distill_fewnerd.json (2,000-input distill
pool, never used for selection): certified 32.9, F1 30.2 (cert-F1 +2.7
[+0.7,+4.7]), hw 29.4 (+3.5 [+1.5,+5.6]), none 26.7, oracle 35.0. Old B-based
run archived (out/distill_fewnerd_fromB.json: 31.4/29.9/28.7). Paper
sentence updated ("beats ... F1 by +2.7 (one training seed)"). Running
logs/run_fewnerd_seeds.sh: seeds 1,2 for certified and F1 ->
out/distill_fewnerd_seeds.json (logs/run_fewnerd_seeds.done, ~2.5 h).
Then: add seed mean+-sd macros to make_numbers and revise the sentence.

### 2026-10-13 10:15: Few-NERD distillation seeds done -> claim corrected
out/distill_fewnerd_seeds.json: certified 32.9 / 32.1 / 29.9 (31.6+-1.6),
F1 30.2 / 30.6 / 31.1 (30.6+-0.4). The seed-0 "+2.7 over F1" does NOT hold
across seeds: level with F1. tab_down Few-NERD rows: hand-written 1 seed
(29.4), F1 and certified 3-seed mean+-sd. Sentence now: beats hand-written
by +3.5 [+1.5,+5.6] (paired, one seed), level with F1 over 3 seeds.
Next (proposed to user): full read-through of main.tex; Prop-3 figure;
optional independent review agent; user compiles + page count; freeze.

### 2026-10-13: full read-through of main.tex (macros resolved), fixes
Fixed: (1) dangling "There the AutoPyVerifier objective..." sentence moved
back before the Prop-3 explanation; (2) rule check phrased as an identity
("as it must, it agrees with all 332"); (3) budget blocks isolating checks
for groups larger than the budget (group constraint covers smaller);
(4) delta-bar wording ("% of each input's correct outputs"); (5) distill
"similar overall accuracy" (50.4 vs 48.0, not "same"); (6) validity: "three
test draws" (Few-NERD/FC draws are not development draws), table caption
too; (7) weak GSM8K filter recall is pooled over BOTH weak models (0.70),
text no longer says Llama-8B only; (8) setup no longer claims all test
results are on the fresh draw (validity + ablations use dev draws);
(9) conclusion states the rule; (10) API cost $73 (53 + 20.20).
Checked: proposer is Claude Opus 5.5 (correct); macros/braces/refs OK.

### 2026-10-13: "research direction and scope" review pass (user prompt.txt)
Backup before edits: paper/main_pre_review.tex. Story unchanged; structure
now: question (is agreement a safe way to select LLM-written checks?) ->
insight (Prop 3: F1 takes a check iff rejected precision < F1/2, so it
deletes categories models are bad at) -> method (budgeted selection +
certificate on model outputs) -> evidence.
Edits: abstract rewritten around the insight (gold-only clause dropped
from abstract); intro gained a "why" paragraph (Prop 3, prediction, stress
test) and a "remedy follows from the diagnosis" paragraph (overall budget
protects unnamed groups > tau/2; certify on model outputs, gold-only
2.8-fold as the justification); contributions 4 -> 3. Method: sentence on
overall budget protecting unnamed groups. Results reordered: 6.1 deletion
(+rule, stress test), 6.2 downstream, 6.3 NEW "What does the constraint
cost?" (tab:fresh + accuracy text led by cert-vs-F1), 6.4 validity (+gold-
only justification, bound-on-A note). tab:fresh column "Cert - Hand" ->
"Cert - F1" (make_numbers). Side material demoted to App. "Additional
Findings" (synthesis vs hand-written catch, proposers, audit of
hand-written checks); section "Ablations and audit" removed from body.
Limitations: "Scope of the condition" (Prop 3 exact for F1 only; APV not
covered; frequency of isolating checks only measured on our six tasks).
Body ~3,300 words + 3 tables.

### 2026-10-13: novelty / literature audit (user prompt), 3 subagents + own checks
Verified myself (fetched): SPADE (arXiv 2401.03038, PDF Sec 3.2: min |F'| s.t.
coverage>=alpha, FFR<=tau on <100 labelled outputs; no held-out bound, no
groups), EvalGen (2404.12272), CodeContests+ (Findings EMNLP 2025), SAFER
(ICLR 2026 poster; Clopper-Pearson + CRC, bounds wrongful exclusion of
correct answers), Egashira et al. COLM 2026 (Sec 4.2: policy "first unlearns
behavior that triggers false negatives" then recovers; triggers = LaTeX
token / English; whole-domain FN only hypothesised -> plateau), Zhao et al.
JMLR 2013 (F1/2 break-even, Lemma 12), Lipton et al. ECML PKDD 2014
(PMC4442797), Rigollet & Tong JMLR 2011, Zhou et al. 2026 (2608.20362),
Gururangan et al. EMNLP 2022.
Verdicts: (1) category deletion by agreement selection + propagation to
distillation/RL: NOVEL (no prior shows it). (2) Prop 3 = set-level form of
the known F1/2 break-even precision -> now attributed (Zhao 2013 Lemma 12;
Lipton 2014), proof "included for completeness", contribution reworded to
"explain it with the break-even property of F1". (3) constrained selection
has precedent (SPADE) -> claim narrowed to input-level + per-group budgets
+ held-out certificate on model outputs + evidence it removes deletion.
RL claim narrowed: Egashira shows unlearning of FN triggers; ours: when the
trigger is a correct category, unlearning is a lasting hidden loss.
Edits: abstract, intro (why + remedy paragraphs), contributions (1)(2),
Related Work rewritten (3 paragraphs: selecting LLM-written checks;
verifier error in RL and filtering; risk control incl. NP classification,
SAFER, Cherian 2024), Prop 3 attribution in Method + appendix proof note,
RL paragraph. paper/lit_refs.bib added (refs.bib now 65 entries).
Not cited (judged less necessary or not verified by me): OMVV, Salem 2026,
Jung "Trust or Escalate", OpenRubrics, Xin 2026, rStar-Coder, ACECoder.

### 2026-10-13: "scientific story and contributions" pass (user prompt)
Backup: paper/main_pre_story.tex. Contribution audit: old (1) split into
Diagnosis (deletion + F1 break-even explanation; falsifiable: 69% CoNLL,
0% on the five tasks without the condition, 99.5% in the Few-NERD stress
test, takes the 4/8 injected checks with lowest rejected precision) and
Consequence (deletion is learned: distill recall 0.08 vs 0.31, also
size-matched and 1.7B; GRPO 0.37 -> 0.13/0.09 vs certified keeps it);
(2) Remedy sharpened (gamma per input bounds filter wipe-out and gated
accuracy loss, Prop 2; overall budget protects unnamed categories; gold-only
2.8x justifies model outputs); old (3) "evaluation on six tasks" REMOVED as a
generic contribution (its falsifiable parts now evidence for Remedy).
Intro now: problem -> precise gap (criteria score aggregate counts; none
asks whose correct outputs are rejected; SPADE/EvalGen/AutoPyVerifier) ->
"Key insight" paragraph -> "Approach" paragraph -> contributions with
section pointers. Abstract rewritten in the same order. Results subsections
renamed Diagnosis / Consequence / Remedy: cost / Remedy: certificate.
Conclusion adds the implication (report which correct outputs generated
tests/rubrics/filters reject, not only how many). Caught and fixed a false
claim ("exactly the 4 checks below threshold": art/location/organization
were also below the initial threshold but not taken).

### 2026-10-13: method audit (user prompt) -- one real code/paper mismatch fixed
Backup: paper/main_pre_method.tex; old curves: code/out/curve_pre_bonf/.
1. ERROR (fixed, no result change): certver/curve.py certified instance-level
   selections with the UNCORRECTED 95% CP bound, while the paper (and
   robust.py) use Bonferroni over the 3 budgets (alpha 0.05/3). The pick
   ("smallest certified budget") is identical on all 6 tasks either way
   (ie 5%, fewnerd 5%, fc 2%, sql 2%, math 1%, morph 2%). curve.py now
   certifies with alpha=0.05/len(taus) and stores B_gamma_upper (corrected)
   + B_gamma_upper95 (uncorrected); logs/run_curve_bonf.sh re-ran the 6
   curves; certified sets and B stats identical (only check ORDER differs,
   and one unused output-level selection swapped a tied check).
2. ERROR (fixed): weak-model paragraph used the uncorrected SQL bound 1.69%
   (caption 1.91%) and claimed "F1 selection exceeded it (1.81/1.51%)",
   comparing F1 to the certified verifier's bound (F1's own bound is 3.77%).
   Sentence now reports only the certified verifier vs its corrected bound;
   make_numbers wkBound = boundB (Bonferroni).
3. Clarity/reproducibility added: delta(x) defined as Pr[V(y)=0|C(y)=1];
   gamma's output set (gold + greedy + 3 samples per model) and why per
   input; gated best-of-N = uniformly random accepted sample, expected
   accuracy in closed form; tau/2 rationale; tie-breaking and stopping;
   main verifier = overall budget (group variant evaluated alongside);
   n=1000, alpha, group alpha 0.05/(3G) for groups >=50 on B, TAU_G=20%
   justified by bound arithmetic (>=~12% at zero errors); Prop 1 assumption
   (candidate verifiers depend on A + proposal data only); resampling at
   tau=2% with 70% of LLM candidates + all hand-written (caption);
   appendix: data slices (50/1000/1000/2000), test sources (fc: every 10th
   Glaive example), decoding temps and max tokens, full group lists, k-means
   settings, distillation (LoRA r16 a32 do.05, 1 epoch, lr 2e-4, eff. batch
   16, fp32, greedy eval), RL (lr 2e-5, 160 tokens, clip 1, merged SFT
   adapter).
No material change to the scientific story.

### 2026-10-13: theory audit (user prompt)
Backup: paper/main_pre_theory.tex. Prop "valid" (CP + union bound) demoted
to a 2-sentence "Validity" paragraph stating the assumptions (appendix
proof removed). Prop "coverage" kept as "What gamma controls" with
intuition first; (a)+(b) merged into "filter loses in expectation at most
delta-bar <= gamma (exchangeable outputs)", (b) gated accuracy >= p0 - gamma,
NEW (c) deleting a group of share s requires gamma >= s/2 and gamma_g >= 1/2
-> budget tau rules out deleting groups > 2tau (named or not); selection at
tau/2 on A rules out groups > tau; groups tracked are >= 5% of inputs, and
B gamma of tau=2% selections <= 20/1000 -> explains 0% deletion. This
replaces three inconsistent informal claims ("larger than the budget",
"larger than tau/2", "wiping"). Prop F1 kept in main text with intuition
first; tautological "agrees with all 332 candidates" removed from results;
unused epsilon removed. Proofs for remaining two propositions in App. A.

### 2026-10-13: mathematical verification (user prompt)
Backup: paper/main_pre_mathcheck.tex. Findings and fixes:
1. ERROR: "delta-bar <= gamma" with delta(x) = Pr[V=0|C=1] over model
   samples is FALSE in general (counterexample: gold accepted, model correct
   w.p. 0.01 and always rejected when correct: delta(x)=1, gamma(x)=0.11).
   Fix: definitions now use the output set S_x (B: gold + greedy + 3
   samples per model), Z_x, R_x; gamma = Pr[Z_x=1]; delta-bar = mean R_x
   (reported on any output set). R_x <= Z_x pointwise gives delta-bar <=
   gamma ONLY on B-like sets. Test delta-bar (33 outputs/model) is now
   described as related to but NOT formally bounded by gamma (tab:fresh
   caption, ablation caption, Prop-1 remark, weak-model sentence: "the
   certificate makes no formal claim" for weaker models).
2. Prop 1(a) simplified and made exact: lost input => Z_x=1 pointwise, so
   E[fraction lost] <= gamma (no exchangeability needed; filter on the
   model outputs in S_x). (b) per model, y0 in S_x. (c) population and
   empirical versions.
3. Prop 2 (F1): added R nonempty; proof now shows D, D' > 0 (gold correct
   => TP+FN >= 1) before cross-multiplying. Fixed a sufficiency error:
   "raises F1 whenever rejected outputs are mostly wrong" -> "whenever
   correct less than F1/2 of the time; since F1/2 <= 1/2 only mostly-wrong
   sets qualify" (necessary, not sufficient).
4. "50-100 inputs => bound >= ~12% at zero errors" was wrong for n=100
   (6.2%). Now: 50 inputs ~12%; every tracked group > 6% (min-size groups:
   6.6-11.7% across tasks) -> per-group 1-5% still uncertifiable (claim
   preserved). Group bounds noted as valid conditionally on group sizes.
5. Deletion explanation on B made precise: tau=2% full-data selections have
   gamma-hat_B <= 2% (max 20/1000, CoNLL) -> deletion on B needs s < 4%.
6. Abstract: "bounds hold on held-out test pools" (not "fresh test data").
Verified OK: Clopper-Pearson + union bound validity; Prop 1(b),(c);
Prop 2 algebra and boundary cases (TP=0, R empty).

### 2026-10-13: claim-evidence ledger + experimental design audit (user prompt)
Ledger: paper/CLAIM_LEDGER.md (23 claims; support levels; gaps; missing
experiments E1-E6 with hypothesis/protocol/priority). Backup before text
edits: paper/main_pre_ledger.tex.
E1 (done, free): certver/resample_detail.py replays robust.py's RNG
(reproduces every deletion rate exactly). CoNLL: the deleting check
ie-r0-84f7d14832 survives the 70% candidate subsample in 138/200
replicates; F1 and APV take it and delete has_else in 100% of those, 0% of
the other 62. => the 69% is the availability rate; claim restated as
"deletes whenever the isolating check is available".
E2 (done, free): output-level (SPADE-style: FFR over correct model outputs
<= 1% on A) selector: 0% deletion on all 6 tasks + Few-NERD stress test;
catch similar (CoNLL 49.5 vs input-level 49.0; inject 27.2 vs 26.9).
=> remedy narrowed: protection comes from budgeting false rejection at all;
per-input gamma adds a certifiable quantity with Prop-1 guarantees.
Files: out/resample_detail_{ie,fewnerd,fc,sql,math,morph,fewnerd_inject}.json;
make_numbers macros rd*.
E3 (running): logs/run_rl2_seeds.sh, RL seeds 2-3 for f1 and certified
gates (~1 h each, GPU) -> out/rl2_ie_seeds.json, logs/run_rl2_seeds.done.
Then: make_numbers RL rows over 4 seeds (f1/certified) and update B4 text.
E5 (paid, ~$1-3) NOT run: needs user approval.

### 2026-10-13: E5 (user approved max $3): Few-NERD feedback proposer round
Key usage at start 409.4476 (NOTE: +$6.40 vs 403.05 after the approved paid
runs with no API calls of ours in between -> possibly other use of the key;
told the user). admit (free) on Few-NERD round-0 candidates ->
out/candidates_e5/admit_fewnerd_round0.json (35 admitted, 16 unsound with
false-rejection feedback). propose round 1 with that standard feedback (no
hint): Opus 25 checks ($0.2179 logged), GPT-4o 2 calls 38 checks ($0.0700)
-> out/candidates_e5/fewnerd_round1_{opus,gpt4o}.jsonl. Kept OUT of
out/candidates/ so main Few-NERD results are unchanged.
Full-data analysis (scratchpad e5.py): F1 selection over round0+round1
takes 6 new checks incl. fewnerd-r1_gpt4o-3815bf311d
"entities_with_proper_casing" (rejects any all-lowercase entity; rationale
"proper nouns usually begin with capital letters") -> wipes 39.2% of
has_other inputs on B (catch 0.535); budgeted tau=2% worst wiped 4.6%.
Two new checks that wipe 100% of 4plus_entities are refused by F1
(rejected precision 0.32/0.37 > threshold 0.268), consistent with Prop 2.
Running: resample_detail --inject "out/candidates_e5/fewnerd_round1_*.jsonl"
-> out/resample_detail_fewnerd_e5.json.
E5 billed total: $0.2879 (key 409.7355). Resampling (200, enlarged pool):
- F1: deletion 0% (never >= 50%), but has_other is its worst-wiped group in
  145/200 (casing check fewnerd-r1_gpt4o-3815bf311d "entities_with_proper_
  casing": rejects all-lowercase entities; Few-NERD "other" has many
  lowercase entities) -> natural PARTIAL category loss.
- APV objective: deletes 4plus_entities in 71% (77% when one of two BUGGY
  checks is available: 31048b889d treats two empty fields as duplicates ->
  rejects ~all outputs; f3a6169bfe requires each entity inside EVERY token
  -> rejects every output with an entity). Mechanism differs: macro-F1
  rewards rejecting almost everything when most outputs are wrong (Few-NERD
  acc 24-34%). F1 refuses both (rejected precision 0.32/0.37 > 0.268).
- budgeted / output-level / F1-constrained / group: 0% deletion.
resample_detail.py now also stores worst_frac and per-group wiped_frac;
rerun for fewnerd_e5 running (has_other wiped distribution).
E5 final (out/resample_detail_fewnerd_e5.json, with per-group fractions):
has_other wiped mean/p90: F1 29.5/40%, APV 71/100%, budgeted 2.2/4%,
output-level 7.6/10%, F1-constrained 2.2/4%, group 1.0/2%. Deletion: APV
71%, all others 0%. Paper: §6.1 "A natural feedback round" paragraph
(macros eOther*, eDel*, eNnew), contribution (1) clause, Limitations
updated (one of six initial pools + one extra round). Ledger E5 row done.

### 2026-10-13 ~15:40: E3 done (RL seeds 2-3)
out/rl2_ie_seeds.json (eval of sftinit + all rl2 gens). Misc recall:
F1 gate 0.135/0.087/0.151/0.079 (0.11+-0.04; unlearns in all 4 seeds; acc
62.8+-0.6 vs start 63.6); certified 0.317/0.437/0.492/0.373 (0.40+-0.08;
acc 65.0+-0.3); label 0.42/0.55 (2 seeds); start 0.37. make_numbers uses
rl2_ie_seeds.json; >= 3 seeds shown as mean+-sd; new macros rlRecMin*,
rlRecMax*, rlN*. Text: abstract (over 4 seeds), C2 ("in every one of 4
seeds, at most 0.15"), §6.2 (certified 0.32-0.49 across seeds), Tab 3
caption, Limitations (two to four seeds). Ledger B4 -> Strong.
Remaining optional: E4 (1.7B second seed), E6 (CIs on deletion/coverage).

### 2026-10-13: adversarial experimental audit (user prompt)
Ledger section F in paper/CLAIM_LEDGER.md (13 issues, classes A/B/C).
Backup: paper/main_pre_adversarial.tex. Done (B/C): certver/adversarial.py
-> out/adversarial_ie.json: deleter rejects GOLD for 86%/81% (A/B) of misc
sentences; F1 on A+B still takes it (78-85% misc lost on test pools);
gold-free clusters rich in misc lose 28-29% vs <=4%; distill composition
(F1: 612 misc entities, 0% titlecase, 8% correct; certified 1,659, 58%,
26%; oracle 222, 100% correct). Wilson CIs; mean worst-group loss 57 vs 4%.
PROVENANCE FINDING: CoNLL distillation sets were built (10-10 16:45) from
selections of the pool BEFORE ie_round2_opus; reconstructed exactly
(out/distill_ie_selections_pre_repair.json; rebuilt 2705/3448 rows ==
saved). Final F1 adds ie-r2_opus-708354e2b9; final certified adds that and
ie-r2_opus-0197537f8a. Disclosed in App. Implementation. (RL gates were
built at run time from the final selections.)
Running: A1 logs/run_ablate_deleter.sh (distil on pre-repair F1 minus
ie-r0-84f7d14832, 3 seeds -> out/distill_ie_f1minusdel.json);
logs/run_budget_sens.sh (resample_detail --budget 0.025/0.005, 6 tasks ->
out/resample_detail_<t>_b<b>.json). Then: text for both.
16:30 adversarial audit results:
- Budget sensitivity DONE (out/resample_detail_<t>_b0.005/0.025.json):
  every budgeted variant (input, group, output-level, F1-constrained) 0%
  deletion on all 6 tasks at tau=1% and 5%; budgeted worst group <= 18%
  (CoNLL tau 5%). F1/APV unchanged (69% CoNLL). Macros bs*; §6.1 sentence.
- Deleter ablation: F1 (pre-repair) minus ONLY ie-r0-84f7d14832 -> recall
  0.325 / 0.349 (seeds 0,1), acc 50.1 / 48.6 (F1 0.08, certified 0.31)
  => the single check causes the downstream loss. Seed 2 OOM'd on the
  SHARED GPU (another user's pytest took 4 GB) -> logs/run_ablate_deleter_s2.sh
  waits for >= 10 GB free, retries (same settings), re-evaluates all seeds,
  writes logs/run_ablate_deleter.done. Then rerun paper/make_numbers.py
  (macros ablDel* recompute over available seeds; text already in §6.2).
Seed 2 retry succeeded: f1minusdel recall 0.325/0.349/0.341 (mean 0.34),
acc 50.1/48.6/51.5 (mean 50.1). make_numbers rerun (ablDelN=3). Ledger F1
updated. Adversarial audit COMPLETE.

### 2026-10-13: full manuscript revision (user prompt)
Backup: paper/main_pre_fullrev.tex. Abstract tightened (~214 words).
Intro: FIXED factual error (CodeT ranks code by agreement with generated
tests; it does not validate against reference solutions); Approach and
Contributions tightened (contribution 2 now includes the deleter ablation
0.34). Setup: per-input justification moved next to gamma. Method: Select
paragraph reordered (groups -> main verifier uses overall budget -> group
variant). Exp. setup: baselines now list F1-with-budget and per-output
(SPADE constraint); strong hand-written moved to appendix with post-hoc
disclosure. §6.1 split into: main finding (+CI, availability) /
Alternative explanations / Budgets prevent it / Where deletion occurs.
§6.3 delta-bar precision unified (frDltCert 1 decimal). Limitations
rewritten (distributional guarantee incl. no formal claim for absent
models and 33-output delta-bar; how often deletion occurs; scale/data;
baselines/students incl. 1.7B one seed); stale "held on fresh draws and
weaker models" removed. Conclusion: any budget prevents deletion; per-input
budget gives the certifiable, bounding quantity.
Body ~4,700 words + 3 tables: page budget may be tight (8 pages); user to
compile and report page count.

### 2026-10-13: concision and accessibility pass (user prompt)
Backup: paper/main_pre_concise.tex. Body ~4,700 -> ~4,230 words (+3 tables).
Intro: Key insight / Approach / Contributions compressed (contributions now
one sentence-group each, details left to §6); gold-only SQL number kept
once in intro (pointer) and fully in §6.4. Method: group-bound arithmetic
and "why budgeted selection does not delete on A/B" moved to App. B
("Certification and Validity Details"); Prop-2 follow-up trimmed. §6.1
"Where deletion occurs" tightened. §6.4 rewritten compactly (single-draw
exceedances summarised by the largest; coverage "at least 93% on five
tasks, 73% on SQL"); full per-task values stay in Tab. validity. §6.2 split
into two paragraphs for readability. Conclusion cut to findings +
implication. Nothing deleted that carries evidence or reproducibility info.

### 2026-10-13: title / abstract / introduction revision (user prompt)
Backup: paper/main_pre_opening.tex. Title -> "When Verifiers Delete
Categories: Agreement-Based Selection of LLM-Written Checks and a Certified
Alternative" (diagnosis-first; remedy has prior art). Abstract: problem ->
gap ("agreement counts errors without asking whose") -> mechanism -> CoNLL
evidence (verifier-level 84%, distill 0.08 vs 0.31, RL 0.37 -> 0.11) ->
prediction -> remedy + evidence -> conclusion sentence. Intro: added why it
matters (verifiers decide what models are trained on); gap paragraph
merges AutoPyVerifier/EvalGen/SPADE/CodeT/HardTests; Approach states the
two differences (per-input gamma with guarantees; per-output budget
protects a category only in proportion to its share of correct outputs,
small for categories models rarely get right -- consistent with E5 7.6% vs
2.2%; model outputs vs gold 2.8x). Contributions: "4 least precise of 8",
GRPO acronym removed. Fixed: abstract had attributed the 84% loss to the
single check (it is the selected verifier's).

### 2026-10-13: narrative and logical flow pass (user prompt)
Backup: paper/main_pre_flow.tex. Structure now: Intro -> Related Work ->
Setup (definitions; now introduces splits A/B, generating models, groups
before use) -> NEW §4 "Why Agreement Deletes Categories" (F1 break-even
proposition moved out of the method; ends by motivating the remedy) ->
§5 Constrained, Certified Selection (opens with the 3-stage pipeline;
Prop-coverage(c) now stated as a PREDICTION tested in §7.3 instead of
"explains Table 1") -> §6 Experimental Setup -> §7 Results: Diagnosis
(pure diagnosis: main finding, alternative explanations, where deletion
occurs, stress test, natural round) / Consequence / Remedy: no deletion,
little cost ("Deletion" paragraph moved here from Diagnosis + "Accuracy")
/ Remedy: certificate. "wipes a group" replaced by defined wording in §4.

### 2026-10-13: figure audit (user prompt)
Main text had NO figures; gen/fig_tradeoff.tex was generated but unused and
STALE (plotted the uncorrected B bound) -> removed from make_numbers.py
(with unused macro boundBnoBonf) and deleted. Added Figure 1 (§7.2,
fig:down) via new paper/make_figures.py (matplotlib 3.8.4 installed into
.venv_train only; torch/transformers/peft versions unchanged): misc recall,
(a) distillation F1 / F1 w/o deleting check / certified / certified
size-matched / label-filtered, (b) RL label / certified / F1 gates with the
start line; one point per seed, bar at mean; y-axis 0-0.6 (no truncation);
Okabe-Ito colours + distinct markers; values printed by the script and
checked against out/*.json. Table tab:down moved to new App. "Downstream
Results" (full accuracy/misc-acc/1.7B/Few-NERD rows). Backup:
paper/main_pre_figure.tex. Single takeaway: recall collapses only when the
deleting check filters or gates, at similar accuracy.

### 2026-10-13: table audit (user prompt)
ERROR FIXED (no data change): ablation "Claimed" bounds used the UNcorrected
95% CP bound (ablate.py), inconsistent with the paper's certificate
(Bonferroni over 3 budgets). make_numbers now recomputes every claimed
bound at alpha=0.05/3 from the stored counts (single_split: A counts; main
/ proposers: B counts, asserted to reproduce the stored 95% bound; gold_only:
count on B's gold answers recovered EXACTLY by inverting the stored bound,
k=37/1000). SQL gold-only claim 4.84 -> 5.19%, ratio 2.8 -> 2.6-fold
(intro + §7.4 via macro); SQL full method 4.61 -> 4.95 (= main-text bound
at tau 5%); CoNLL full method 3.59 -> 3.89 (= boundBIE). All "Holds"
unchanged. Validity table header fixed (spanning "Test gamma (%)": mean,
max). Downstream table: added "without the deleting check (3 seeds)" row
(0.34+-0.01 recall, 50.1+-1.4 acc); Start row relabelled "label-filtered
SFT"; units in header. Checked: safety table certified counts match
curve selections; no -0.0 artifacts; rounding never flips Cert-F1 signs;
bold only marks failed bounds (consistent).

### 2026-10-13: scientific integrity audit (user prompt)
Backup: paper/main_pre_integrity.tex. 11 statements corrected (ledger
section G). Notable: F1 deleted in 0.5% of morphology resamples but the
0-decimal macro printed "0" in Table 1 and text ("deletes on none") ->
new rate() formatter in make_numbers (sub-1% rates get one decimal) and
wording "at most 0.5%"; student-behaviour claim replaced by measured
predictions (F1 student 78 misc entities, 21% title-case vs certified 190,
49%); base model recall 0.11; Spider aliases 818/819; "accepted exactly"
-> "raises F1 exactly". New macros: stuMisc*, rlRecBase, rlElseBase,
sqlJoin*, delRateFoneMaxOther.

### 2026-10-13: academic writing pass (user prompt)
Backup: paper/main_pre_writing.tex. Prose only, no technical change:
contribution (1) untangled (stress test no longer under "tasks where the
condition fails"); §4 triple restatement of the break-even rule trimmed;
"Validity" made a \paragraph like its siblings; "100% and 100% of those"
-> "both objectives delete ... in 100% of those replicates"; "rows of
CoNLL inputs" -> "outputs for CoNLL inputs"; "wiping" -> defined term
"losing"; paragraphs no longer open with bare "Figure 1." / "Table 4.";
RL paragraph split into shorter sentences; conclusion "accepts" ->
"rewards" (consistent with the integrity fix); "these are what we add" ->
"we address all three". Stock-phrase scan clean; sentence openers varied.

### 2026-10-13: simulated ARR red-team review (independent agent)
Scores S3/E3/O3 (Findings), conf 4. Backup: paper/main_pre_redteam.tex.
New analyses (certver/redteam.py -> out/redteam.json; data/fresh_bstruct/):
gold-admission+F1 never takes the casing check, deletes nothing (all tasks);
fresh draws restructured like B: certified gamma holds on IE 1.00 / math
0.33 / morph 0.67 but FAILS on SQL 2.33 vs 1.91; gold-only SQL verifier
gamma on like-with-like pools 23.3% vs claimed 5.19% (4.5x, replaces the
2.6x delta-bar comparison in intro/§7.4); F1 without gold rows still takes
the deleter; group certificate passes 5/6 tasks (CoNLL 20.5%).
FIXED: Table 1 rows lacked spacer cells (15-col header, 13 cells) -> Hand
column showed 178. Removed CIs on resampling rates (replicates share B).
Reframed C1 (one natural case). Full list: paper/CLAIM_LEDGER.md section H.
Needs NEW evidence (not done): natural proposer rounds on more datasets
with rare categories to measure how often deletion arises.

### 2026-10-13: final end-to-end consistency audit (user prompt)
Backup: paper/main_pre_final_audit.tex. Checked every hand-typed number in
the text (all design constants or previously verified), stale phrases,
symbols, acronyms, terminology, cross-refs, cites, inputs. Fixed: API cost
$73 -> $74 (53.05 + 20.20 + 0.29); Fig. 1 caption "555" -> \szEvalIE;
RLVR, GRPO, SFT now defined at first use; tau introduced in the intro
before use; Related Work no longer uses tau for SPADE's threshold
(notation clash). Terminology consistent (British spelling; "oracle" only
in "human oracle programs"). gen/tab_{cert,distill,filter,main}.tex are
v4.0-only artefacts (README note). make_numbers (1,138 macros) and
make_figures rerun; no missing macros/refs/cites/inputs; braces and $
balanced. The paper still needs a local LaTeX compile + page count.

### 2026-10-13: figures + PaperBanana prompts (user request)
Backup: paper/main_pre_figures2.tex. New figures (matplotlib, rendered and
inspected; numbers from out/*.json or gen/numbers.tex):
- fig_overview (figure*, Intro; TikZ twin fig_overview_tikz.tex using the
  same macros, NOT compiled here): agreement path vs budgeted+certified path
  for the CoNLL casing check (23% < 32%, 84%, recall 0.08 / 0.37->0.11 vs
  0.31 / 0.40).
- fig_mechanism (§4): 387 candidate checks; x = rejected precision / (F1/2),
  y = largest share of a group lost; only 8 in the danger zone (CoNLL
  deleter + 7 injected stress-test checks); 5 points clipped at x=3 (caption).
  Data: certver/figdata.py -> out/figdata_mechanism.json.
- fig_validity (appendix): U_B vs test-draw gamma + fresh gamma; SQL fresh
  failure shown in dark vermillion.
- fig_cost (appendix): cert - F1 gated accuracy with 95% CIs per task/model.
Fixed during inspection: overlapping labels/legend (mechanism), text
overflow and wrong step order (overview: check is refused during selection,
before certification), crowded tick labels (validity).
\usetikzlibrary{arrows.meta} added to main.tex. paper/figure_prompts_
paperbanana.md: 6 prompts (overview "conveyor belt", mechanism "balance",
propagation "fading colour", certification "split A / split B", two
statistical plots) in PaperBanana's input format (methodology + caption),
numbers filled from gen/numbers.tex. Page budget: +~0.4 page in main text;
compile and check.

### 2026-10-13: repository restructured in place for a public GitHub release
Layout now: src/ (certver, soundver, train_sft.py, train_grpo.py, tests),
paper/, out/ (results), data/ (generated; data/raw = public datasets,
git-ignored), scripts/ (download_data.sh, data_checksums.sha256,
hf_upload.py, hf_download.py, runs/run_*.sh), docs/ (this log,
SESSION_NOTES.md, claude/), archive/ (version1-3, code + paper source),
README.md, INDEX.md, requirements*.txt, .env.example, .gitignore, LICENSE
(MIT), CITATION.cff (authors TODO). Every move is in _trash/MOVES.log;
removed material is in _trash/ (git-ignored). version4/ now only holds the
untouched .venv_train (git-ignored).
Code changes: DATA_ROOT = data/raw (env CERTVER_DATA_ROOT), .env read from
repo root, run scripts cd to repo root + PYTHONPATH=src + TRAIN_PYTHON;
version2 dependency removed (spider_distill.py copied verbatim; old SQL label
path -> certver.sqllabel); Spider db paths in data files rewritten to
repo-relative + resolve_db_path() fallback. Verified: make_numbers and
make_figures reproduce paper/gen identically (figures pixel-identical); SQL
label reproduces 120/120 saved labels; sandbox test passes; data loaders
work for all six tasks. Public datasets pinned (HF commits for Few-NERD,
Glaive, GSM8K; SIGMORPHON commit ac161e1; Spider official zip); GSM8K JSON
conversion byte-identical. Large generated files (3,878 files, 742 MB incl.
4.6 MB private CoNLL) listed in data/manifest.json for Hugging Face.
Tracked repo: 712 files, 126 MB (largest 4.6 MB).
