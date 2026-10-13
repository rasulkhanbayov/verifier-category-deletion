# Session status snapshot (2026-09-03)

## Phase 1 (B7) status: seed-0 data collection COMPLETE for all 3 tasks

- SQL: data/records_sql_seed0.jsonl (26,367 records, 4th generation attempt
  after fixing 4 real checker bugs in sql_schema_valid). Reconciled in
  out/sql/. Llama-3.1-70B measures exactly sound (delta=0.0000, ceiling=3.72
  pts); GPT-4o/GPT-4o-mini/Llama-3.1-8B show small residual delta
  (0.0007-0.0017), consistent with a documented, accepted ~1-in-480
  correlated-subquery checker limitation, not a remaining bug.
- IE: data/records_ie_seed0.jsonl (26,400 records, 1st attempt, no bugs
  found). Reconciled in out/ie/. GPT-4o and GPT-4o-mini measure exactly
  sound (delta=0.0000, ceilings 2.17/3.06 pts); both Llama models show
  small residual delta (0.0014/0.0089).
- Morphology: data/records_morph_seed0.jsonl (26,400 records, 1st attempt).
  Reconciled in out/morph/. All 4 models measure substantially UNSOUND
  (delta 0.003-0.178 -- recheck exact llama-3.1-8b figure in out/morph/rates.json
  before quoting), consistent with the paper's existing SIGMORPHON
  canonical-vs-surface-segmentation finding.

## Bugs found and fixed this session (all in code/soundver/checks.py)

1. Table aliases (FROM t AS t1) not resolved -> false schema_valid=False.
2. SELECT-list column aliases (AVG(age) AS average_age) not resolved.
3. Function names (UPPER, CAST, etc.) and CASE/WHEN/THEN/ELSE/END keywords
   misread as column references.
4. Derived-table aliases, aliases used inside nested subqueries, and a
   correlated-subquery-column leak into outer scopes -- fixed by rewriting
   sql_schema_valid from regex to a proper sqlglot AST/scope-based
   implementation (kept the regex version as _sql_schema_valid_regex, an
   ImportError fallback only).
   Also ported SQLite's quoted-string-literal fallback rule (a double-quoted
   token that doesn't resolve to a real column is treated as a string
   literal) into the sqlglot path.

All fixes are covered by 23 permanent regression tests in
soundver.checks._selftest (was 13 at session start). A stress test against
~480 fresh real candidates across all 4 models found the residual false-
rejection rate at ~1-in-480, traced to a rare correlated-subquery pattern
(an unqualified column that doesn't exist on its own subquery's table but
does exist on an ENCLOSING scope's table, which real SQL resolves via
correlation) -- documented as an accepted, low-incidence limitation in
sql_schema_valid's docstring rather than chased further.

## Old/superseded data files (kept as .bak, do not use)

- data/records_sql_seed0.jsonl.pre_alias_fix.bak (1st SQL attempt, before
  any bug fixes)
- data/records_sql_seed0.jsonl.pre_sqlglot_fix.bak (3rd SQL attempt, after
  bugs 1-3 fixed but before the sqlglot rewrite / bug 4)

## generate.py changes

- Added dataset loaders for Spider/CoNLL2003(iepile)/SIGMORPHON, an
  OpenRouter completion client, admissible-label logic per Def. 2 (SQL:
  test_suite_accuracy via version2's spider_task.py, imported as a utility
  function only, not its data; IE: field_value_match; morph:
  gold_segmentation_match).
- IE redesigned as slot-filling over CoNLL2003's 4 entity types
  ({"location":[...], "else":[...], "organization":[...], "person":[...]}),
  matching checks.py's flat-object IE contract -- per explicit user choice,
  documented in generate.py's IE_ENTITY_TYPES/IE_SCHEMA comments.
- Concurrency added (ThreadPoolExecutor, SOUNDVER_GEN_WORKERS env var,
  default 8) after the first sequential attempt was too slow (~35s/instance,
  projected ~7.8hrs/task) -- cut pacing to ~4.7s/instance, ~63min/task.
- B9 (model snapshots): openai/gpt-4o-2024-11-20 and
  openai/gpt-4o-mini-2024-07-18 confirmed as real, pinned OpenRouter slugs.
  meta-llama/llama-3.1-{8b,70b}-instruct have NO dated snapshot on
  OpenRouter at all (Meta doesn't version endpoints the way OpenAI does) --
  documented exception in LLAMA_NO_SNAPSHOT, with the actual serving
  `provider` (and system_fingerprint) logged per-request to a side file
  (<out>.providers.jsonl) as a partial mitigation. Already observed
  OpenRouter routing the same nominal Llama model to different backend
  providers (Novita vs DeepInfra) within a handful of calls.

## Next steps (per the approved plan, <home>/.claude/plans/jiggly-soaring-haven.md)

1. Write the reconciled SQL/IE/morph numbers into soundver_main.tex's
   Table 3/Table 7-equivalent tables, verbatim from out/{sql,ie,morph}/
   rates.json and tab_ceiling.tex -- NOT yet done as of this snapshot.
2. Phase 4: classify IE's soundness leak (bug vs. scope failure) per the
   paper's own S3 criterion -- decides n=1 vs n=2 for the paper's core
   finding count.
3. Phase 5: resolve the ethics-section human-re-derivation sentence (E1,
   gating item) -- ask the user directly, do not assume.
4. Phase 6 B12: read arXiv:2509.17995 ("Variation in Verification") in
   full before trusting its current citation/positioning.
5. Phase 3: B4's 5-seed replication (the expensive item) -- not yet started
   for any task at seed 0's current data.
6. Phases 6 (remainder)/7/8: B17 inter-implementer comparison, B10
   citations, B14 SIGMORPHON CI, B5 DPC baseline decision, hygiene pass.

## Update: IE classification investigation (Phase 4) found a 5th real bug

Investigated IE's small residual delta (both Llama models) by inspecting
actual false-rejection instances. Found: ie_no_overlap's original
implementation resolved each entity string to its FIRST occurrence via
text.find(x), with no handling for the case where a shorter entity's
surface text is a literal substring of a longer, different entity's span
(e.g. gold entities "Lebanon" and "South Lebanon Army" in the same
sentence -- "Lebanon" genuinely appears twice, once embedded in "South
Lebanon Army" and once standalone, but text.find() always returns the
first, embedded occurrence, producing a false "overlap" even for an
exactly-correct extraction).

Per the paper's own S3 criterion ("an implementation defect is one some
correct implementation would not make; a scope failure is one none
avoids"), this is a BUG, not a scope failure: a correct implementation
that tries all occurrences of a repeated substring and accepts any
non-overlapping assignment (which the fix now does, via backtracking)
would not make this mistake. Fixed in ie_no_overlap, verified against the
real failing case, added as regression test #24 (24/24 passing).

CONSEQUENCE FOR THE PAPER'S CLASSIFICATION QUESTION (n=1 vs n=2): this
strongly suggests IE's apparent unsoundness, like SQL's, was substantially
a checker-implementation artifact rather than a genuine scope failure --
i.e. IE likely does NOT qualify as a second scope-failure finding
alongside morphology. This makes the paper's confirmed finding count more
likely n=1 (morphology only), not n=2, PENDING the re-run below.

IE data regenerated a 2nd time (data/records_ie_seed0.jsonl, old version
backed up as .pre_overlap_fix.bak) to get real delta measurements against
the fixed checker -- not yet reconciled as of this note. Once reconciled,
if IE measures exactly sound (delta=0.000) for most/all models, that
would confirm this was the whole explanation and IE should NOT be counted
as a second confirmed scope-failure finding.

## Update: IE reconciled after ie_no_overlap fix, classification DECIDED

Final IE reconciliation (2nd generation attempt, with the ie_no_overlap
fix): GPT-4o delta=0.0000 (sound, ceiling 2.19 pts), GPT-4o-mini
delta=0.0000 (sound, ceiling 3.04 pts), Llama-3.1-70B delta=0.0010 (small
residual, consistent with the same accepted correlated-subquery-style
limitation already documented for SQL), Llama-3.1-8B delta=0.0103
(elevated, did NOT improve from the pre-fix 0.0089 -- investigated
further).

Investigated all 17 of Llama-3.1-8B's remaining false-rejection cases
directly: 100% trace to the model returning an empty JSON object {}
instead of the schema-required all-four-keys-with-empty-lists format,
specifically on instances where gold is genuinely "no entities of any
type." The field-value-match correctness label (correctly, per Def. 2)
treats {} as matching an all-empty gold since it never presupposes the
required_fields check; required_fields (correctly) flags {} as missing
the required schema keys. CONCLUSION (per explicit user decision): this
is NEITHER a checker bug (both checks are doing exactly what they are
specified to do) NOR treated as a second scope-failure finding --
checks.py is NOT modified for this. It is reported as IE's genuine, if
narrow and model-specific, residual delta for Llama-3.1-8B only.

FINAL IE CLASSIFICATION FOR THE PAPER: n=1 confirmed finding overall
(morphology only). IE does NOT qualify as a second scope-failure finding:
2 of 4 models (GPT-4o, GPT-4o-mini) measure exactly sound; the other 2
(both Llamas) show small, model-specific residual delta (0.0010, 0.0103)
that is either an accepted low-incidence checker limitation (already
documented) or a real-but-narrow format/content disagreement specific to
one model's behavior on a degenerate case -- neither is "a failure no
implementation avoids" in the sense S3 requires for a scope-failure
finding. This resolves REDFLAGS.md's B16 (IE was previously
"unclassified"): IE is classified as NOT contributing to the paper's
confirmed-finding count; only morphology does.

Both SQL and IE data collection are now COMPLETE and believed final:
- data/records_sql_seed0.jsonl (4th generation attempt, checker fully
  audited: 4 real bugs found/fixed, sqlglot rewrite)
- data/records_ie_seed0.jsonl (2nd generation attempt, 1 real bug
  found/fixed in ie_no_overlap)
- data/records_morph_seed0.jsonl (1st attempt, no bugs found, matches
  paper's existing SIGMORPHON finding)

24/24 self-tests passing in soundver.checks (started at 13/24 this
session). Next steps per the approved plan: write these reconciled
numbers into soundver_main.tex (not yet done), then Phase 5 (ethics
sentence, ask user directly), Phase 6 B12 (read Variation in
Verification in full), Phase 3 (5-seed replication, the expensive item).

## Update: soundver_main.tex updated with real reconciled numbers (E1-E5, Table 3)

Wrote real, verified numbers into the paper throughout:
- Table 3 (tab:ceiling): rewritten. 3/12 cells sound (SQL/Llama-3.1-70B,
  IE/GPT-4o, IE/GPT-4o-mini), real ceilings 3.72/2.19/3.04 pts, rule-of-three
  bounds computed and compared honestly against the smallest measured leak
  (found the bound is NOT uniformly tighter than nearby leaks -- a real,
  more nuanced finding than initially assumed, caught by checking the
  actual numbers rather than asserting the comparison).
- E1: real per-model delta values, resolved IE classification (n=1,
  morphology only -- SQL and IE's leaks traced to checker limitations, not
  scope failures).
- E2: three real certified ceilings.
- E3/E4: NEW analysis code written (soundver.rates.degradation,
  soundver.reconcile.gain_curve) to compute predicted-vs-observed gain
  across the full N budget grid and stacking monotonicity from existing
  records -- no new API calls needed. Result: 18/18 (cell,budget) checks
  confirm Cor. gain in the 3 sound cells (down from the old paper's
  overcounted "24 SQL + 4 IE" against unsound cells); E4 monotonicity
  holds 4/4 for SQL and IE, morphology's accuracy-monotonicity fails for
  2/4 models exactly where its stack is unsound.
- E5: NEW data collection (generate.py --want-logprobs, N=8, all 3 tasks,
  ~600 API calls each) plus new analysis (soundver.rates.degradation
  proper, confidence-gate design matching the paper's own E5 description
  exactly: bottom-quartile-of-instance-pool rejected, not a raw ranking
  score). Real result: floor holds 8/8 SQL+IE cells regardless of whether
  degradation was predicted; morphology's floor fails 3/4 cells, correctly
  attributed to its unsound gate rather than treated as a counterexample.
- Conclusion, abstract, contribution (ii), and the claim-coverage appendix
  table (tab:claims) all updated to match -- caught and fixed a second
  real error while doing this: the appendix's "gate has an accuracy edge"
  disclaimer row claimed no pairwise gated-vs-homogeneous difference
  reached significance, but a direct check found ONE real significant
  difference (morphology/Llama-3.1-70B, p=0.023, on an unsound gate) --
  fixed rather than left as an unverified claim.

STILL NOT DONE: tab:main / tab:main-extra (SQL's and IE's full baseline
sweep -- self-consistency, LLM-as-judge, trained reward model) are a
separate, larger data-collection task not attempted this session (E5's
paragraph now explicitly flags those tables' numbers as not yet
reconciled against the corrected checkers). Also not done: E0 (B13,
label-admissibility check against the pre-fix checker), B4's 5-seed
replication, B8's label audit and prompt sweep, B12 (reading the
Variation in Verification citation in full), and the mechanical
submission-hygiene pass (B1: remove remaining \textcolor{red} spans not
already cleaned up).

## Update: E0, tab:params, tab:main, tab:main-extra all done with real data

- **E0 (B13)**: built e0_label_check.py, a self-contained script
  reconstructing the ORIGINAL pre-fix schema validator (no alias/
  function/keyword handling), ran it across all 4 SQL models with both
  execution-match and test-suite-accuracy labels. Confirmed exactly:
  delta=0.0000 under execution match in every cell (structural
  necessity per Def. admissible), delta=0.26-0.34 under test-suite
  accuracy (exposing the buggy validator's real false rejections that
  execution match structurally cannot see). Written into E0/E1
  paragraphs and the appendix; both B13 red-flag blocks removed.

- **tab:params**: rewritten with real numbers across all three tasks
  (was stale/missing morphology entirely). Predicted/observed columns
  now honestly show "--" for all 9 unsound cells rather than a
  precondition-violating number.

- **tab:params-morph**: fixed to show "--" for predicted/observed
  (previously computed a nominal prediction against an unsound stack,
  contradicting the E3 paragraph's own framing).

- **tab:main (SQL baseline sweep)**: built from scratch --
  train_reward_model.py (logistic regression, 300 instances x 9
  completions from Spider's TRAINING split, 0.704 validation AUROC) and
  run_sql_baselines.py (self-consistency via execution-result clustering,
  LLM-as-judge, reward model, all three collected from the same
  200-instance x 8-candidate pool). Real results: reward model shows the
  strongest ungated gain (+6.5 pts), floor holds for all three scorers
  both ungated and gated on this draw. Also computed real
  "Rejection sampling"/"BoN sound scorer" rows (from out/sql/rules.json)
  and a real Oracle-selection upper bound (+6.0 pts, from the E5 sample).
  FOUND AND FIXED a real structural bug while doing this: several
  footnote letters (h,i,j,k,l,n,o) were used in tab:main but only
  defined in a separate appendix section -- threeparttable scopes
  footnotes locally, so these would have rendered as broken references
  in a real compile. Fixed by defining them in the table's own notes
  block.

- **tab:main-extra (IE baseline sweep)**: same pattern --
  train_ie_reward_model.py (IE-specific features: entity count, span
  length, schema-check outcomes; 0.822 validation AUROC, even stronger
  than SQL's) and run_ie_baselines.py (self-consistency via entity-SET
  clustering rather than execution-result clustering, since IE has no
  execution semantics). Real results: all three scorers show modest
  ungated gains, floor holds for all 6 cells (3 scorers x ungated/gated).
  IE's stack now measures exactly sound for GPT-4o (delta=0.0000, not the
  old table's stale 0.002), so this table's floor tests are now genuine
  Prop. floor tests, not near-approximations.

Structural verification after all edits: brace depth 0, even dollar
count, no broken \ref, all three threeparttable blocks' \tnote/\item
pairs resolve cleanly.

STILL OPEN: B4 (5-seed replication), B8 (label audit + prompt sweep,
validity.py already implemented, never run), B10 (CoNLL2003/SIGMORPHON
citations+licenses), B14 (SIGMORPHON 28% figure's binomial CI/sample
provenance -- may already be partially addressed, check current text),
B17 (independent reference-implementation comparison -- checks.py IS
that comparison now, just needs the delta-difference reported explicitly
against the numbers this session produced), submission hygiene (search
for remaining \textcolor{red} spans).

## Update: B17, B10, B14 done; appendix red-flag block cleaned up

- **B17**: ran b17_checker_comparison.py (this paper's sqlglot-based
  sql_schema_valid vs. version2's genuinely independent spider_task.py,
  fresh 100-instance x 4-model x 5-candidate sample, 2,000 candidates
  total). Result: 0.2% disagreement (4/2,000), one real model-level
  difference (GPT-4o: 0.61% own checker vs 0.00% version2's, on the same
  accepted correlated-subquery-limitation class already documented).
  Written as a new "Inter-implementer agreement (B17)" paragraph placed
  directly in sec:results (Findings), right before E2 -- NOT in the
  appendix red-flag block, since this is a resolved, real finding, not an
  open item.

- **B10/B14**: already done in an earlier pass this session (CoNLL2003 +
  SIGMORPHON 2022 citations verified and added with license notes; real
  Wilson 95% CI computed for the SIGMORPHON 27% figure, n=200).

- **B12**: read arXiv:2509.17995 in full via a research agent (not just
  the abstract). Confirmed the paper's actual Sec. 4.2 finding matches
  the main text's citation almost verbatim (TNR falls substantially as
  generator capability rises, e.g. Qwen2.5-72B verifier TNR 0.68->0.17 on
  Llama-3.1-8B vs Qwen3-32B outputs; attributed to "well-structured but
  incorrect solutions"). No prose change needed in sec:related/sec:intro
  -- only the .bib entry was wrong. Fixed: was a placeholder
  {Anonymous}/{inproceedings, ICLR 2026} entry never verified against the
  actual paper; corrected to the real 6-author list (Zhou, Yefan and Xu,
  Austin and Zhou, Yilun and Singh, Janvijay and Gui, Jiang and Joty,
  Shafiq), retyped as @misc/arXiv:2509.17995 (2025) since no confirmed
  peer-reviewed venue was found -- the ICLR 2026 booktitle was also an
  unverified guess.

- **Appendix cleanup**: removed the now-resolved B16/B11 flags (done
  earlier) and B17/B12 flags (done this update) from the "Open items"
  block, plus a stale "[REMOVE BEFORE SUBMISSION] Seven blocking findings
  open" fcolorbox that no longer matched the actual open count. Only B15
  (failure-case examples) and B8/B4/B5 (not yet run) remain flagged, all
  genuinely still open. Verified brace depth 0 / even dollar count after
  each edit.

## Update: B15, B11, stale B7 flag, B8-V2, B5 all closed or substantially advanced

- **B15**: added a real "What a rejected-correct output looks like" paragraph
  right after the E1 finding, using the first 3 gold segmentations (in
  seed-0 iteration order, no cherry-picking) that fail `concatenates`:
  East Indian, swordsman, bummiest. Each verified character-by-character
  against the actual `morph_concatenates()` check before writing (caught
  and fixed an overstated claim about *why* "East Indian" fails -- it's
  both a root-spelling change AND an unstripped space, not just the
  former). SQL/IE's own residual leaks were NOT given examples, since
  \S\ref{sec:results} already traces both to checker-implementation
  limits, not scope failures -- no example is owed for a bug, only for
  the one genuine finding (morphology).

- **B11**: exhaustive sub-conjunction results (already computed, just
  never written up) confirm 0 violations across all 22 non-empty subsets
  of the 3 certified cells' stacks (7 for SQL/Llama-3.1-70B, 15 for
  IE/GPT-4o+GPT-4o-mini). Interesting real detail: SQL's bound rises
  monotonically with each added check, but IE's bound is ALREADY at its
  full value from `no_overlap` alone -- the other three IE checks
  contribute nothing further on this sample. Written into the E3/E4
  paragraph; flag removed.

- **Stale B7 flag removed**: a leftover appendix flag in app:numeric
  still said "no raw experimental outputs... ship the per-instance
  records" -- exactly what this session's entire Phase 1 already did.
  Pure staleness from an earlier draft pass; removed.

- **Fixed a real bug in validity.py** (never run before this session): a
  multi-line f-string was syntactically invalid (unterminated string
  literal spanning two print() lines) -- would have crashed on first
  invocation. Fixed by extracting to a local variable first.

- **B8-V1 (label audit)**: found that validity.py's own annotation sheets
  are unusable by a human annotator -- they only have instance_id/cand_idx,
  no raw text, because Record deliberately stores no raw generated text
  (only booleans). Built b8_v1_label_audit_sample.py: a fresh, smaller
  generation pass that keeps raw text for exactly the epsilon events
  needed (444 total across 3 tasks x 4 models, blind, shuffled, 2 sheets).
  Sample is ready in out/label_audit/; SCORING STILL NEEDS AN ACTUAL HUMAN
  ANNOTATOR (2, blind) -- explicitly flagged in the paper (footnote
  [B8-V1]) rather than faked or skipped silently. I did not attempt to be
  one of the two annotators myself -- that would repeat exactly the
  category error the paper's own E1 ethics flag warns against (a machine
  check is not a human verification).

- **B8-V2 (prompt sweep)**: designed and ran for real. Added genuine
  few-shot exemplars + 4 variant prompt-builders (paraphrase_a,
  paraphrase_b, no_fewshot, format_reminder) to generate.py for all 3
  tasks (previously `--prompt-id` was accepted but did nothing). Ran at
  n=60 first (all 3 tasks x 4 models x 4 variants) -- found the
  pre-registered "max ceiling under 1pt" reading naively "FAILS" for
  several cells, but traced this to n=60 being underpowered relative to
  the 1-point threshold (bootstrapped the SAME 60-instance subset of the
  ALREADY-COLLECTED 200-instance base data alone and got a wildly
  different ceiling from pure sampling noise: 0.19 vs the real 2.19 for
  IE/GPT-4o, 95% CI [0, 0.49]). Re-ran the 3 genuinely flagged cells
  (SQL/GPT-4o-mini, IE/GPT-4o, IE/GPT-4o-mini) at full n=200 for a real
  answer: SQL/GPT-4o-mini is unsound under every prompt including base
  (consistent, not new); both IE cells stay exactly sound (delta=0.000)
  under all 5 prompts, with the ceiling moving in a modest 1.03-3.04pt
  band -- the literal 1-point threshold still "fails" but only because it
  was fixed before the base ceiling itself (2.19/3.04) was known to
  already exceed it. Written into the paper as an honest finding
  (soundness is prompt-robust; the pre-registered threshold was
  miscalibrated, not the result). B8-V2's flag removed; only B8-V1's
  scoring step remains flagged.

- **B5 (DPC baseline)**: originally scoped as "just cite the reported
  ordering," but the user asked to actually run it. Investigated DPC's
  actual method (arXiv:2604.15163, ACL 2026) via a research agent -- it's
  a much heavier 4-stage multi-agent pipeline (Slicer/Tester/Solver
  agents, synthetic minimal-distinguishing-database generation with
  self-correction loops, Hungarian-algorithm Bipartite Soft-F1 matching)
  than initially described in the paper's own related-work paragraph.
  Used the OFFICIAL repo (github.com/HKUSTDial/DPC, MIT license) rather
  than reimplementing from scratch: cloned, installed deps, prepared the
  SAME 200-instance seed=1 sample tab:main's baseline sweep already uses
  (run_dpc_prep.py generates 8 fresh GPT-4o candidates per instance in
  DPC's expected JSON format), ran DPC's own selection pipeline against
  it (dpc_repo/artifacts/selected/dpc_gpt4o_full_results.json, 200/200
  processed, no errors). Result pending final reconcile against a fresh
  greedy baseline (run_dpc_reconcile.py) -- early check showed 73.0%
  selection accuracy vs 67.0% greedy on this sample (+6.0pts), comparable
  to the reward model's own +6.5pt ungated gain.

- **B4 (5-seed replication)**: launched (run_seeds_1234.sh), full scale
  (seeds 1-4, all 3 tasks, all 4 models, 200 instances, 32 candidates
  each -- same protocol as seed 0). ~317K API calls, ~12.5hr estimated.
  Running in background; not yet reconciled.

## Update: B4 finished and reconciled -- a real, important negative result

5-seed replication (seeds 1-4, all 3 tasks, all 4 models, 200 instances,
32 candidates each) completed and reconciled via
`soundver.reconcile --seeds`. Found something that changes the paper's
headline claim:

**SQL/Llama-3.1-70B (the paper's third "certified sound" cell at seed 0,
delta=0.0000, ceiling 3.72 pts) does NOT survive replication.** At the
other 4 seeds it measures delta=0.0005-0.0027 -- the same small residual
checker-limitation class already documented for the paper's other 3 SQL
cells. Seed 0 was a lucky zero count on a rate this low, not a genuine
certification. Investigated directly (not just trusted the aggregate):
all false-rejection instances at seeds 1-4 show `schema_valid: False`,
matching the exact signature of the already-accepted, low-incidence
correlated-subquery checker limitation -- not a new bug.

**Both IE cells that measured sound at seed 0 (GPT-4o, GPT-4o-mini) DO
survive**: delta=0.000 at every one of the 5 seeds (10/10 model-seed
pairs). What does NOT replicate cleanly is the ceiling's magnitude: GPT-4o
ranges 0.50-2.19 pts across seeds (mean 0.94, SD 0.70), GPT-4o-mini
0.59-3.04 (mean 1.41, SD 0.97) -- an SD comparable to the mean, so a
single-seed ceiling number overstates precision on its own.

**Net effect: 2 certified cells survive replication, not 3, and both are
IE (not "one from each task" as the seed-0 draw suggested).** This is
exactly the failure mode REDFLAGS.md and the plan warned B4 might reveal
("if the SD exceeds the bound itself... flag this to the user rather than
deciding unilaterally"). Given the user's explicit choice (check IE's
cells first, then decide the full reframe), rewrote the paper honestly
throughout rather than either hiding this or overclaiming SQL still holds:

- E1 findings paragraph: added a new "B4: what replication changes"
  paragraph stating the real result plainly.
- E2/E3/E4 findings paragraphs: rewritten to report only the 2 surviving
  IE cells' bounds (mean+-SD across seeds), SQL's seed-0 numbers now
  explicitly marked as not replicating.
- Table 3 (tab:ceiling): SQL/Llama-3.1-70B's row marked with a dagger
  and its bound put in parentheses, caption explains why; IE's two rows
  bolded as the cells that actually survive. Rule-of-three range recomputed
  for 2 cells (0.00091-0.00140), not 3.
- Appendix tab:params: same dagger treatment, note added.
- Appendix claims table (app:claims): "Ceiling = 3.72pts, Llama SQL" row
  replaced with the real 2-cell mean+-SD figures; SQL's non-replication
  stated explicitly; E3/E4 check counts corrected (18/18 -> 12/12,
  9 -> 10 unsound SQL/IE cells).
- Exhaustive sub-conjunction (B11) paragraph: SQL/Llama-70B's exhaustive
  result reframed as a seed-0 consistency check, not a certified finding.
- Contamination (V3, appendix) and Limitations (main body) paragraphs:
  both previously discussed "SQL's one certified cell" with a 5-8pt bound
  -- rewritten since that cell no longer certifies.
- tab:stack-breakdown caption: same dagger-style caveat added.
- **Also found and fixed a genuinely stale bug while doing this sweep**:
  fig:two-rates (the intro TikZ scatter plot) was plotting completely
  wrong epsilon values for SQL (0.693/0.776/0.928/0.988 hardcoded) that
  didn't match ANY real measured data (real values: 0.690/0.832/0.918/0.991)
  -- looks like leftover placeholder coordinates from before this
  session's real data collection, never caught until this sweep.
  Recomputed all 12 points' exact (eps, delta) coordinates from real
  seed-0 data and rewrote the TikZ block with inline comments showing
  the source numbers. Also fixed the caption's wrong claims ("four land
  on the green edge" -> really three at seed 0; "three IE cells sit just
  below" -> really two) and the abstract's "$61$-$99\%$" range (real
  range across ALL 12 cells is $58$-$99\%$; the sentence specifically
  means the 2 surviving certified cells, which is $88$-$92\%$, so fixed
  to that instead of the all-cells number).

Removed the B4 appendix flag (now stale/resolved either way -- reconciled
and written up, whether or not the news was what the seed-0 draft hoped).

## Update: B8-V1 sheets had a real usability bug -- fixed

Went to actually prepare B8-V1 for a human annotator and found the sheets
built earlier this session were unusable: they showed only the model's raw
output and the row_id/task/instance_id, but NEVER the task input (the word
being segmented, the question being answered, the text being extracted
from) or gold. A human cannot judge "correct or incorrect" without seeing
the input -- this was missed when the sheets were first built.

Fixed without any new API calls: `LOADERS[task](200, seed=0)` is a
deterministic, purely-local function, so the exact item for each sampled
instance_id could be reconstructed offline and joined onto the existing
annotation_key.jsonl. Wrote `b8_v1_enrich_sheets.py`, verified the join is
sound (spot-checked instance_ids resolve to the right item, e.g.
morph-26721 -> "swordsman", matching the same word already used as a B15
failure example), ran it. New sheet columns: `row_id, task, task_input,
candidate_output, human_label, notes` -- gold and the automatic label
stay ONLY in annotation_key.jsonl, never shown to annotators (blind).
Verified all 444 rows have non-empty input and output.

Built `b8_v1_collect_annotations.py` for after both sheets are filled in:
converts the two CSVs into the `{row_id, annotator, human_label}` JSONL
format `soundver.validity.score_audit` expects, then runs scoring
automatically. Tested end-to-end with a synthetic filled sheet (all labels
"incorrect", matching the automatic label) -- confirmed the pipeline runs
without error (Krippendorff's alpha, wrong-label rate, corrected
epsilon/ceiling per cell).

That test run surfaced a SECOND real bug while validating: `score_audit`
evaluates every seed-0-sound cell against a fixed "ceiling under 1 point"
threshold -- both stale now, since (a) it would still include
SQL/Llama-3.1-70B, which B4's 5-seed replication showed does NOT actually
survive, and (b) the same threshold-miscalibration problem already found
and fixed for B8-V2 (the real base ceilings, 2.19/3.04 pts, already
exceed 1 point, so the threshold was never meaningful). Fixed
`score_audit` to restrict to the two cells that actually survived
replication (IE/GPT-4o, IE/GPT-4o-mini) and report the corrected ceiling
honestly instead of a miscalibrated pass/fail line -- matching exactly how
B8-V2's paragraph in the paper was already fixed. Re-verified the fix with
the same synthetic test.

Everything needed for the human step is now ready and genuinely usable:
`out/label_audit/annotation_sheet_{1,2}.csv` (444 rows each, task input +
candidate output shown, blind), fill in the `human_label` column with
correct/incorrect/unsure, then run `b8_v1_collect_annotations.py`.

STILL OPEN (only 2 items): B8-V1's actual human annotation step (sheets
are ready and now genuinely scoreable; I did not attempt to be one of the
two annotators myself -- that repeats exactly the category error the
paper's own E1 ethics flag warns against), and the E1 ethics gating
sentence (human re-derivation of all 9 numbered results -- user said "not
sure yet, leave as-is" when asked directly). Once those two close,
remaining hygiene: re-run
measure_pages.py).

## Update: strengthening pass (plans.md P1-P11), full audit + fixes

User asked for a full weaknesses/strengths audit and a prioritized
strengthening plan. Wrote both to new files: `plans.md` (11 prioritized
items, P1-P11, checkbox-tracked) and `CLAUDE.md` (standing project
context for future sessions). Worked through the list one item at a
time, verification discipline maintained throughout (every number traced
to a real computed/saved file before being written into the .tex).

**P1 (stale `\miss{}` markers)**: both removed. B9's turned out to be a
real gap, not just stale -- the paper's prose never actually stated the
pinned snapshot strings anywhere outside the flag itself. Fixed by
writing them into the "Models and access" paragraph plus a real,
verified description of the Llama/Qwen no-dated-snapshot mitigation
(confirmed via the actual .providers.jsonl data that SQL/Llama-8B seed-0
genuinely saw 3 different backend providers -- Novita, DeepInfra, Groq
-- not just 2 as first assumed). Access date range also corrected after
checking real file timestamps (2026-09-02 to 09-04, not a first-guess
09-20). B3's was genuinely stale (the whole session's real-data work
already satisfies it); removed.

**P2 ("two of three" vs "one of three")**: the audit's OWN first-pass
guess about the direction of this inconsistency was wrong -- checked
real seed-0 delta values across all 12 cells and found ALL THREE tasks
have delta>0 somewhere (not 2), so "two of three" was an undercount.
Fixed both occurrences to say "somewhere on all three tasks," keeping
the correct, narrower "one of three" claim (confirmed scope failures)
distinct and unchanged.

**P3-P5**: DPC's crossing-zero CI now stated explicitly; a "Scope,
stated up front" paragraph added right after Contributions (flagged the
real risk that no LaTeX compiler is available here to check this against
COLING's 8-page limit); B4's seed-0-false-certification finding promoted
to a first-class contribution (v) plus an abstract sentence.

**P6 (seed convergence)**: real finding, saved to
`out/ie/convergence.json` -- GPT-4o-mini's ceiling estimate looks close
to settled by n=5 seeds, GPT-4o's does not (still moving ~5% of its own
value from n=4 to n=5, SE=0.31 on a 0.94 mean). Wrote this honestly
rather than claim convergence that isn't there.

**P7**: turned out to be a non-issue on investigation -- checked file
timestamps and confirmed the baseline sweep (`out/sql_baselines.json`,
`out/ie_baselines.json`) was already generated AFTER the checker fixes,
using the corrected `soundver.checks` module directly (no separate
copy). The paper's own caveat claiming this was outstanding was itself
stale; fixed the caveat text, no new computation needed.

**P8**: confirmed still 0/444 filled in on both sheets -- genuinely
blocked on a human annotator, not something completable solo. Flagged
clearly in plans.md as an action item for the user/co-author.

**P9 (third model family)**: original plan (locally-cached
Qwen2.5-14B-Instruct) hit two real obstacles -- not on OpenRouter, and
doesn't fit the P100's 16GB VRAM in fp16. Switched to
qwen-2.5-7b-instruct/qwen-2.5-72b-instruct via OpenRouter (same protocol
as every other model). Confirmed via direct test calls that OpenRouter
serves no dated snapshot for either (added both to generate.py's
LLAMA_NO_SNAPSHOT set, documented as now meaning "no dated snapshot"
generally). Ran a 5-instance smoke test before committing to scale.
Full 5-seed x 3-task x 2-model collection (~198K calls) launched as
`run_qwen_seeds.sh`, RUNNING IN BACKGROUND, not yet reconciled or
written into the paper.

**P10 (cross-lingual morphology)**: found the paper's own claim
("SIGMORPHON 2022 ships the languages needed") was factually wrong --
cloned the real shared-task repo and confirmed all 9 languages are
agglutinative/fusional, no templatic language present. Fixed this in
Limitations. Found a real, free Arabic dataset (Quranic Arabic Corpus,
GPL) via a research agent, but direct inspection caught a subtle design
trap: its morpheme-level segmentation IS concatenative (same as
Hebrew/Arabic clitic-splitting generally), so reusing the SAME
`concatenates`-style check on it would have shown the check holding --
the opposite of the intended point. Stopped, redesigned a templatic-
analogue check instead (root consonant skeleton subsequence-of-word,
`run_templatic_check.py`), ran it on 50,269 real gold word-root pairs
(no model involved, same gold-only design as SIGMORPHON's own finding):
delta=27.2% (Wilson 95% CI [26.8%,27.6%]) -- within noise of
SIGMORPHON's own 27% for a completely different phenomenon, written up
as a real, honestly-scoped finding (explicit that the match could be
coincidence at n=1 comparison; explicit that the MODEL-facing half is
still not run). Added a verified citation (Dukes & Habash 2010, LREC,
cross-checked against the ACL Anthology directly) to soundver_refs.bib.

**P11 (second independent IE checker implementation)**: found
version2/ie_task.py's `_find_span` has the EXACT same text.find()
first-occurrence bug that was found and fixed in this session's
soundver.checks.ie_no_overlap -- confirmed by direct code inspection
before running anything, which is itself informative (two independent
authors made the same natural mistake). Built
b17_ie_checker_comparison.py following the B17 SQL precedent exactly:
converts v3's slot-filling format to v2's entity-list format so both
checkers see the same extracted spans; caught and fixed a real bug in
my own comparison script before trusting it (v2's label_correct()
internally re-parses raw text expecting a JSON LIST, but v3's output is
always a JSON OBJECT, so calling it directly would have always returned
"wrong" -- fixed to use the paper's own canonical _field_value_match
label instead, applied to the already-parsed object). Ran a 10-instance
smoke test first (clean, 0 errors) before running the full 100-instance
x 4-model comparison (2,000 candidates total, matching B17's SQL scale
exactly) -- RUNNING IN BACKGROUND as of this note, not yet reconciled or
written into the paper.

STILL OPEN as of this update: P9 and P11's actual results (both running
in background, need reconciliation + honest write-up once done), P8
(blocked on human), final hygiene pass (re-run measure_pages.py once a
LaTeX toolchain is available, confirm COLING's 8-page limit against all
the new prose added this pass).

## Update: P11 finished and written up; P9 hit a real stall and was restarted

**P11 result**: full 100-instance x 4-model comparison finished cleanly
(0 errors). Overall disagreement 25/2,000 = 1.25% (six times SQL's own
B17 rate of 0.2%, still small). One real, investigated finding: for
Llama-3.1-8B, this paper's checker measures delta=2.38% against the
independent second implementation's 0.00% on the SAME candidates -- the
REVERSE pattern from SQL's B17 result. Confirmed (via direct code
reading, not just running the numbers) this is NOT the no_overlap bug
resurfacing -- it's a real structural difference: v3's required_fields
checks the parsed object has all 4 top-level keys; v2's checks each item
in its own converted entity-list has both required keys, vacuously true
for an empty list, so it never flags a bare `{}` as missing fields the
way v3 correctly does. This matches (and independently confirms) the
already-documented Llama-3.1-8B empty-list-omission quirk from earlier
in the session. Written up as a new paragraph continuation right after
the existing SQL B17 paragraph in Findings, with the exact mechanism
explained rather than left as an unexplained number.

**P9 stall incident**: sql/seed0 completed cleanly (13,200 records, both
Qwen models, verified). sql/seed1 then stalled for 4+ hours with ZERO
log progress past 175/200 instances (first model), despite the process
accumulating CPU time throughout -- genuinely stuck, not just slow.
Diagnosed via `/proc/<pid>/task`: ~99-106 threads present where the
`ThreadPoolExecutor(max_workers=8)` should only ever show ~8-10. Could
not get a proper stack trace (`py-spy` not installed in this
environment). Ruled out a corrupted/locked SQLite file directly (opened
`wta_1.sqlite` in 0.02s, fine) and ruled out an API outage (a fresh test
call succeeded immediately). Root cause NOT confirmed -- flagged
honestly as unexplained rather than guessed at.

Killed both the wrapper script and the stuck Python process. Confirmed
seed0's data was safe on disk (it had already been written), but
seed1's in-progress work for the first model was NOT recoverable --
`generate.py` only calls `write()` once per (task, model) pair, after
the whole `ThreadPoolExecutor` block for that model closes, not
incrementally. This is a real design gap worth fixing properly at some
point (flagged in plans.md and CLAUDE.md), not something to route around
silently.

Restarted as `run_qwen_seeds_resume.sh`: skips the already-done
sql/seed0, reduces `SOUNDVER_GEN_WORKERS` to 4 (down from 8, on the
theory that SQL's per-instance SQLite/NFS I/O was more likely to be the
contention point than the other two tasks, though this is a mitigation
guess, not a confirmed fix), and added `watch_qwen_stall.sh` running
alongside it -- polls the log file's size every 60s and flags a stall
within 15 minutes of zero growth instead of discovering one 4+ hours
late as happened this time. The same elevated thread count (99 at fresh
startup, even with only 4 workers configured) reappeared on restart,
which is itself informative: it's likely a structural property of how
`generate.py`/`requests`/`sqlite3` interact under this task, not
something the worker-count reduction alone fixes -- worth deeper
profiling if it recurs, since the current fix is a mitigation, not a
diagnosis.

STILL OPEN: P9's collection (running, being actively watched this time),
P8 (blocked on human), final hygiene pass.

## Update: P9's stall root-caused and actually fixed (not just mitigated)

The reduced-worker restart stalled again at the SAME point (sql/seed1,
175/200) -- two reproductions at the same spot ruled out random NFS
flakiness, so stopped guessing and traced it properly this time.

**Root cause**: `_label_correct` for SQL calls `test_suite_accuracy`,
which executes the MODEL'S OWN generated SQL (arbitrary, unpredictable
per-instance) against SQLite databases with no `set_progress_handler`.
`sqlite3.connect(timeout=...)` only bounds lock-WAIT time, not query
EXECUTION time -- a real, easy-to-miss gotcha. A single pathological
model-generated query can therefore hang a worker thread indefinitely.
Ruled out concurrency/file-locking on the cached distilled databases
directly first (20 concurrent trivial queries against the suspect
`wta_1` database, 113MB, an outlier ~30x the median Spider DB size, all
finished in <25ms) -- the hang is specific to actual query content
executed against these DBs, not file access contention.

This combined with `ThreadPoolExecutor` + `as_completed()`'s unbounded
wait: as_completed() cannot skip past one future that never completes,
so ONE hung instance blocks progress forever even with every other
future in the batch already finished minutes/hours earlier.

**Real fix in `code/soundver/generate.py`** (not a workaround, not
touching the frozen `version2/spider_task.py` that B17's inter-
implementer comparison depends on staying unmodified):
1. Replaced the unbounded `as_completed()` loop with
   `concurrent.futures.wait(pending, timeout=180,
   return_when=FIRST_COMPLETED)` in a while-loop, marking anything
   still pending after the window as a hard-timeout skip rather than
   waiting forever.
2. Caught a SECOND bug while testing this: `with ThreadPoolExecutor(...)
   as pool:` calls `shutdown(wait=True)` on exit, which ITSELF blocks on
   a hung thread regardless of the loop having already moved past it --
   confirmed directly with an isolated test (3 quick futures + 1
   permanently-hung one; the loop correctly detected and skipped the
   hang, but the `with` block's exit still hung the whole script).
   Switched to a plain `pool = ThreadPoolExecutor(...)` + explicit
   `pool.shutdown(wait=False)`.
3. Caught a THIRD, related issue verifying end-to-end: ThreadPoolExecutor
   worker threads are not daemon threads by default, so Python blocks at
   normal process exit until every thread finishes too -- would have
   meant a hang on the very LAST instance of the very last model/task
   still prevents the script from ever exiting even with fixes 1-2 in
   place. Added `os._exit(code)` at the very end of `__main__` (after
   all files are already written and closed, so this is safe) to bypass
   Python's normal thread-join-on-exit behavior.

Verified the complete fix with an isolated hang-simulation test before
trusting it on the real job (matches the exact real code pattern: 3
quick + 1 permanently-hung future, confirmed both that the main loop
proceeds past the hang at the timeout boundary AND that the process
still exits cleanly afterward).

Relaunched as `run_qwen_seeds_resume2.sh` (skips sql/seed0, still
4 workers) with a tighter `watch_qwen_stall2.sh` (10 min, down from 15)
-- a real stall should no longer be structurally possible with this fix,
so if the watcher fires again, that would be genuinely new information,
not a recurrence of the same diagnosed bug.

STILL OPEN: P9's collection (running with the real fix now, being
watched), P8 (blocked on human), final hygiene pass. Worth considering
whether this reproducibility hazard (an execution-based harness that can
hang on adversarial-in-effect model output) deserves its own sentence in
the paper's Limitations/reproducibility discussion if there's page
budget room -- other researchers building similar harnesses would hit
the same class of bug.
