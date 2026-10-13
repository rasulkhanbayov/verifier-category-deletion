# version4 paper

- `main.tex`: the paper (ACL template, review mode). Compile:
  `pdflatex main && bibtex main && pdflatex main && pdflatex main`
  (needs pgfplots, tikz, siunitx, threeparttable, booktabs, multirow).
- `make_numbers.py`: regenerates `gen/` (all tables, figure coordinates and
  in-text number macros) from `../code/out/`. Never edit `gen/` by hand.
- `refs.bib` = `refs_v3.bib` + `new_refs.bib` (11 papers verified against
  arXiv on 2026-10-10) + `classic_refs.bib` (Clopper-Pearson, rule of three).
- Not compiled in the authoring environment (no LaTeX there): check page
  count (8 pages main body for ACL long papers) and fix overfull boxes.
- refs.bib is built as: cat refs_v3.bib new_refs.bib classic_refs.bib review_refs.bib lit_refs.bib > refs.bib
  (review_refs.bib: 11 related-work entries verified 2026-10-12: LtT, CRC,
  conformal LM, conformal factuality, data programming, Snorkel, group DRO,
  DeepSeekMath/GRPO, Qwen3, Few-NERD, Glaive FC dataset).
- v4.1 (2026-10-12): `main.tex` and `make_numbers.py` are the v4.1 rewrite
  ("When Verifiers Delete Categories"). The v4.0 draft is kept as
  `main_v4.0.tex` / `make_numbers_v4.0.py`. `gen/fig_tradeoff.tex` is
  generated but not included in the body.
- lit_refs.bib (2026-10-13 novelty audit): 11 entries, each with a comment
  naming the page it was checked against (Zhao 2013, Lipton 2014, SPADE,
  EvalGen, CodeContests+, SAFER, Rigollet & Tong 2011, Zhou 2026, Gururangan
  2022, Yue 2025, Oakden-Rayner 2020). Full audit notes were in the session
  scratchpad (lit_A/B/C.md); summary in ../PLAN.md section 10.
- Figures: `../.venv_train/bin/python make_figures.py` writes gen/fig_downstream.{pdf,png}
  from ../code/out/ (matplotlib lives only in .venv_train). The old unused
  pgfplots trade-off figure was removed (it used the uncorrected bound).
- gen/tab_cert.tex, tab_distill.tex, tab_filter.tex, tab_main.tex are produced
  only by make_numbers_v4.0.py for the archived main_v4.0.tex; main.tex does
  not use them.
- Figures (make_figures.py, run with ../.venv_train/bin/python): fig_overview
  (main, page-2 teaser; TikZ alternative fig_overview_tikz.tex, uncompiled
  here), fig_mechanism (main, §4; data from code/out/figdata_mechanism.json
  via `python -m certver.figdata`), fig_downstream (main, §7.2),
  fig_validity and fig_cost (appendix). figure_prompts_paperbanana.md holds
  PaperBanana prompts generated from gen/numbers.tex.
