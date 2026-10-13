# PaperBanana prompts for "When Verifiers Delete Categories"

Generated from `gen/numbers.tex` (every number below comes from the saved
experiment outputs). PaperBanana (Zhu et al., arXiv 2601.23265, ICML 2026)
takes a **methodology description** (source context) and a **caption**
(communicative intent); each prompt below gives both, plus a visual concept
and hard constraints. Use the outputs as concept art or as a starting point
to redraw; check every label against the paper before use. The verified
matplotlib/TikZ figures in `gen/` remain the reference versions.

Shared style guidance (append to every prompt):
> Flat vector style for an ACL paper, white background, no 3D, no
> gradients, no clip-art people. Colour-blind-safe Okabe–Ito palette:
> vermillion #D55E00 for agreement-based selection (the failure), blue
> #0072B2 for budgeted selection (the remedy), grey #555555 for neutral
> elements, orange #E69F00 for injected stress-test checks. Serif labels,
> minimum 7 pt at single-column width (8.3 cm) or 6 pt at double-column
> width (17 cm). Use exactly the labels and numbers given; do not add
> numbers, equations, logos or text that are not listed.

---

## 1. Overview / teaser (double column) — "The conveyor belt with two gates"

**Source context (methodology).**
Language models write candidate Python checks for structured outputs such as
JSON entity extraction. A verifier is a conjunction of checks; it decides
which model outputs are kept for best-of-N selection, training-data
filtering and reinforcement-learning rewards. Checks are usually kept if
they agree with correctness labels (F1). On CoNLL-2003 one LLM-written check
states that "proper nouns do not belong in the miscellaneous field". Models
put many wrong entities into that field, so the check raises F1 and is
selected, but it also rejects every correct miscellaneous answer
(e.g. "German", "Euro 96"). Our alternative selects checks under a budget on
false rejection and certifies the selected verifier on held-out model
outputs.

**Caption (intent).** Two ways to select LLM-written checks from the same
candidate pool. Agreement keeps a check whose rejected outputs are mostly
wrong, although they include every correct answer of one category, and the
category disappears downstream; a false-rejection budget refuses the check
and the result is certified.

**Visual concept (creative).** A factory conveyor belt carrying small
document cards, each card showing an entity extraction output; some cards
carry a small tag "misc: German" or "misc: Euro 96" (correct answers, drawn
with a thin green tick) and others are visibly malformed (wrong, thin red
cross). The belt splits into two lanes.
Top lane (vermillion): a gate labelled "Select by agreement (F1)" with a
scoreboard reading "F1 ↑". The gate drops *all* "misc" cards into a bin,
including the ticked ones. After the gate, a small student robot reading the
kept cards has an empty "misc" slot; a caption bubble reads
"student recall 0.08" and "RL recall 0.37 → 0.11".
Bottom lane (blue): a gate labelled "Select under a budget" with a small
gauge "false rejections ≤ τ/2" whose needle stays in the green zone; the
gate lets ticked misc cards pass. A wax-seal stamp reading "certified on
held-out model outputs" sits on the lane. The student robot's "misc" slot
is filled; bubble: "student recall 0.31", "RL recall 0.40".
**Hard constraints.** Exactly two lanes; label text exactly as quoted;
numbers only 0.08, 0.31, 0.37, 0.11, 0.40, 84% (the share of
miscellaneous sentences whose every correct output is discarded, shown on
the top bin as "84% of misc. sentences lose every correct output").

---

## 2. Mechanism — "The break-even balance"

**Source context.** Adding a check to a verifier rejects a set of outputs.
F1 rises exactly when the precision of that rejected set is below half the
current F1 (the break-even precision F1/2), no matter whose outputs they are.
On CoNLL the miscellaneous outputs are correct at rate 0.23, below the
threshold 0.32, so a check that rejects all of them raises F1 even
though it deletes the category. A budget on the fraction of inputs with a
correct output rejected forbids it, whatever its precision.

**Caption (intent).** Agreement weighs only how precise the rejected set
is, never whose outputs it contains; below the break-even precision F1/2
it will reject a whole category.

**Visual concept (creative).** A two-pan balance scale. Left pan: a pile of
rejected *wrong* outputs (red crosses), large. Right pan: a pile of
rejected *correct* outputs (green ticks), smaller, all wearing the same
"misc" badge. The beam tilts toward "F1 ↑". A dial on the fulcrum marks
"break-even precision = F1/2 = 0.32" and a pointer at
"rejected precision = 0.23". To the right, a separate blue
"budget" padlock is clamped on the right pan with the label "γ ≤ τ":
whatever the tilt, the padlock stops the whole category from being
removed.
**Hard constraints.** No other numbers; the text "F1/2" must appear; do not
draw any equation other than "F1/2" and "γ ≤ τ".

---

## 3. Propagation — "The fading colour"

**Source context.** The verifier filters distillation data and gates RL
rewards. With the F1-selected verifier, the filtered CoNLL training data
keeps 612 miscellaneous entities, none title-case, 8% correct
(certified filtering: 1,659, 58% title-case, 26% correct). Students
distilled from it recall 0.08 of miscellaneous entities (certified:
0.31); removing only the deleting check restores 0.34. A policy whose
RL reward is gated by the F1-selected verifier falls from recall 0.37 to
0.11 in every one of four seeds; with the certified gate it ends at 0.40.

**Caption (intent).** A category removed by the verifier is learned away:
it fades from the filtered data, from the distilled student and from the
RL policy, while overall accuracy stays similar.

**Visual concept (creative).** Three panels left to right — "filtered
data", "distilled student", "RL policy" — each a small grid of coloured
tiles, one colour per entity type. In the vermillion row (agreement), the
"misc" colour fades from saturated to almost white across the three panels;
in the blue row (budgeted), it stays saturated. A thin accuracy bar under
each panel stays the same length in both rows.
**Hard constraints.** Tile colours are illustrative only; print the recall
numbers exactly as listed above under the student and RL panels.

---

## 4. Certification protocol — "Select on A, certify on B"

**Source context.** Split A (1,000 inputs) is used to choose checks under
the budget γ̂_A ≤ τ/2. Split B (1,000 disjoint inputs, gold plus a greedy
output and three samples from each of three models) is used only to
certify: k inputs with a rejected correct output give a one-sided
Clopper–Pearson upper bound U_B on γ, Bonferroni-corrected over the budgets
τ ∈ {1, 2, 5}%, and the smallest certified τ is reported.

**Caption (intent).** Selection and certification use disjoint labelled
splits of model outputs, so the bound on how often correct outputs are
rejected is valid for the selected verifier.

**Visual concept (creative).** Two stacked trays of index cards, "split A"
and "split B", separated by a dashed wall. A hand-shaped selector picks
check cards only from tray A into a "verifier" folder; a magnifying glass
over tray B reads "k of 1,000 inputs" and outputs a ruler marked "U_B" with
three notches "1% · 2% · 5%"; the smallest notch above U_B lights up.
**Hard constraints.** Labels exactly: "split A", "split B", "verifier",
"U_B", "1% · 2% · 5%", "k of 1,000 inputs". No other numbers.

---

## 5. Statistical plot (PaperBanana plot mode) — downstream recall

**Source context / data (exact values, one per seed).**
Distillation, miscellaneous recall on CoNLL test (555 inputs):
F1 filter 0.056, 0.095, 0.103; F1 without the deleting check 0.325, 0.349,
0.341; certified 0.31, 0.31, 0.31; certified size-matched 0.278, 0.302,
0.278; label-filtered 0.365.
RL (GRPO, 200 steps): label reward 0.421, 0.548; certified gate 0.317,
0.437, 0.492, 0.373; F1 gate 0.135, 0.087, 0.151, 0.079; starting recall
0.365 (dashed line).

**Caption (intent).** The deleted category is learned: recall collapses only
when the deleting check filters the data or gates the reward.

**Plot spec.** Two panels sharing a y-axis "Misc. entity recall" from 0 to
0.6 (no truncation); one marker per seed with a short bar at the mean;
vermillion for F1, orange for F1 without the check, blue for certified,
light blue for size-matched, dark grey for label. Do not interpolate, smooth
or add error bars that are not in the data.

---

## 6. Statistical plot — the two ingredients (scatter)

**Data.** Use `../code/out/figdata_mechanism.json`: for each candidate check,
x = precision of rejected outputs ÷ (F1/2) of its task, y = largest share
of a group's inputs it loses (387 points). Highlight kind == "deleter"
(star, vermillion), "injected" (diamond, orange), "casing" (plus, light
blue); all others grey. Shade x < 1 and y ≥ 0.5.

**Caption (intent).** Only checks that both raise F1 and wipe out a group are
dangerous; agreement takes exactly those (8 checks: the CoNLL deleting
check and 7 injected stress-test checks).

**Plot spec.** x from 0 to 3 (state that 5 points with x > 3 are drawn at
the edge), y from 0 to 1.05, dashed line at x = 1, dotted at y = 0.5.
