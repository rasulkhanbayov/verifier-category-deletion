# soundver — project context

## Status (2026-10-08)

NOT being submitted to the ARR October 2026 cycle. The work is being
reframed as "certified verifier synthesis" in `../version4/` (see
`../version4/PLAN.md`). Treat this directory as frozen source material:
reuse its theory, audit findings and harness, but don't modify it in place.

## What this is

"Soundness Is a Measurement, Not an Argument: Auditing Free Verifiers in
Structured NLP." Targeting COLING 2027 Main Track (ARR October 2026
cycle, deadline 12 Oct 2026), currently also weighing NAACL. Main file:
`soundver_main.tex`. Task tracker: `plans.md` — check it first, update
it as items close.

## The paper's core argument

Well-formedness checks (SQL parses/executes, a record validates against
its schema) are trusted as free, sound verifiers for test-time scaling
and RLVR — but soundness is a task-level *argument*, not a measured
property of the implementation. The paper builds a three-step audit
(Def. 2 admissibility, measure delta against a label that doesn't
presuppose the check, classify any delta>0 as an implementation bug or a
genuine scope failure) and runs it over 3 tasks (SQL/Spider,
IE/CoNLL2003, morphology/SIGMORPHON) x 6 models across three vendor
families (OpenAI: GPT-4o, GPT-4o-mini; Meta: Llama-3.1-8B,
Llama-3.1-70B; Alibaba: Qwen2.5-7B, Qwen2.5-72B), 5-seed replicated for
all six.

## Key result, and the one thing to never forget

**3 of the paper's 18 (task, model) cells are certified sound under
5-seed replication, all IE, spanning 2 of the 3 vendor families
(OpenAI's GPT-4o and GPT-4o-mini, and Alibaba's Qwen2.5-72B) — no
Llama/Meta cell has ever certified, on any task, at any seed.**
SQL/Llama-3.1-70B looked sound at seed 0 (delta=0.0000) but leaked at
all 4 other seeds (delta=0.0005-0.0027) — a lucky zero count, not a
real certification. SQL/Qwen2.5-72B is a DIFFERENT, weaker case: its own
seed-0 delta was already nonzero (0.0002) — it never certified even
once, at any seed, so it is not a "false certification" the way
Llama-70B is, just a cell that never qualified. **Do not describe the 3
surviving cells as spanning "three vendor families" — this exact wrong
phrase was written into 4 different places during integration and had
to be caught and fixed; the surviving cells are 2-of-3 OpenAI, 1-of-3
Alibaba, zero Meta.** This is written up in "B4: what replication
changes" and threaded through every table/paragraph that cites cell
counts (all reconciled as of 2026-09-30's full Qwen integration pass —
see `plans.md`'s P9 entry for the complete list of what was touched and
the two real errors caught and fixed along the way).

Only **one** confirmed scope failure overall: morphology's
`concatenates` check, because SIGMORPHON English gold segmentations are
canonical, not surface (27% fail, 95% CI [21%,34%]). SQL and IE's own
residual deltas (across all 6 models now) trace to checker-implementation
bugs or model-specific content/format quirks (documented per-model),
not scope failures — do not count them as findings about the tasks.

## Verification discipline (binding, not optional)

Every number written into `soundver_main.tex` must come from an actual
saved/computed output file — never from memory, extrapolation, or "this
sounds about right." This project caught and fixed several real
fabrication near-misses this way (a stale TikZ figure with placeholder
epsilon values that didn't match any real data; a rule-of-three bound
computed with the wrong denominator; a table row bolded from a since-
overturned seed-0 result). After any edit to the .tex file, check:
- brace balance: `content.count('{') - content.count('}')` == 0
- even dollar-sign count (unclosed math mode)
- no dangling `\ref`/`\label` (every `\ref{x}` has a matching `\label{x}`)
- every `\cite` key exists in `soundver_refs.bib` and vice versa

## Where things live

- `soundver_main.tex` — the paper.
- `soundver_refs.bib` — bibliography; check licenses/venues were
  actually verified before trusting an entry (some earlier placeholder
  author lists were caught and fixed this session).
- `code/soundver/` — the actual measurement harness (`generate.py`,
  `checks.py`, `rates.py`, `reconcile.py`, `validity.py`). This is what
  produces every real number in the paper; nothing should be hand-typed.
- `code/data/records_*_seed{0,1,2,3,4}.jsonl` — per-instance records,
  one row per (task, model, seed, instance, candidate). No raw generated
  text is stored (only booleans) except in the small B8-V1 label-audit
  sample (`code/out/label_audit/`), which does store raw text since a
  human needs to read it.
- `code/out/` — reconciled tables/rates, one JSON/tex-fragment per
  task, produced by `reconcile.py`. Paste numbers from here into the
  paper verbatim, never retype by hand.
- `progress_notes/session_status.md` — chronological log of what was
  done, bugs found/fixed, and why. Read this for history; `plans.md` is
  the forward-looking task list.
- `dpc_repo/` — a clone of the official DPC baseline
  (github.com/HKUSTDial/DPC), used to run the DPC comparison row in
  `tab:main` rather than reimplementing it from scratch.

## Known-open items (see plans.md for the full strengthening list)

- **B8-V1 — DONE (2026-10-07).** Two annotators scored the 444-item sample
  (alpha=0.783). IE's automatic label is wrong on 7.4% of accepted-incorrect
  outputs, so the IE ceilings are reported both uncorrected and corrected
  (5-seed: 2.88+-0.72 GPT-4o, 3.20+-1.02 GPT-4o-mini); the near-exhaustion
  claim for IE is withdrawn per the pre-registered reading. Use IE-specific
  lambda, never the cross-task pooled 0.245 (it imports SQL/morph label
  errors). Numbers come from `code/out/label_audit/b8_v1_score_output.txt`.
  User confirmed (2026-10-07) the annotators were two independent people;
  flag removed.
- **E1 ethics sentence — RESOLVED (2026-10-07).** User confirmed the
  independent human verification of every numbered result happened and
  the sentence is correct; both red flags removed, sentence kept as is.
  The paper has no `\textcolor{red}` notes left.
- **`generate.py` had two real, now-fixed bugs, found while collecting
  the third model family (P9, Qwen).** Both were found the hard way
  (multiple real stalls/data-loss incidents during actual collection,
  not caught by unit-level testing), so read both before assuming the
  harness "just works" against a new model:

  1. **No timeout on a per-instance future, so one stuck instance could
     block the whole batch forever.** `ThreadPoolExecutor` +
     `as_completed()`'s no-timeout wait meant ONE never-completing
     future blocked progress indefinitely even with every other future
     already done (this looked at first like a SQLite/query-execution
     hang, but the real cause turned out to be bug 2 below — a 429/504
     retry loop that used to give up almost instantly, which then LOOKED
     like a hang from the caller's perspective because `_complete`
     itself raised quickly and the whole (task,model,seed) cell then
     failed near-100%, not because any single call blocked forever. The
     ~95-99 "extra threads" seen while debugging this were a red
     herring — `import numpy` alone spawns one idle BLAS worker thread
     per CPU core (48 on this machine) at import time, completely
     unrelated to any bug.). Fixed anyway, since it's real and correct
     defense-in-depth regardless of root cause: the per-model loop now
     uses `concurrent.futures.wait(..., timeout=SOUNDVER_INSTANCE_TIMEOUT,
     return_when=FIRST_COMPLETED)` (env-var tunable, default 180s) and
     skips any future still pending as a logged hard-timeout error,
     plus `pool.shutdown(wait=False)` (not a `with` block, which itself
     blocks on `shutdown(wait=True)`) and `os._exit()` at the very end
     of `__main__` (ThreadPoolExecutor workers are not daemon threads,
     so Python normally blocks at process exit on an abandoned one).

  2. **The real cause: `_complete`'s retry logic treated 429 (Too Many
     Requests) and 504 (Gateway Timeout) the same as any transient
     network error — 3 retries, ~7s total backoff — nowhere near
     enough to survive real provider-side rate-limiting.** This let
     entire (task, model, seed) cells fail almost completely under
     sustained load (confirmed: sql/seed2's 72B model got 0/6600
     records, ie/seed0's 72B got 957/6600). The OpenRouter account
     itself is a dollar-credit account (`/api/v1/auth/key`, $700 limit,
     not a fixed requests/interval cap), so this is most likely
     provider-side throttling specific to the two Qwen models' backend
     under new sustained load, not an account-level limit. Fixed: 429/504
     now get their own branch with a much longer backoff (10s base,
     exponential, capped at 120s, respecting a `Retry-After` header if
     present) and retries raised 3->6.

  Deliberately did NOT touch `version2/spider_task.py` (where SQL
  execution actually happens) for either fix — that file is the frozen,
  independent-by-design codebase B17's inter-implementer comparison
  depends on staying unmodified.

- **Third model family (P9) — DONE.** `qwen/qwen-2.5-7b-instruct` and
  `qwen/qwen-2.5-72b-instruct` (via OpenRouter; the locally-cached
  Qwen2.5-14B was never used — not served on OpenRouter, doesn't fit
  the P100's 16GB VRAM). Both added to `generate.py`'s
  `LLAMA_NO_SNAPSHOT` set (no dated snapshot on OpenRouter for either).
  Collection hit two real, now-fixed bugs along the way (inadequate
  429/504 backoff; a self-inflicted timeout shorter than 72B's honest
  ~8min/instance serial cost) — full debugging history in `plans.md`'s
  P9 entry, worth reading before assuming you understand
  `generate.py`'s failure modes. Fully reconciled and integrated into
  the paper (2026-09-30): E0, E2, E3, E4, Table 3, tab:params,
  tab:params-morph, tab:stack-breakdown, the claims table, the
  contamination paragraph, and fig:two-rates all now include all 6
  models. E5 (confidence-gate floor test) and B17 (inter-implementer
  agreement) and B8-V2 (prompt sweep design) remain explicitly scoped
  to the original 4 models — E5 because neither Qwen model returns
  per-token logprobs from any OpenRouter provider (checked directly),
  the other two as a stated time-scoping choice, not silently left
  ambiguous. `generate.py` has a real gap worth fixing sometime: it
  only writes records to disk once per (task, model) pair, not
  incrementally, so a stall/kill mid-model loses all of that model's
  progress for that seed rather than just the last few instances.
- Full strengthening/audit task list: `plans.md`.

## Working style for this project (carried over from session history)

- Prefer running the actual harness over hand-computing or estimating a
  number, even when the estimate seems obviously right.
- When a result contradicts an earlier draft's claim (like B4 did),
  write up the honest result and fix every downstream table/paragraph
  that cited the old number — don't leave a stale claim standing next
  to the correction.
- Flag genuine human-judgment gates (ethics sentence, label annotation)
  rather than attempting to resolve them as an AI — these are explicitly
  not substitutable per the paper's own stated epistemics.
- No LaTeX compiler available in this environment — verify structural
  integrity (braces, refs, cites) via Python/grep checks instead of
  compiling. Flag to the user if a real compile + `measure_pages.py`
  page-count check is needed before submission.
