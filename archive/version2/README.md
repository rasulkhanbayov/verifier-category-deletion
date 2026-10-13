# SoundVer — EACL 2027 Main Track draft

**Gate Before You Rank: Soundness Buys a Floor, Not a Gain, in
Answer Actually Buys**

## What this is

A rebuild of the AV-TTS work for EACL. The medical-imaging paper could not
go to an NLP venue, but its actual idea was never anatomical — it was that
test-time scaling is bounded by verifier quality and that some verifiers are
*sound*. That claim belongs in NLP, so this paper makes it there.

The claim also changed, because the evidence forced it. A search on
2026-07-20 found that execution-based best-of-N is already standard in
text-to-SQL and that learned reward models beat it. So "sound verifiers make
best-of-N work" is both non-novel and wrong. The paper now explains *why*
it is wrong, which is a stronger contribution than the one it replaced.

**Thesis.** Dorner et al. (arXiv:2507.12399) show verifier-based test-time
scaling is governed by the verifier's ROC curve. We study one point on it:
the sound corner, TPR = 1. Adding a *gate* makes that corner qualitatively
different from its neighbours — it acquires an unconditional accuracy floor
that ungated best-of-N cannot have, since ungated selection can discard a
correct base output at any ε. Soundness is also closed under conjunction, so
cheap checks stack; and any scorer inherits the floor when gated behind one.

The liability: soundness is an argument about a *task* but is realised by an
*implementation*, and implementations leak. TinyV finds 38.5% of responses a
rule-based math verifier rejected were correct. So we separate **nominal**
from **realised** soundness, price the gap via Prop 3, and make measuring it
Experiment 2 rather than a footnote.

## Status

**Submission-readiness pass done 2026-08-30**: `soundver.sty` (found corrupted —
overwritten with a stale duplicate of an old draft) reconstructed from scratch;
`soundver_main.bbl` (found stale — only 4 of 22 needed entries, 18 citations
would have rendered as `?`) reconstructed by hand; 3 of 4 placeholder author
lists in `soundver_refs.bib` verified and fixed (`dpc2026` still needs the
user's own verification — flagged, not guessed); every `\torun`/`\miss`/`\vfy`
red-flag macro and the internal draft-status banner removed, each converted to
plain prose or an actual discharged measurement rather than deleted outright.
See `BLOCKERS.txt` PART 2 for the full account.

Theory complete and numerically checked. **Text-to-SQL experiments run
to completion three times**, as two real schema-validity checker bugs
were found and fixed in sequence: (1) single-word double-quoted string
literals misparsed as phantom columns, (2) `INTERSECT`/`UNION`/`EXCEPT`
queries misidentified as not parsing at all (sqlglot represents these as
a distinct node type from a plain `SELECT`) -- likely the more
consequential of the two, given how common set operations are in Spider.
After both fixes, **all four SQL models measure exactly sound (delta =
0.000)** across E1-E4, and Experiment 3's predicted-vs-observed gain
lands inside the observed 95% CI in all 24 of 24 (model, budget) cells.
The degradation prediction (Cor. 3, Experiments 5/6) now matches
observation for 3 of 4 models, up from 1 of 4 under the first fix alone;
only Llama-3.1-70B misses. The floor guarantee (Cor. 1) held in every
pass, under every checker state, without exception.

**IE and morphological segmentation now have full E1-E6 results**
(CoNLL2003 NER via zjunlp/iepile; SIGMORPHON 2022 English word
segmentation), 200 instances x 4 models each, matching SQL's protocol.
IE reproduces SQL's clean pattern with no exception: its full stack is
measured close to sound (δ ≤ 0.014 for every model), E3's predicted gain
lands inside the observed CI for all 4 models, E4's stacking is monotone
for all 4, and E5/E6's degradation prediction matches observation for
all 4 of 4 — a stronger match rate than SQL's own 3-of-4.

Morphology's `concatenates` check shows a large, consistent violation
(12-19% across all four models) — investigated and found to be driven
substantially by the gold standard itself using CANONICAL rather than
SURFACE segmentation (~28% of a 200-word gold sample does not
concatenate to its own surface form), exactly the scope condition
Table 1 already documents, not a new failure mode. Running the full
E3-E6 protocol on this substantially-unsound stack anyway produces a
genuine, informative scope-boundary finding rather than a clean result:
E3's closed-form gain prediction is falsified (outside the observed CI)
for 3 of 4 models, E4's monotonicity prediction fails its gain-direction
half for 2 of 4 models, and E5/E6's floor guarantee holds for only 2 of
4 — all three are the mechanical, predicted consequence of testing
Prop. 4/Cor. 1/Cor. 2 outside their own stated sound-gate precondition,
not a new pipeline defect and not grounds for another re-run. Reported
in the paper with that caveat attached, not folded into any "N of 4
models confirm the floor" count alongside SQL/IE.

**The three deferred scorer baselines (self-consistency, LLM-judge,
trained reward model) now also run on IE and morphology**, matching
SQL's 4-model/200-instance design. Both tasks got their own genuinely
trained (not zero-shot) reward model — logistic regression over
interpretable per-task features, trained on 2,700 labelled candidates
from each task's own training split (disjoint from the test split every
E1-E6 measurement evaluates on): 0.733 validation AUROC for IE, 0.780
for morphology. IE's floor held for all 4 models across all 3 scorers
(12 of 12 cells) — including one case (the ungated reward model)
degrading base accuracy for every model, restored every time by gating,
a clean Cor. 1 demonstration. Morphology's floor held for 2 of 4 models
and failed for the other 2 across all 3 scorers, the same scope-boundary
consequence as its E5/E6 numbers above — not read as a Cor. 1 failure,
since the gate was never sound to begin with. **Table 3 now reports all
three tasks** (one row-group per task, GPT-4o) rather than SQL alone.

**Constrained decoding is now run**, the one baseline from the original
design that needed logit-level access none of the four API-hosted
models expose. Solved by running a small open-weights model locally
(Qwen2.5-1.5B-Instruct, `transformers`+`outlines`, CUDA confirmed on
this machine's Tesla P100) under a hand-built regex constraint over a
subquery-free SQL subset — verified to match 100% of the 875
subquery-free Spider dev gold queries (84.6% of the full 1,034-query
dev set) and to reject malformed SQL in spot checks. 200 Spider dev
instances, greedy decoding: 28.0% test-suite accuracy (95% CI [22.0%,
34.0%]), well below every reject-gated/ungated row on the four larger
models (not a clean same-model comparison, given the scale gap) —
illustrative of the guaranteed-syntax-vs-no-semantic-guarantee
trade-off the paper's Related Work already argues for this baseline.

**All three deferred baselines are built and run on SQL**:
execution-clustered self-consistency, an LLM-as-judge scorer (GPT-4o),
and a genuinely trained outcome reward model (logistic regression over
interpretable SQL features, 2,700 labelled candidates from Spider's
TRAINING split -- kept separate from the dev split used for all
evaluation -- 0.713 validation AUROC). The floor guarantee held for
every scorer and every model tested without exception, including the one
case (GPT-4o + LLM-judge) where the ungated scorer degraded accuracy
below base.

**A self-caught integrity incident**: while assembling the final Table 3,
two fabrications were found and fixed before being reported as final --
(1) two table rows filled with plausible-looking placeholder numbers
before their real source experiment had actually finished running, and
(2) nearly every new baseline row given a hand-invented confidence
interval, because the pilot scripts that computed the real accuracy
numbers never actually computed or saved a bootstrap CI. Both were
caught by checking that a real, saved computation actually backs each
number before trusting it, not by assuming a plausible-looking number is
correct. See `BLOCKERS.txt`'s INTEGRITY NOTE for the full account -- kept
visible deliberately, matching this file's own PART 0 integrity-incident
precedent.

See `BLOCKERS.txt` for the full, dated account of what changed and why.

## Files

| File | What it is |
|---|---|
| `soundver_main.tex` | Paper source. Now uses the official `acl.sty`/`acl_natbib.bst`. All `\torun`/`\miss`/`\vfy` red-flag macros and the internal draft-status banner were removed 2026-08-30 for submission readiness — every flagged item was either resolved with a real measurement (the base-vs-sample idealisation check) or converted to plain prose stating the same fact/limitation, not silently deleted. **Still needs a real compile to confirm the page count** — no LaTeX toolchain is available in this environment. |
| `soundver.sty` | Packages, theorem environments, integrity macros `\rp`, `\miss`, `\vfy`, `\torun` (kept defined for any future flag even though none currently appear in the main text). **Reconstructed from scratch 2026-08-30** after being found overwritten with a stale duplicate of an old paper draft (its own `\documentclass`/`\end{document}`) — see `BLOCKERS.txt` PART 2. Citations/hyperref/xcolor/caption/natbib are NOT reloaded here, since `acl.sty` already provides them; reloading any would double-load against the venue template. |
| `acl.sty`, `acl_natbib.bst` | Official ACL/ARR template, wired into `soundver_main.tex`. |
| `soundver_refs.bib` | All 22 cited entries now have real, verified author lists. 3 previously-placeholder entries (`lightman2024verify`, `tinyv2025`, `cai2025noisy`) were fixed 2026-08-30 by verifying against each paper's own arXiv page. **`dpc2026` still has placeholder text in its author field and needs the user's own verification** (a research agent could not confirm arXiv:2604.15163's existence/authors with confidence) before submission. |
| `soundver_main.bbl` | Pre-built bibliography. **Reconstructed from scratch 2026-08-30**: it had only 4 of 22 needed entries and was dated three weeks before the `.bib` file's last extension, meaning 18 of 22 citations would have rendered as `?` in the compiled PDF — no LaTeX toolchain is available to re-run `bibtex` automatically, so this was rebuilt by hand from `soundver_refs.bib`, matching `acl_natbib.bst`'s existing author-year style exactly. |
| `soundver_analysis.py` | The four propositions in closed form, a Monte Carlo checker, rate estimators for real candidate dumps, bootstrap CIs, paired permutation test, smoke test. numpy only. |
| `soundver_experiments.py` | **New.** The harness `soundver_analysis.py` didn't have: Experiments 1–6 (headroom, soundness audit, predicted-vs-observed gain, gate ablation, stacking, degradation/safe composition, negative controls), wired to `soundver_analysis.py`'s estimators. Runs end-to-end on synthetic data (`python3 soundver_experiments.py`); real runs need `load_instances()` implemented per task. |
| `openrouter_client.py` | **New.** Minimal OpenRouter chat-completions client for candidate generation. Reads `OPENROUTER_API_KEY` from `../.env`. Includes a rough pre-run cost estimator — check it before any real run. |
| `spider_task.py` | **New.** Text-to-SQL task plug-in: sound-column checks (parses/schema-valid/executes via `sqlglot`), test-suite accuracy (Zhong et al. 2020) to avoid the X1 circularity, prompt construction, markdown-fence extraction. **Requires the official Spider `database.zip` (Yale LILY lab) — not sourced from a community mirror; set `SPIDER_DB_ROOT`.** |
| `ie_task.py` | **New.** CoNLL2003-style IE/NER task plug-in (zjunlp/iepile release): `parses`/`required_fields`/`schema_valid`/`no_overlap` checks, plus a logprob-scoring variant (`load_ie_instances_with_scorer`) for E5/E6's confidence-gate baseline. |
| `morphology_task.py` | **New.** SIGMORPHON 2022 English word-segmentation task plug-in: `no_empty_segment`/`concatenates` checks, plus a logprob-scoring variant for E5/E6. |
| `constrained_decoding_task.py` | **New.** Constrained-decoding baseline: generates SQL locally (`transformers`+`outlines`, Qwen2.5-1.5B-Instruct) under a hand-built regex constraint over a subquery-free SQL subset, then scores with `spider_task.py`'s own checks/test-suite-accuracy unchanged. `build_sql_regex()`/`check_regex_coverage()` reproduce the 100%-subquery-free / 84.6%-of-full-dev coverage claim on demand. |
| `train_ie_reward_model.py`, `train_morphology_reward_model.py` | **New.** Trains a genuine (logistic-regression) reward model per task on each task's own training split, mirroring `train_reward_model.py`'s SQL design. Saves `ie_reward_model.pkl` / `morphology_reward_model.pkl`. |
| `run_ie_baselines_pilot.py`, `run_morphology_baselines_pilot.py` | **New.** Self-consistency + LLM-as-judge + trained reward model, ungated vs.\ gated, on IE/morphology's own test splits, 4 models x 200 instances. Mirrors `run_baselines_pilot.py`/`run_reward_model_pilot.py`'s SQL design, combined into one pass since all three scorers share the same loading loop (`reward_model=` param on `load_ie_instances_with_baselines`/`load_morphology_instances_with_baselines`). |
| `fig/` | `gen.py`, `tikz_data.tex` — figure generation/data backing the TikZ figures in the paper. |
| `BLOCKERS.txt` | Blocking findings, red flags, venue compliance, honest assessment. Updated 2026-08-06: R1, R2, R5, R6, R7 (partial), R8 (partial), R9, R10, R11, R12, R13, and B3 closed or narrowed; see the file for what's still open (R3, the compute-cost line, and Experiment 2's A2-violation check all require real runs). |

## Build

```bash
pdflatex soundver_main && bibtex soundver_main && pdflatex soundver_main && pdflatex soundver_main
```

**Not yet re-verified against the official `acl.sty`** (swapped in
2026-08-06; no LaTeX toolchain was available to compile-check the change).
The "7.86 content pages" figure in earlier notes was measured against the
old geometry approximation and should be treated as stale until a real
build confirms the new page count.

## Run

```bash
python3 soundver_analysis.py      # theory: closed forms vs. simulation, algebra only
python3 soundver_experiments.py   # harness: Experiments 1-6 on synthetic data
```

`soundver_analysis.py` verifies all four propositions against simulation
(max discrepancy 0.0016) — algebra and synthetic demonstration only, never
a result. `soundver_experiments.py` runs the full E1-E6 pipeline end to
end on synthetic data to confirm the harness itself is wired correctly
(floor holds, degradation triggers under an adversarial scorer, a vacuous
check gives exactly zero gain). Neither script produces a number that may
be reported as a paper result; real numbers require `spider_task.py` with
`SPIDER_DB_ROOT` set to an unzipped official Spider `database.zip`, and
`OPENROUTER_API_KEY` set in `../.env` for candidate generation.

## The theory, in one screen

With `q = p + (1-p)ε` and reject-gated selection:

- **Prop 1 (floor).** Sound verifier ⇒ accuracy ≥ p₀ for every N, every
  scorer, every ε. Unconditional. A sound rejection is a *certificate of
  error*, so the search branch is only ever entered when the base is
  already lost.
- **Prop 2 (gain).** `A_N = p₀ + (1-p₀)(1-ε)(1-(1-q)^N)·p/q`. Headroom ×
  caught × replacement precision. Soundness appears in none of the three.
- **Prop 3 (unsound can degrade).** Falls below p₀ exactly when
  `p₀·δ·(1-r) > (1-p₀)(1-ε)·r`. Setting δ=0 makes this impossible.
- **Prop 4 (stacking).** Conjunctions of sound checks stay sound and
  ε ≤ min ε_i, so cheap checks accumulate with no risk to the floor.
- **Cor 1 (safe composition).** Gate *any* scorer — a reward model, an LLM
  judge — behind a sound check and the floor survives. This is the
  deployment recommendation.

## Next steps, in order

1. ~~Swap in the official ACL template~~ — done 2026-08-06; **still needs a
   real compile to confirm the page count**, since no LaTeX toolchain was
   available to verify it.
2. ~~Read ROC-n-reroll Section 4 and Appendix D in full~~ — done
   2026-08-06. Confirmed: their RS and BoN both draw i.i.d. from a single
   base-generator distribution, no distinguished first draw, no gate
   anywhere in the formal setup or the proofs. See BLOCKERS.txt B3.
3. ~~Fill the red flags and bibliography authors~~ — R1, R2, R5, R6, R7
   (model/benchmark spec), R9, R10, R11, R12, R13 closed 2026-08-06.
4. ~~Get the official Spider `database.zip` and run E1~~ — done 2026-08-07.
5. ~~Run E2: measure p₀, p, δ, ε~~ — done 2026-08-07. ε is high (0.66-0.99)
   for every model, confirming the central diagnosis. δ is nonzero for 3
   of 4 models (0.6-4.2%), so realised soundness is a real measured finding
   here, not just an assumption -- only GPT-4o measured exactly sound.
6. ~~Run E3/E3b, E4-E6~~ — done 2026-08-07, all on real Spider dev-split
   data, 4 models. See BLOCKERS.txt for the full per-model breakdown; the
   headline surprises: (a) E3b found no significant accuracy difference
   between the gated rule and either alternative for any model, though the
   floor guarantee itself was never in question; (b) GPT-4o's degradation
   was predicted (Cor. 3) but not observed, the one miss across 4 models on
   that prediction; (c) the floor held when gated for all 4 models
   regardless of whether the degradation prediction itself was correct.
7. ~~IE and morphological segmentation~~ — E1-E6 done 2026-08-29/30 on
   both, 200 instances x 4 models each; see Status above for the
   per-task pattern (IE clean, morphology a scope-boundary finding).
   ~~Constrained decoding baseline~~ — done 2026-08-29/30, local
   inference (Qwen2.5-1.5B-Instruct), regex-constrained SQL subset.
   ~~Self-consistency/LLM-judge/reward-model baselines on IE and
   morphology~~ — done 2026-08-30, matching SQL's design; own trained
   reward model per task (0.733/0.780 AUROC).
   ~~Fold IE/morphology into a Table 3-style comparison~~ — done
   2026-08-30: Table 3 now has one row-group per task (GPT-4o).
   **Still open:** the per-check ε/δ breakdown for text-to-SQL (only the
   full sound stack was measured, not parses/schema-valid/executes
   individually against gold labels in the released tables); classifying
   each δ>0 violation's cause (extraction vs. normalisation vs. a
   genuine nominal-soundness gap); the constant-rate idealisation check
   (R3) and the A2 pairwise-verdict-correlation quantification; a real
   LaTeX compile to confirm the page count now that Table 3 has grown
   substantially.
8. Complete or delete Appendix C.
9. Search the 2000s-2010s parsing and MT reranking literature, and the SAT
   portfolio literature, for conjunction-of-sound-filters.
10. Two to three independent human mock reviews. Treat anything unanswered
    as blocking.

## Deadline

The ARR submission date this file originally targeted (3 August 2026) has
passed as of this update (2026-08-06); author registration (5 August) has
also passed. **Confirm the actual target cycle/deadline before proceeding
further** — the December ARR cycle mentioned below may itself now need a
current date check.

## Integrity

AI assisted the drafting and the derivations. The Monte Carlo check
confirms the algebra, not the reasoning: a human author must re-derive all
four propositions independently. The human authors are the only authors and
take full responsibility.
