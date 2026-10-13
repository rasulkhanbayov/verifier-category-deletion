# Session notes

What a successor needs to know about this project. `docs/PLAN.md` is the full
chronological log; `paper/CLAIM_LEDGER.md` lists every claim with its evidence.

## 1. History

| Version | Folder | Paper | Status |
|---|---|---|---|
| 1 | `archive/version1` | AV-TTS, anatomy-verified test-time scaling (MICCAI) | different project, kept for reference |
| 2 | `archive/version2` | SoundVer, "Gate Before You Rank" (EACL draft) | superseded |
| 3 | `archive/version3` | "Soundness Is a Measurement, Not an Argument" (COLING package) | frozen, not submitted; its SQL label was broken, so its SQL numbers must not be reused |
| 4.0 | (this repo, superseded drafts removed) | certified verifier synthesis | reframed after an internal review (2026-10-10) |
| 4.1 | this repo | "When Verifiers Delete Categories" | current paper |

Why the reframes: version3 measured whether hand-written checks are sound;
version4 asked how to *select* LLM-written checks safely; an internal review
showed the strongest finding was that agreement-based selection deletes a
category, so version 4.1 is built around that diagnosis, its consequences and a
budgeted, certified alternative.

## 2. The paper in brief

* **Diagnosis.** F1 (agreement) selection accepts a check exactly when the
  precision of the outputs it newly rejects is below F1/2 (a known break-even
  property; Zhao et al. 2013, Lipton et al. 2014). On CoNLL-2003 one
  LLM-written check ("proper nouns do not belong in the miscellaneous field")
  meets this and is selected whenever it is a candidate; it deletes the
  miscellaneous category. A stress test on Few-NERD and a natural feedback round
  (a casing check removing ~30% of the "other" type) confirm the mechanism.
* **Consequence.** Distilled students lose the category (recall 0.08 vs 0.31);
  removing only the deleting check restores it (0.34); GRPO policies gated by
  the F1 verifier unlearn it in all four seeds.
* **Remedy.** Select under a budget on γ (fraction of inputs with a correct
  output rejected), overall and per group; certify γ on held-out model outputs
  with a Clopper–Pearson bound (Bonferroni over τ ∈ {1, 2, 5}%).
* **Honest scope.** Natural deletion on one of six tasks; a per-output
  (SPADE-style) budget and gold-based admission also prevented deletion on our
  data; the certificate failed under Spider's train-to-dev shift; average
  accuracy up to ~3 points below F1 on CoNLL/Llama.

## 3. Audits done on the paper (2026-10-13)

In order, each recorded in `docs/PLAN.md` §10 and the ledger: research-direction
and scope; novelty and literature (three literature agents plus own
verification; claims narrowed after SPADE, Lipton et al., Egashira et al.);
scientific story and contributions; method audit (found that `curve.py`
certified with an uncorrected bound; fixed, picks unchanged); theory audit;
mathematical verification (four errors fixed, e.g. δ̄ ≤ γ only for B-like output
sets); claim–evidence ledger and experimental design (E1–E6); adversarial audit
(causal ablation of the deleting check, budget sensitivity, provenance);
manuscript revision; concision; title/abstract/introduction; narrative flow;
figure and table audits (Table 1 spacer-cell bug found later by the red team);
integrity audit; writing pass; simulated ARR red-team review (Overall 3,
Findings); end-to-end consistency audit.

## 4. Provenance notes and known quirks

* The CoNLL distillation training sets were built from selections made
  **before** the last CoNLL proposer round (`out/distill_ie_selections_pre_repair.json`);
  the final F1 and certified selections add one and two repair-round checks,
  neither the deleting check. Rebuilding from the earlier selections reproduces
  the saved sets exactly. The ablation table was also computed on that earlier
  pool (CoNLL catch 52.0 vs 52.5).
* `ablate.py` stored uncorrected 95% bounds; `make_numbers.py` recomputes the
  Bonferroni-corrected values from stored counts (the gold-only SQL count,
  37/1000, is recovered by inverting the stored bound).
* The three certified CoNLL students give identical misc recall (0.31) from
  different predictions (checked).
* Few-NERD and function calling were added later: their three test draws are
  uninspected and serve both as the final test set and the certificate check.
* The Few-NERD feedback-round checks (`out/candidates_e5/`) and stress-test
  checks (`out/candidates_inject/`) are kept out of all main results.
* Rates under 1% are printed with one decimal (`rate()` in `make_numbers.py`)
  so a 0.5% resampling rate never prints as 0.

## 5. Costs and compute

* API (OpenRouter): version4 about **$74** in total (53.05 + 20.20 + 0.29). The
  key's usage once rose by $6.40 without a corresponding run of ours; check for
  other users of the key.
* GPU: one NVIDIA P100 (16 GB), fp32 (fp16 diverged). TRL's GRPOTrainer
  produced degenerate samples, so `src/train_grpo.py` is a direct GRPO loop. The
  GPU is shared; one run hit out-of-memory because another user's job took 4 GB.
* Sandbox: RLIMIT_AS raised to 16 GB (a 2 GB limit hung workers).

## 6. What this restructure changed (2026-10-13)

* Layout: `src/` (was `version4/code/{certver,soundver}` and training scripts),
  `paper/`, `out/`, `data/` (generated), `data/raw/` (public datasets, git-ignored),
  `scripts/runs/` (was `version4/code/logs/*.sh`), `docs/`, `archive/`.
* Paths: `DATA_ROOT` is `data/raw` (override with `CERTVER_DATA_ROOT`); `.env`
  is read from the repo root; run scripts `cd` to the repo root and set
  `PYTHONPATH=src`; training uses `${TRAIN_PYTHON:-python3}`.
* The SQL label no longer imports from version2: `_connect` and
  `_make_distilled_copy` were copied verbatim into `src/certver/spider_distill.py`
  (the label reproduces 120/120 saved labels), and the older SQL path in
  `soundver.generate._label_correct` now calls `certver.sqllabel`.
* Stored Spider database paths in data files are repo-relative; `resolve_db_path`
  rebuilds any other path from the database name.
* Check: `make_numbers.py` and `make_figures.py` reproduce all tables, macros
  and figures identically (figures compared pixel by pixel).
* Removed material is in `_trash/` (git-ignored; `_trash/MOVES.log` lists every
  move) for review before deletion.

## 7. Open items

1. Compile the paper and check it fits in 8 pages (never compiled here: no LaTeX).
2. Fill in authors in `CITATION.cff` and the paper.
3. Upload the generated data: `bash scripts/hf_upload.sh` (public data to
   rasulkhanbayov/verifier-category-deletion, CoNLL to the private
   rasulkhanbayov/verifier-category-deletion-conll).
4. Optional, paid (~$10–12): natural proposer rounds on 2–3 more datasets with
   rare categories, to test how often deletion arises (the main reviewer
   objection).
5. Optional: second seed for the 1.7B student; compile the TikZ overview.
