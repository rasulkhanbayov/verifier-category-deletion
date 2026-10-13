# Plan: strengthen soundver_main.tex for COLING/NAACL submission

Source: full-paper audit (weaknesses in claims/results/evidence, then
cost-tagged strengthening proposals), run against the current draft.
Each item below is marked `[ ]` open / `[x]` done. Update the checkbox
and add a one-line note under an item when it's completed, so this file
stays a running log, not just a wishlist.

## Priority order

Cheap internal-consistency fixes first (P1-P5), since they cost almost
nothing and remove self-inflicted red flags. Then medium-cost analysis
on data already collected (P6-P8). Then new data collection, ranked by
value-to-cost for COLING/NAACL specifically (P9-P11).

---

## Cheap fixes (hours, no new data)

- [x] **P1. Delete or resolve the two stale `\miss{}` markers (B9, B3).**
  Done. B9 was NOT already fully satisfied as assumed — the paper's
  prose/tables only ever used short model names ("GPT-4o", "Llama-3.1-70B"),
  never the actual dated snapshot strings, so the "Models and access"
  paragraph was rewritten to state them explicitly:
  `openai/gpt-4o-2024-11-20`, `openai/gpt-4o-mini-2024-07-18` (pinned),
  and the Llama-3.1 no-dated-snapshot exception with the real mitigation
  (per-request provider logging — verified 200/200 SQL seed-0 instances
  for Llama-3.1-8B actually saw multiple backend providers: Novita,
  DeepInfra, Groq, confirmed from `data/records_sql_seed0.providers.jsonl`).
  Access date range corrected from a first guess (09-02 to 09-20) to the
  real file-timestamp range (2026-09-02 to 2026-09-04) after checking
  `ls -la --time-style=full-iso` on the actual data files — a caught
  near-miss, not hand-waved. B3 verified genuinely resolved (every
  `out/{sql,ie,morph}/` directory has real `rates.json`, `seeds.json`,
  `tab_ceiling.tex` etc., all real per-instance-derived output, not
  hand-typed) and the marker (which also referenced a stale
  `REDFLAGS.txt` filename — actual file is `REDFLAGS.md`) removed.

- [x] **P2. Fix "two of three tasks" vs "one of three" inconsistency.**
  Done, and the direction was the OPPOSITE of my first-pass audit guess:
  checked real seed-0 delta values across all 12 cells
  (`soundver.rates.estimate` per model per task) and found ALL THREE
  tasks have at least one model with delta>0 (SQL: 0.0007-0.0017 across
  3 of 4 models; IE: 0.0010-0.0103 across 2 of 4; morphology:
  0.11-0.18 across all 4) — so "two of three" was actually an
  undercount, not an overcount. Rewrote both lines (138, 207) to say
  "somewhere on all three tasks" / "all three of our tasks," and added
  the correct narrower qualifier ("though only one... survives as a
  genuine property of the task rather than our own implementation") so
  the delta>0-somewhere claim (true for 3/3) stays clearly distinct from
  the confirmed-scope-failure claim (true for 1/3, unchanged). Verified
  contribution (ii) already said "on all three tasks" correctly, so no
  further edits needed there.

- [x] **P3. State DPC's non-significance explicitly.**
  Done. Added "not distinguishable from zero at this sample size" right
  after the CI in the Baselines and statistics paragraph. Checked the
  table note (item m) separately and left it as-is since the table row
  itself already shows the crossing-zero CI directly
  ($+2.0$~[$-1.5$,~$5.5$]) — no need to duplicate the clause there.

- [x] **P4. Move the scope-limiting caveat earlier.**
  Done — added a "Scope, stated up front" paragraph right after the
  Contributions list (before Related Work), stating the
  syntactic/schema-not-semantic and English-only limits in ~5 sentences,
  pointing forward to Limitations for the full typological argument
  rather than duplicating it.

  **PAGE BUDGET FLAG (cumulative, updated after P1-P11): word count grew
  from 14,029 to 14,730+ across this whole pass (~700 words, ~5%) —
  P4's new paragraph, P5's contribution (v) + abstract sentence, P6's
  "Is five seeds enough?" paragraph, P10's templatic-check paragraph,
  and P11's IE comparison paragraph all add real body-text content, not
  just table/appendix edits. No LaTeX compiler is available in this
  environment to check the real page count against COLING's 8-page
  limit.** Before submission: compile with `pdflatex`/`latexmk` and run
  `measure_pages.py`. If over budget, trim candidates in priority order
  (least load-bearing first): P4's scope paragraph (a pointer, can
  shrink to 2-3 sentences), P6's seed-convergence paragraph (could move
  to a footnote or appendix table), P11's IE comparison (could
  compress to 2-3 sentences appended to the existing SQL B17 paragraph
  instead of its own block). Do NOT cut P5 (the promoted contribution)
  or P10's false-claim fix — those are correctness fixes, not
  optional elaboration.

- [x] **P5. Promote B4 (the seed-0 false certification) to a first-class
  contribution.**
  Done. Added a sentence to the abstract right where the two-checker-
  bugs point already was ("A single seed is not enough to trust either:
  one of our own three seed-0 soundness certifications is itself a
  false positive, exposed only by 5-seed replication, which we take as
  evidence for the paper's own thesis rather than bury as a
  correction"). Added contribution (v) to the intro's Contributions
  paragraph, right after (iv), stating the finding plainly and pointing
  to the existing B4 paragraph in Findings for the numbers. Reused the
  exact, already-verified delta range (0.0005-0.0027) rather than
  restating loosely. The B4 paragraph itself (soundver_main.tex,
  Findings section) was left as-is — it's the detailed evidence; the
  new text is the framing that tells a reader why it matters before
  they get there.

## Medium cost (new analysis on data already collected)

- [x] **P6. Report ceiling convergence across the 5 seeds already
  collected.**
  Done, pure recompute, no new API calls. Computed running mean/SD/SE of
  the ceiling as seeds 0..k-1 accumulate, k=1..5, for both surviving IE
  cells, saved to `code/out/ie/convergence.json`. Honest finding, not
  the reassuring one hoped for: GPT-4o-mini looks close to settled
  between n=4 and n=5 (1.430->1.410 pts) but GPT-4o is still moving
  meaningfully (0.992->0.937, about 5% of its own value) and its SE at
  n=5 (0.31 pts) is not small relative to its 0.94-pt mean. Added a new
  "Is five seeds enough?" paragraph right after B4 in Findings stating
  this plainly: five seeds narrows the estimate from a single noisy
  draw to a usable range, but does not yet pin it down to a stable
  number, and the paper says so rather than implying otherwise. All
  numbers double-checked against the saved JSON before writing them
  into the .tex file.

- [x] **P7. Reconcile the self-consistency/LLM-judge/reward-model
  baseline sweep against the corrected checkers.**
  Turned out to be a stale caveat, not an outstanding task. Checked file
  timestamps: `soundver/checks.py` (the corrected checker module) was
  last modified 2026-09-03 00:03, and `out/sql_baselines.json` /
  `out/ie_baselines.json` were generated AFTER that (14:01 and 20:00 the
  same day) — confirmed `find . -newer out/ie_baselines.json -name
  checks.py` returns nothing, i.e. checks.py was never touched again
  after these baselines ran. Confirmed both baseline scripts import
  directly from `soundver.checks` (no separate/duplicated copy), and
  spot-checked `out/sql_baselines.json`'s numbers against the actual
  table cells in `tab:main` — they match exactly. The reconciliation was
  already done; only the paper's own caveat text was stale. Rewrote the
  E5 paragraph's closing sentence to state this plainly instead of
  claiming outstanding work that isn't outstanding.

- [x] **P8. Complete B8-V1's human label validation.** — **DONE
  (2026-10-07), integrated into the paper.** User confirmed annotator
  independence and the E1 ethics sentence (2026-10-07); all red flags
  removed from the paper. User chose: IE-specific lambda
  as headline, pooled + per-cell as robustness. `soundver/validity.py`
  `score_audit` rewritten to compute per-task/per-cell lambda (Wilson CIs),
  per-task alpha, and 5-seed corrected means; output saved to
  `out/label_audit/b8_v1_score_output.txt` (source of every V1 number in the
  paper). Paper edits: abstract (four->six models stale fix; corrected eps
  81-85%), "Where soundness holds" (corrected 2.88+-0.72 / 3.20+-1.02, near-
  exhaustion not claimed), E2, claims-table Ceiling row, Validity-of-rates
  paragraph (red B8-V1 flag replaced by results + a red VERIFY flag asking the
  user to confirm the two annotators were independent people), appendix V1
  Result paragraph (3 deviations disclosed: gold withheld, no third
  adjudicator, IE risk ranking wrong; IE stratum alpha 0.661 < floor
  reported). Earlier notes: Labeled sheets copied into
  `out/label_audit/annotation_sheet_{1,2}.csv` (blank originals kept as
  `*_blank_backup.csv`); scorer output in `out/label_audit/b8_v1_score_output.txt`.
  Integrity: 444/444 labeled each, item text identical to originals, each
  annotator overrules the automatic label ~30% on different items (not
  copied from the key). Overall alpha=0.783 (passes 0.67 floor); raw
  agreement 400/444. Per task: SQL alpha=0.857 lam=0.338; IE alpha=0.661
  (just UNDER floor on its own) lam=0.074 [0.042,0.128]; morph alpha=0.759
  lam=0.324. lam = both annotators say "correct" (no third adjudicator was
  used, unlike the appendix design). Sample = stack-ACCEPTED, auto-label
  incorrect, so correction only shrinks eps / raises ceiling; delta
  (soundness) untouched. The scorer pools lam across tasks (0.245) ->
  IE ceilings 9.30/9.90 pts — overstates; the appendix's own design is
  per-stratum. IE-specific lam -> GPT-4o 2.19->4.15 [3.28,5.68], GPT-4o-mini
  3.04->4.87 [4.05,6.33]. Per-cell lam: GPT-4o 0.216 -> 8.36 [5.27,13.79],
  GPT-4o-mini 0.000 -> 3.04 [3.04,5.40]. Sample covers original 4 models
  only (Qwen2.5-72B's IE cell is not in it). Older status below:
  **(previously) BLOCKED ON HUMAN, not something I can complete.**
  Checked: `out/label_audit/annotation_sheet_{1,2}.csv` both still show
  0/444 rows filled in. This is not a task I can do myself — it
  requires an actual independent human judgment (two annotators, blind
  to each other and to the automatic label), for the same reason the
  E1 ethics sentence can't be resolved by a machine check. What's ready
  on my end: the sheets themselves (444 items each, real task input +
  candidate output shown, gold/automatic label withheld) and
  `b8_v1_collect_annotations.py` to score them once filled in. **Action
  needed from you (or a co-author)**: two people independently fill in
  the `human_label` column (`correct`/`incorrect`/`unsure`) in both
  sheets, then run `python3 b8_v1_collect_annotations.py` from `code/`.

## Higher cost (new data collection)

- [x] **P9. Add a third model family.** — **DONE, fully integrated into the paper (see "FULL PAPER-WIDE INTEGRATION DONE" note below). Had real stall/rate-limit/timeout incidents along the way, see notes below.**
  Original plan (Qwen2.5-14B-Instruct, locally cached) hit a real
  obstacle: not on OpenRouter, and a 14B model needs ~28GB fp16 which
  doesn't fit the available P100's 16GB VRAM without quantization work.
  Switched to `qwen/qwen-2.5-7b-instruct` and `qwen/qwen-2.5-72b-instruct`
  via OpenRouter instead — matches the paper's existing API-based
  protocol exactly, brackets the existing 8B/70B Llama split, cheap
  (~$0.0000001-0.0000004/token). Confirmed via 3 test calls that
  OpenRouter does NOT serve a dated snapshot for either Qwen id (same
  category as Llama), so added both to `generate.py`'s
  `LLAMA_NO_SNAPSHOT` set (kept the variable name, documented in a
  comment that it now means "no dated snapshot" generally, not
  Llama-specifically) so the same per-request provider-logging
  mitigation applies. Ran a 5-instance smoke test on IE first (25 API
  calls) and inspected the output records before committing to scale —
  clean, well-formed records, checks firing correctly.

  Full scope matches the paper's own 5-seed standard (chosen explicitly
  over a cheaper seed-0-only option, since B4's own finding is that
  seed-0-only certification isn't trustworthy — doing that for new
  models would be a double standard): 2 models x 3 tasks x 5 seeds x
  200 instances x 32 candidates = ~198K API calls. Launched as
  `run_qwen_seeds.sh` in the background
  (`data/records_{task}_qwen_seed{0..4}.jsonl` as it completes).

  **Stall incident (2026-09-28)**: sql/seed0 completed cleanly (13,200
  records, both models, verified). sql/seed1 then stalled for 4+ hours
  with zero log progress past 175/200 instances (first model) despite
  accumulating CPU time — confirmed genuinely stuck, not just slow, via
  `/proc/<pid>/task` showing ~99-106 threads where only 8 were expected
  from the `ThreadPoolExecutor(max_workers=8)`. Root cause NOT fully
  identified (`py-spy` unavailable for a stack dump; ruled out a
  corrupted/locked SQLite file by testing `wta_1.sqlite` directly —
  opened in 0.02s, fine). Since seed1's records are only written to
  disk once per MODEL (`write()` called after each model's
  `ThreadPoolExecutor` block closes, not incrementally per-instance),
  killing the stuck process lost all of seed1's in-progress work for
  the first model — a real gap in `generate.py`'s checkpointing design,
  worth fixing properly at some point (write incrementally, or at least
  per N instances, not only at the end of a whole model's loop).

  Killed and restarted as `run_qwen_seeds_resume.sh`: skips
  sql/seed0 (already done), reduces `SOUNDVER_GEN_WORKERS` from 8 to 4
  (lower NFS/SQLite contention, since SQL is the most I/O-heavy task
  and the stall happened specifically there), and added
  `watch_qwen_stall.sh` running alongside it — polls the log file every
  60s and flags a stall within 15 minutes of zero growth, instead of
  discovering one 4 hours late as this time. The oddly high thread
  count (99 even at fresh startup with only 4 workers) reappeared on
  restart too — not itself a proven cause of the stall, but a genuine
  unexplained anomaly worth someone with better profiling tools looking
  into if this recurs.

  **Root cause found and fixed (2026-09-28, second stall).** The
  reduced-worker restart stalled AGAIN at the exact same point
  (sql/seed1, 175/200) — same pattern twice ruled out random NFS
  flakiness. Traced properly this time: `_label_correct` for SQL calls
  `test_suite_accuracy`, which executes the MODEL'S OWN GENERATED SQL
  (arbitrary, unpredictable) against SQLite databases with no
  `set_progress_handler` — `sqlite3.connect(timeout=...)` only bounds
  LOCK-WAIT time, not query EXECUTION time, so one pathological
  model-generated query (e.g. against the two outlier-large Spider DBs,
  `wta_1` 113MB / `soccer_1` 341MB, both ~30-100x the median) can run
  unbounded. Ruled out concurrency/locking on the cached distilled
  copies directly (20 concurrent trivial queries against `wta_1`
  finished in <25ms each) — the hang is specific to some actual
  model-generated query content, not file access.

  This combined badly with `as_completed()`'s no-timeout wait: ONE hung
  future blocks the whole per-model loop forever, even though every
  other future had already finished. Did NOT touch `version2/spider_task.py`
  (the frozen, independent-by-design B17 comparison codebase) to fix
  this. Instead fixed `generate.py` itself: replaced the unbounded
  `as_completed()` loop with `concurrent.futures.wait(..., timeout=180s,
  return_when=FIRST_COMPLETED)`, skipping any future still pending after
  the window as a hard-timeout error rather than waiting forever.
  Caught and fixed a SECOND bug while testing this fix: `with
  ThreadPoolExecutor(...) as pool:` calls `shutdown(wait=True)` on exit,
  which itself blocks on a hung thread regardless of the loop having
  "moved on" — switched to a plain `pool = ThreadPoolExecutor(...)` +
  explicit `pool.shutdown(wait=False)`. Caught and fixed a THIRD,
  related issue verifying end-to-end: `ThreadPoolExecutor` worker
  threads are not daemon threads, so Python blocks at normal process
  exit until they finish too — added `os._exit(code)` at the very end of
  `__main__` (after all files are already written/closed) to bypass
  this. Verified the full fix with an isolated hang-simulation test
  (3 quick + 1 permanently-hung future, confirmed the loop correctly
  proceeds past the hang at the timeout boundary and the process still
  exits) before trusting it on the real job. Relaunched as
  `run_qwen_seeds_resume2.sh` with a tighter stall-watcher (10 min, was
  15) since a real stall should no longer be possible with this fix --
  if the watcher still fires, that's new information, not the same bug.

  **IMPORTANT CORRECTION: the ~95-99 thread anomaly was a RED HERRING,
  not related to the actual stall.** Traced it precisely: `import
  numpy` alone spawns exactly 48 threads (= `nproc`, confirmed) as its
  BLAS backend's pre-spawned worker pool, sitting idle on
  `futex_wait_queue_me` until actually used for parallel linear algebra
  -- this is standard, well-known NumPy/OpenBLAS behavior, completely
  benign. `version2/spider_task.py` pulls in `soundver_experiments`
  which imports `numpy` (directly or transitively via
  `soundver_analysis`), so every SQL-task run has always carried this
  idle thread pool, unrelated to workers, unrelated to hangs, unrelated
  to the actual bug. All the earlier thread-count-based reasoning in
  this note (concurrency-bug theories, worker-count correlation
  guesses) was chasing a false lead -- confirmed by testing with
  SOUNDVER_GEN_WORKERS=1: still showed ~96 threads immediately, proving
  the count has zero relationship to configured concurrency. Lesson for
  future debugging: verify an anomaly is actually load-bearing before
  building theories on top of it.

  **Third stall, even with the timeout fix (2026-09-28, later same day)**:
  restarted twice more after the fix above; both times stalled again at
  sql/seed1, and critically, the 180s per-instance timeout NEVER FIRED
  (13+ min elapsed, well past 180s, zero log output of any kind —
  meaning either the fix has a real bug not caught by isolated testing,
  or the hang happens somewhere the fix doesn't cover). Investigated
  much further before giving up and just retrying blindly again:
  - Confirmed via `/proc/<pid>/task`: still ~95-99 threads with only
    2-4 configured workers, and via per-thread `wchan`: ~95 threads on
    `futex_wait_queue_me` (lock wait), only 2-3 on `do_poll` (real I/O).
    This rules out the threads being idle/finished workers — they are
    actively contending on SOME lock.
  - Ruled out `ThreadPoolExecutor` itself creating excess threads: a
    clean isolated test (200 queued no-op tasks, 4 workers) used exactly
    5 threads total, not ~99.
  - Ruled out fresh SQLite distillation as the cause for THIS specific
    stall: checked every db_id actually used in sql/seed=1's 200-instance
    sample, all already have complete 3/3 distilled copies cached.
  - Ruled out concurrent DB-file access/locking directly: 20 concurrent
    trivial queries against the largest suspect DB (`wta_1`, 113MB, an
    outlier ~30x the median Spider DB size) all completed in <25ms each.
  - `strace` unavailable (no ptrace permission in this sandboxed
    environment) -- could not get a live syscall trace of the actually-
    hung threads, which would have been the most direct way to confirm
    the mechanism.
  - Noticed this is a SHARED multi-user machine (other users' training/
    inference jobs visible in `ps aux`) but system load (2.06 on 48
    cores) and memory (142GB free) both looked light at the time of
    inspection, weakening (not eliminating) a resource-contention
    explanation -- NFS-specific contention from other users remains
    untested and plausible.

  Given the timeout fix's own correctness was verified in isolation but
  is NOT preventing the real stall, added much more granular
  instrumentation rather than guess further: print immediately (not
  just every 25 instances) whenever a single candidate's completion or
  `_label_correct` call individually exceeds 15-30s, with the actual
  generated SQL text included, gated behind a new
  `SOUNDVER_INSTANCE_TIMEOUT` env var (default still 180s) so the
  timeout itself is tunable without code edits. Relaunched a third time
  as `run_qwen_seeds_resume3.sh` with `SOUNDVER_GEN_WORKERS=2` (down
  from 4, isolating concurrency further) and `SOUNDVER_INSTANCE_TIMEOUT=90`
  (shorter, for faster diagnostic feedback) plus `watch_qwen_stall3.sh`
  (5-min threshold). **If this stalls too, the next real diagnostic step
  is SOUNDVER_GEN_WORKERS=1 (fully serial, eliminates concurrency as a
  variable entirely) — if a fully serial run still stalls at the same
  point, the bug is in a single-threaded code path (most likely inside
  `test_suite_accuracy`'s actual query execution against one specific
  problematic instance's model-generated SQL), not a concurrency bug at
  all, and the fix needs to target THAT instead.**

  **Serial (SOUNDVER_GEN_WORKERS=1) diagnostic result**: ran with a
  60s per-instance timeout. Real result: 193/200 instances hit the hard
  timeout, only 7/200 actually completed -- confirms this is SYSTEMIC
  at 60s, not one pathological instance. But zero `[slow]` warnings
  fired anywhere in the log, meaning the hang happens BEFORE the first
  `_complete()` call inside `process_one` even returns -- my fine-
  grained instrumentation (which only prints after a call returns) is
  structurally blind to a call that never returns at all. Re-tested the
  exact same instances that had timed out (e.g. sql-00570) completely
  in isolation immediately afterward -- all fast (<1s for prompt
  construction + API call + db connect). This means the hang, when it
  happens, is likely either (a) genuinely transient/environmental (API-
  side latency or degradation at specific moments, given `timeout=60`
  passed as a single float to `requests.post` bounds CONNECT and READ
  separately, not combined, so worst case across 3 retries could
  legitimately exceed 60s even under normal-but-slow conditions), or
  (b) something that only manifests under conditions not yet
  reproduced in isolation. Root cause NOT fully confirmed despite
  extensive effort (isolated component tests for sqlite3.connect,
  prompt construction, and _complete on the specific timed-out
  instances all came back fast).

  **Decision**: rather than continue chasing an intermittent/hard-to-
  reproduce cause indefinitely, trust the verified-correct timeout+skip
  mechanism (it DID work correctly in the 60s serial test: exactly the
  193 hung instances were skipped and logged, the 7 that completed were
  recorded normally -- no silent data loss, no indefinite block) and
  re-tune it to a more generous, still-bounded value for a real
  production attempt: `SOUNDVER_INSTANCE_TIMEOUT=240` (up from 60,
  giving real margin above `_complete`'s own worst-case retry budget)
  with `SOUNDVER_GEN_WORKERS=4`. Launched as `run_qwen_seeds_final.sh`
  with `watch_qwen_final.sh` (10-min stall threshold) alongside it. If
  this run completes with a real but small skip rate (a few percent,
  not the 96.5% the 60s test showed), that's an acceptable, honestly-
  reportable outcome -- skipped instances are logged with a reason
  (`hard timeout: no future completed within Ns`) and excluded from the
  225 written records rather than silently fabricated, consistent with
  this whole project's verification discipline.

  **The 240s/4-worker retune worked.** SQL/seed1's 7B model: 199/200
  completed, only 1 hard-timeout skip (`sql-00483`, db=`wta_1` -- same
  outlier-large database flagged from the very start of this
  investigation, a genuinely recurring pattern worth a footnote but not
  worth chasing further at a 0.5% impact rate). The new `[slow]`
  diagnostics fired usefully too (e.g. "sql-00624 cand=13 total 63s"),
  confirming individual candidates CAN legitimately take 30-60+s under
  real conditions -- consistent with the theory that 60s was simply too
  tight a timeout relative to real (if unusual) latency, not that
  something was infinitely hung. Collection continued cleanly onto the
  72B model and past seed=1 without further intervention needed.

  **CORRECTION: the 240s retune was necessary but not sufficient --
  a second, more serious bug was discovered once the job ran longer.**
  Letting `run_qwen_seeds_final.sh` continue past sql/seed1 revealed
  entire (task, model, seed) cells failing catastrophically:
  sql/seed2's 72B model got 0/6600 records (100% failure), ie/seed0's
  72B model got only 957/6600 (14.5%), several other cells 30-90%
  incomplete. Root cause, found by actually reading the skip reasons
  instead of just the skip COUNT: real `429 Too Many Requests` and
  `504 Gateway Timeout` errors from OpenRouter, not hangs. `_complete`'s
  retry logic treated these identically to any transient error --
  3 retries, 1s/2s/4s backoff, ~7s total -- nowhere near enough to
  outlast real rate-limiting. Checked the OpenRouter account directly
  (`/api/v1/auth/key`): this is a dollar-credit account ($700 limit,
  ~45% used, not a fixed requests-per-interval cap), so the 429s are
  most likely PROVIDER-side throttling specific to the Qwen models'
  backend under the sudden new load this collection introduced, not an
  account-level limit.

  Fixed `_complete` properly: 429/504 now get their own branch with a
  much longer backoff (10s base, exponential, capped at 120s, respecting
  a `Retry-After` header if the API provides one) instead of the
  generic-error path, and retries raised from 3 to 6. Also reduced
  `SOUNDVER_GEN_WORKERS` to 3 (from 4) to lower sustained request
  pressure on the specific overloaded provider, as a complementary
  mitigation alongside better backoff, not instead of it.

  Audited every already-written file's actual per-model record count
  against the expected 6600 (200 instances x 33 completions) rather
  than trust "the job finished" -- found the exact list of incomplete
  cells (sql seeds 2-4's 72B model; ie ALL 5 seeds needing at least the
  72B model, seed0 needing both; morph not started at all yet). Wrote
  `run_qwen_resume_targeted.sh` to re-run exactly those, with one
  important safety note: `generate.py`'s `write()` OVERWRITES the whole
  output file per invocation (not per-model, not append) -- re-running
  with only the missing model would have silently DESTROYED the
  already-good other model's data in that same seed's file. Every
  re-run in the targeted script therefore passes BOTH models together
  even where only one needs fixing, accepting some redundant re-fetch
  cost to eliminate that data-loss risk entirely. Left sql/seed1's 7B
  model as-is (6567/6600, 99.5%, the single already-documented
  `wta_1` timeout) rather than re-run it needlessly.

  **THE ACTUAL ROOT CAUSE, finally found (2026-09-29): not a bug, a
  timeout budget mismatch.** After the retry-logic fix, re-ran the
  targeted resume -- it finished ("TARGETED RESUME DONE") but audited
  the actual per-model counts against expected and found 9 of 15
  seed-task cells STILL badly incomplete for the 72B model specifically
  (several near-total failures: sql/seed2 0/6600, sql/seed4 0/6600,
  morph/seed3 0/6600). Investigated directly rather than retry blindly
  again: measured qwen-2.5-72b-instruct's real per-call latency live
  (5 direct calls) -- 12-18s per call (via Novita/DeepInfra), roughly
  10x qwen-2.5-7b-instruct's ~1-2s. `process_one()` makes its 33
  completions (1 base + 32 candidates) SERIALLY within a single
  instance (not concurrently), so one 72B instance legitimately needs
  ~33 x 15s =~ 8+ minutes end to end. `SOUNDVER_INSTANCE_TIMEOUT=240`
  (4 min, set during earlier hang-debugging) was therefore SHORTER than
  the real, honest serial cost for this model -- a self-inflicted
  timeout-too-short problem masquerading as a provider outage, not
  actual rate-limiting or a hang. (The earlier 429/502 fix was still
  real and worth keeping -- those genuinely happened and needed better
  backoff -- but they were not the dominant cause of the persistent 72B
  failures; the timeout budget was.)

  Fixed: raised `SOUNDVER_INSTANCE_TIMEOUT` to 900s (15 min, real
  margin above the ~8-min honest cost) and raised
  `SOUNDVER_GEN_WORKERS` back to 8 (since the earlier reduction to 3
  was mitigating a misdiagnosed cause; smoke-tested 8 workers against
  10 real 72B instances first -- 90/90 completions succeeded cleanly,
  no 429s, confirming concurrency itself was never really the problem).
  At 8 workers the real wall-clock cost is ~3.4hr/cell x 9 remaining
  incomplete cells =~ 31hr total -- a genuinely long job, launched as
  `run_qwen_resume2.sh` with `watch_qwen_resume2.sh` (30-min stall
  threshold, deliberately longer than earlier watchers since 72B's
  real per-checkpoint pacing is now expected to be slow, not stalled).

  **`run_qwen_resume2.sh` finished ("RESUME2 DONE") -- nearly complete
  success.** Audited every one of the 15 (task, seed) cells' actual
  per-model record counts against the expected 6600: 14/15 cells are
  now at 99-100% (several at exactly 6600/6600 for both models).
  Only ONE cell remains incomplete: sql/seed2's 72B model at
  5313/6600 (80.5%, 39/200 instances skipped, all genuine 429s that
  outlasted even the 120s-capped backoff during a burst of concurrent
  load -- a real, now much rarer, residual rate-limit effect, not a
  new bug). Re-running just that one cell
  (`data/records_sql_qwen_seed2.jsonl`, both models, same settings:
  8 workers, 900s timeout) rather than the whole batch again.

  **P9 COLLECTION COMPLETE (2026-09-29/30).** Final audit of all 15
  (task, seed) cells against the expected 6600 records/model: every
  single cell is now above 95% for both models, most at exactly 100%.
  Only two cells have any residual gap, both small and both honestly
  logged rather than silent: sql/seed1's 7B model (99.5%, 33 missing,
  the original single `wta_1` timeout from the very first debugging
  round) and sql/seed2's 72B model (96.0%, 264 missing, residual
  429/504/read-timeout errors that outlasted even the improved
  backoff during a final resume pass). Both gaps are small enough
  (<5% each) not to materially bias any rate estimate, and are exactly
  the kind of honestly-reported small residual the paper's own B4
  discipline (report real n, don't silently pad it) already expects.

  Full debugging arc, for anyone reading this later: suspected SQLite
  hang -> ruled out -> suspected rate-limit-only bug -> partially real,
  fixed, but insufficient alone -> actual dominant cause: 72B model is
  genuinely ~10x slower per call than 7B, and an earlier timeout
  (240s) set during hang-debugging was shorter than 72B's honest
  serial per-instance cost (~8min) -> fixed with a 900s timeout and
  workers back to 8 -> two resume passes closed all but 2 small gaps.

  **FULL PAPER-WIDE INTEGRATION DONE (2026-09-30).** Reconciled all
  6 models' data (`soundver.reconcile --seeds` for all 3 tasks), then
  systematically updated every place the model list/cell count
  appeared: model list (intro), E0 (re-ran on both Qwen models, real
  numbers: delta=0 under execution match, 0.19-0.22 under test-suite
  accuracy, consistent with the original 4), Table 3/tab:ceiling (added
  Qwen rows, updated caption to 18 cells / 3 surviving cells), the
  abstract, contribution (v), the "Where soundness holds" paragraph, B4's
  full findings paragraph, "Is five seeds enough?" (Qwen-72B is the
  TIGHTEST-converging of the 3 surviving cells, SE=0.18 at n=5 vs
  GPT-4o's 0.31), E2, E3/E4 (re-ran gain-curve + exhaustive-subset on
  Qwen, 6/6 and 0-violations respectively, both cleanly confirming),
  the appendix tab:params (added Qwen rows + predicted/observed for
  IE/Qwen-72B), tab:params-morph, the claims table (app:claims, every
  row's counts corrected), the contamination paragraph, "Models and
  access" (real access dates, confirmed via direct provider testing
  which providers actually serve each Qwen model), tab:stack-breakdown
  (added Qwen row + caption fix), and the intro's fig:two-rates TikZ
  scatter plot (added all 6 new data points with verified eps/delta
  coordinates, not just the prose).

  **REAL ERROR CAUGHT AND FIXED mid-integration**: initially wrote
  SQL/Qwen2.5-72B as a "seed-0 false certification" parallel to
  SQL/Llama-3.1-70B (same dagger-marked pattern) -- but direct
  verification (`estimate(rs, seed=0)`) showed Qwen-72B's SQL delta at
  seed 0 was ALREADY nonzero (0.0002), never a genuine seed-0
  certification at all. This is a materially different, weaker story
  than Llama-70B's (which genuinely was delta=0.0000 at seed 0 before
  failing at other seeds) and got corrected in every one of ~6 places
  it had been written before finalizing -- caught by the same
  verification-before-writing discipline this whole project runs on,
  applied to my OWN new prose, not just the original draft's claims.

  **E5 genuinely cannot be extended to Qwen**: checked directly (both
  models, every available provider) -- neither Qwen2.5-7B nor
  Qwen2.5-72B returns per-token logprobs from any OpenRouter provider.
  Stated this explicitly wherever E5 is discussed rather than silently
  leaving the scope ambiguous. B17 (inter-implementer agreement) and
  B8-V2 (prompt sweep design) were both left scoped to the original 4
  models as a deliberate, stated choice given time constraints -- not
  claimed as extended.

  **Real new finding, the headline result of this whole P9 effort**:
  IE/Qwen2.5-72B-Instruct is genuinely sound at all 5 seeds
  (delta=0.0000 throughout), giving THREE certified cells total (not
  two): GPT-4o, GPT-4o-mini (both OpenAI) and now Qwen2.5-72B (Alibaba),
  so the surviving cells span two vendor families, not three -- no
  Llama/Meta cell has ever certified, at any seed, on any task. Its
  ceiling (2.15+-0.40 pts) is tighter (lower SD) than either existing
  OpenAI cell, and its seed-to-seed convergence is the best of the
  three.

  **A SECOND self-check catch, found on final review**: had written
  "the three surviving cells span three vendor families" in FOUR
  separate places (abstract, "Where soundness holds," B4's paragraph,
  and the fig:two-rates caption) -- wrong every time. The three
  surviving cells are GPT-4o, GPT-4o-mini (both OpenAI) and
  Qwen2.5-72B (Alibaba): that's TWO vendor families, not three, and
  no Llama/Meta cell has ever certified on any task at any seed. Easy
  mistake to make since the STUDY has 3 families (OpenAI/Meta/Alibaba)
  and it's tempting to assume the surviving subset mirrors that, but it
  doesn't. Fixed all four instances after a deliberate final check
  against the actual cell list rather than trusting the pattern from
  memory -- the same discipline that caught the SQL/Qwen2.5-72B
  "false certification" error above, applied a second time in the same
  pass.

  **PAGE BUDGET FLAG (updated again)**: word count now 15,769 (was
  14,029 before this whole strengthening pass, ~1,740 words / ~12.4%
  growth total). No LaTeX compiler available in this environment --
  compile and run measure_pages.py before submission; if over budget,
  the Qwen-specific additions to already-dense paragraphs (E3/E4,
  contamination, tab:stack-breakdown's caption) are more compressible
  than the tables themselves.

  **Next steps once collection finishes**: check the skip rate/reasons
  in the final log before trusting any Qwen number — if skips are
  concentrated in specific db_ids or instances (wta_1 is the current
  lead), that's still worth a one-line caveat, not just silently
  accepting a slightly-reduced n for those cells. Run E1's
  admissibility audit on the new cells (checker bugs are per-model-
  output-format, so a NEW model can trigger a checker edge case never
  seen before — do not assume the existing checkers handle Qwen's
  output format perfectly without checking), reconcile via
  `soundver.reconcile --seeds`, and only then write any new numbers
  into the paper — same verification discipline as everything else.
  Also worth a footnote in the paper's own Limitations/reproducibility
  discussion if there's room: this is a genuine reproducibility hazard
  (a model-generated adversarial-in-effect query, or just real
  API-latency variance, stalling an unbounded evaluation harness) that
  other researchers building similar execution-based harnesses would
  hit too.

- [x] **P10. Run the cross-lingual morphology test.** — Done, but the
  scope ended up narrower and more honest than originally planned.
  First finding: the paper's own claim "SIGMORPHON 2022 ships the
  languages needed to test it" was FALSE — cloned the real shared-task
  repo (github.com/sigmorphon/2022SegmentationST) and confirmed its 9
  languages (Czech, English, French, Hungarian, Italian, Latin,
  Mongolian, Russian, Spanish) are all agglutinative/fusional, none
  templatic. Fixed this false claim in Limitations before doing
  anything else.

  Searched for a real templatic (Arabic/Hebrew root-and-pattern)
  dataset via a research agent — found the Quranic Arabic Corpus
  (github.com/mustafa0x/quran-morphology, GPL, 130K morpheme lines,
  free, no login-gate via the GitHub mirror). But direct inspection
  revealed the SAME task definition (does a word's SEGMENTATION
  concatenate back to the surface form) would NOT test templaticity —
  the visible morpheme/clitic segmentation in that data IS concatenative
  (verified: joining segments reproduces the surface word cleanly, same
  as Hebrew/Arabic clitic-splitting generally); the actual templatic
  non-concatenativity only lives in a separate ROOT: field. Using the
  same check on this data would have shown `concatenates` holding —
  the OPPOSITE of the intended point — so stopped and redesigned rather
  than running a result that would look like it refutes the paper's own
  claim for the wrong reason.

  Designed a templatic-analogue check instead (`run_templatic_check.py`):
  is a gold root's consonant skeleton (orthographically normalised,
  diacritics stripped) a SUBSEQUENCE of the gold surface word's? Applied
  to gold only (50,269 real word-root pairs from the full Quran text),
  no model involved — same gold-only design as the SIGMORPHON finding.
  Real result, saved to `code/out/templatic_check.json`: fails 27.2%
  of the time (Wilson 95% CI [26.8%, 27.6%]) — within noise of
  SIGMORPHON's own 27% for a completely different check/language/
  phenomenon. Wrote this into Limitations as a genuine finding, explicit
  that the match could be coincidence at n=1 comparison, and explicit
  about what's STILL not done (the model-facing half: whether an LLM's
  predicted roots show the same delta pattern, which needs its own
  admissible label and generation harness — real future work, not
  claimed as done). Added a verified citation (Dukes & Habash 2010,
  LREC, confirmed against the ACL Anthology directly) to
  `soundver_refs.bib` for the data source.

- [x] **P11. A second independent implementation of the IE or
  morphology checker stack.** Done.
  Chose IE over morphology because IE's `no_overlap` had a real,
  found-and-fixed bug this session (the `str.find()` first-occurrence
  bug), giving something concrete to cross-check. Confirmed by direct
  code inspection BEFORE running anything that `version2/ie_task.py`'s
  `_find_span` has the identical bug (independent confirmation two
  authors made the same natural mistake). Built
  `b17_ie_checker_comparison.py` on the B17-SQL precedent: converts
  v3's slot-filling format to v2's entity-list format so both checkers
  score the same extracted spans. Caught and fixed a real bug in the
  comparison script itself before trusting it: v2's `label_correct()`
  re-parses raw text expecting a JSON list, but v3's model output is
  always a JSON object, so calling it directly would always report
  "wrong" — fixed to use the paper's own canonical `_field_value_match`
  label on the already-parsed object instead. Ran a 10-instance smoke
  test (clean) before the full 100-instance x 4-model run (2,000
  candidates, matching B17-SQL's exact scale).

  Real result: 1.25% overall disagreement (25/2,000) — six times SQL's
  0.2%, still small. One real model-level finding, the reverse pattern
  from SQL's: for Llama-3.1-8B, this paper's checker measures
  delta=2.38% against the second implementation's 0.00% on the SAME
  candidates. Investigated before writing anything: this is NOT the
  no_overlap bug resurfacing — it's IE's already-documented,
  model-specific content-vs-format disagreement (Llama-3.1-8B omitting
  empty-list fields). Traced to a real structural difference: v3's
  `required_fields` checks the parsed OBJECT has all 4 top-level keys;
  v2's checks each item in a converted ENTITY LIST has both required
  keys, which is vacuously true for an empty list, so it never flags a
  bare `{}` as missing fields. Two checkers testing genuinely different
  things about the same leak, not a disagreement about what the leak
  is — written up with that precision rather than left ambiguous.
  Added as a new paragraph continuation right after the existing B17
  (SQL) paragraph in Findings.

---

## Verification discipline (carried over, still binding)

Every number written into `soundver_main.tex` must be pulled from an
actual saved/computed output file and cross-checked before the edit —
never from memory or extrapolation. After any edit: check brace depth
(`content.count('{') - content.count('}')` == 0) and even dollar count,
same as every prior edit this session.
