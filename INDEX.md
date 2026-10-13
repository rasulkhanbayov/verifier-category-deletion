# Index

A map of the repository for a new reader. Run everything from the repository
root with `PYTHONPATH=src`.

## Start here

| File | What it is |
|---|---|
| `README.md` | Findings, install, three levels of reproduction, data sources and licences |
| `paper/main.tex` | The paper |
| `paper/CLAIM_LEDGER.md` | Every claim in the paper, its evidence file, support level and the audits behind it |
| `docs/SESSION_NOTES.md` | Project history, decisions, audits, known problems and open items |
| `docs/PLAN.md` | Full working log of the project (chronological) |

## Paper

| File | Role |
|---|---|
| `paper/main.tex` | Manuscript (ACL format); includes `gen/` tables, macros and figures |
| `paper/make_numbers.py` | Writes `paper/gen/numbers.tex` (every number in the text) and all tables from `out/` |
| `paper/make_figures.py` | Writes `paper/gen/fig_*.pdf` from `out/` and `gen/numbers.tex` |
| `paper/gen/` | Generated tables, number macros and figures (never edit by hand) |
| `paper/fig_overview_tikz.tex` | TikZ version of Figure 1 (same numbers; the PDF version is used by default) |
| `paper/refs.bib` | Bibliography (built from `refs_v3.bib`, `new_refs.bib`, `classic_refs.bib`, `review_refs.bib`, `lit_refs.bib`) |
| `paper/figure_prompts_paperbanana.md` | Prompts for drawing the figures with PaperBanana |

### Which file produces each table and figure

| Paper element | Produced by | From result files | Computed by |
|---|---|---|---|
| Fig. 1 overview | `make_figures.py` | `gen/numbers.tex` | (below) |
| Fig. mechanism (two ingredients) | `make_figures.py` | `out/figdata_mechanism.json` | `python -m certver.figdata` |
| Fig. downstream (recall) | `make_figures.py` | `out/distill_ie_seeds.json`, `distill_ie_f1minusdel.json`, `distill_ie_matched.json`, `distill_ie.json`, `rl2_ie_seeds.json` | `scripts/runs/run_distill*.sh`, `run_ablate_deleter.sh`, `run_rl2*.sh` (+ `certver.eval_distill`) |
| Table: catch, false rejection, deletion | `make_numbers.py` → `gen/tab_safety.tex` | `out/robust_<task>.json`, `out/curve_<task>_inst_multi.json` | `certver.robust`, `certver.curve` (`run_apv.sh`) |
| Table: fresh test accuracy | `make_numbers.py` → `gen/tab_fresh.tex` | `out/report_<task>_fresh.json` | `certver.report` (`run_fresh_reports.sh`, `run_paid_post.sh`) |
| App. table: downstream | `make_numbers.py` → `gen/tab_down.tex` | distillation and RL files above, `out/distill_fewnerd*.json` | as above |
| App. table + figure: certificate check | `make_numbers.py` → `gen/tab_validity.tex`; `fig_validity` | `out/robust_<task>.json`, `out/redteam.json` | `certver.robust`, `certver.redteam` |
| App. figure: accuracy cost | `make_figures.py` → `fig_cost` | `out/report_<task>_fresh.json` | `certver.report` |
| App. table: ablations | `make_numbers.py` → `gen/tab_ablate.tex` | `out/ablate_<task>_multi.json` | `certver.ablate` |
| Text: F1 break-even, stress test | `gen/numbers.tex` | `out/f1rule.json`, `out/robust_<task>_inject.json` | `certver.f1rule`, `certver.robust --inject` (`run_inject.sh`) |
| Text: availability of the deleting check, per-output budget, budget sensitivity, feedback round | `gen/numbers.tex` | `out/resample_detail_*.json` | `certver.resample_detail` (`run_resample_detail.sh`, `run_budget_sens.sh`) |
| Text: alternative explanations, data composition | `gen/numbers.tex` | `out/adversarial_ie.json` | `certver.adversarial` |
| Text: red-team analyses (gold admission, fresh validity, group certificate) | `gen/numbers.tex` | `out/redteam.json` | `certver.redteam` |

## Method code (`src/`)

| Path | Role |
|---|---|
| `src/soundver/generate.py` | Task loaders (data in `data/raw/`), prompts, correctness labels, hand-written checks, OpenRouter client |
| `src/soundver/checks.py`, `records.py`, `rates.py` | Hand-written checks and record/rate utilities |
| `src/certver/data.py` | Splits: proposal (50), A (1,000), B (1,000), distillation (2,000), test, fresh |
| `src/certver/pool.py` | Generates model outputs for a split (API; cost-capped) |
| `src/certver/propose.py` | Asks an LLM to write candidate checks |
| `src/certver/sandbox.py` | Runs LLM-written checks in a restricted, fail-closed sandbox |
| `src/certver/admit.py` | Runs checks on pools; admission reports and feedback |
| `src/certver/curve.py` | Selection on A (budgeted, F1, AutoPyVerifier objective) and certification on B |
| `src/certver/robust.py` | Groups, budgeted / group / F1 selection, two-level certificate, resampling, like-with-like test |
| `src/certver/report.py` | Test-set accuracy, false-rejection rates and filtering metrics with bootstrap CIs |
| `src/certver/sqllabel.py`, `spider_distill.py` | SQL correctness label (original + three perturbed databases) |
| `src/certver/distill_sets.py`, `eval_distill.py` | Distillation training sets and student evaluation |
| `src/certver/f1rule.py`, `figdata.py` | Break-even analysis and figure data |
| `src/certver/resample_detail.py`, `adversarial.py`, `redteam.py`, `ablate_deleter.py`, `ablate.py` | Audit analyses |
| `src/train_sft.py`, `src/train_grpo.py` | Student distillation (LoRA SFT) and GRPO policies |
| `src/tests/` | Sandbox test and inspection scripts |

## Data and results

| Path | Contents |
|---|---|
| `data/raw/` | Public datasets (not in git; `scripts/download_data.sh`) |
| `data/pools/` | Splits A and B: gold, greedy and three samples per model |
| `data/test/`, `data/test_bstruct/` | Development test draws and their B-like restructuring |
| `data/fresh/`, `data/fresh_bstruct/`, `data/fresh_weak/` | Fresh test draws, B-like restructuring, weaker models |
| `data/distill/`, `data/distill_fewnerd/` | Distillation pools, training sets, student generations |
| `data/rl/` | RL starting adapter, policy generations and logs |
| `data/MANIFEST.md`, `data/manifest.json` | Files hosted on Hugging Face (size, sha256) |
| `out/` | All result files the paper reads (JSON), `out/candidates/` (LLM-written checks), `out/verdicts/` (cache, on Hugging Face) |

## Scripts

| Path | Role |
|---|---|
| `scripts/download_data.sh` | Pinned downloads of the public datasets + checksum check |
| `scripts/data_checksums.sha256` | Checksums of the raw files used for the paper |
| `scripts/hf_upload.sh`, `scripts/hf_download.py` | Hugging Face transfer of large generated files |
| `scripts/runs/run_*.sh` | The run scripts used for each experiment (each lists its inputs and outputs) |

## Archive

`archive/version1` (AV-TTS, a different MICCAI project), `archive/version2`
(SoundVer, EACL draft), `archive/version3` (the predecessor paper, "Soundness Is
a Measurement, Not an Argument"; frozen and not submitted). Code and paper
source only; each folder has its own README. Nothing in `src/` depends on them.
