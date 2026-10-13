# When Verifiers Delete Categories

Code, data pointers and paper source for **"When Verifiers Delete Categories:
Agreement-Based Selection of LLM-Written Checks and a Certified Alternative"**.

Programmatic checks decide which model outputs are kept in best-of-N selection,
synthetic-data filtering and reinforcement learning, and they are increasingly
written by language models and kept if they agree with correctness labels. We
show that agreement can delete a whole category of correct outputs:

* By the break-even property of F1, adding a check raises F1 exactly when the
  precision of the outputs it rejects is below half the current F1, even if
  those outputs include every correct answer of one kind.
* On CoNLL-2003, F1 selection keeps an LLM-written check ("proper nouns do not
  belong in the miscellaneous field") whenever it is among the candidates; the
  selected verifier then discards every correct output for
  84% of sentences with a miscellaneous entity.
  Students distilled from the filtered data recall 0.08 of these
  entities instead of 0.31, and an RL policy whose reward the
  verifier gates unlearns them (recall 0.37 → 0.11±0.04 over
  4 seeds), at similar average accuracy.
* Selecting checks under a budget on the fraction of inputs with a correct
  output rejected, and certifying it on held-out model outputs with a
  Clopper–Pearson bound, deleted no category on six tasks (CoNLL-2003,
  Few-NERD, Glaive function calling, Spider SQL, GSM8K, SIGMORPHON 2022
  segmentation) with three generating models.

Honest scope: natural deletion appeared on one of six tasks; simpler safeguards
(a per-output budget, or admitting only checks that never reject gold) also
prevented it on our data; the certificate failed under Spider's train-to-dev
database shift. See `paper/CLAIM_LEDGER.md` for every claim and its evidence.

## Repository map

See **[INDEX.md](INDEX.md)** for a file-by-file guide and for which script
produces each table and figure. In short: `src/` (method code), `paper/` (LaTeX
and the scripts that generate every number and figure), `out/` (saved
results), `data/` (generated model outputs), `scripts/` (run scripts, data
download, Hugging Face transfer), `docs/` (project notes), `archive/` (earlier
versions of the project).

## Install

```bash
python3.10 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt            # analysis, tables, figures
pip install -r requirements-train.txt      # only for GPU training (see file for torch/CUDA)
export PYTHONPATH="$PWD/src"
```

## Reproduce

All commands run from the repository root.

**Level 1: tables and figures from saved results** (minutes; no GPU, no API).
Everything the paper reports is regenerated from `out/*.json`:

```bash
python paper/make_numbers.py      # paper/gen/numbers.tex and all tables
python paper/make_figures.py      # paper/gen/fig_*.pdf
cd paper && pdflatex main && bibtex main && pdflatex main && pdflatex main
```

**Level 2: analyses from saved model outputs** (CPU hours; no API).
Download the raw datasets and the generated data, then rerun selection,
certification, resampling and the audits:

```bash
bash scripts/download_data.sh                       # public datasets -> data/raw/ (+ checksum check)
python scripts/hf_download.py      # large generated files (data/MANIFEST.md)
python scripts/hf_download.py --private   # CoNLL-2003 files (access on request)
bash scripts/runs/run_apv.sh                        # curves, reports and resampling for all tasks
python -m certver.redteam --out out/redteam.json    # example audit; see INDEX.md for the rest
```

Each `scripts/runs/run_*.sh` documents its own inputs and outputs; INDEX.md
lists which run produced which result file.

**Level 3: full rerun** (API generation and GPU training).
Copy `.env.example` to `.env` and add an OpenRouter key. Generating all model
outputs and candidate checks cost about $74 in API calls
(GPT-4o-mini, Llama-3.1-70B, Qwen2.5-72B; GPT-4o and Claude Opus 5.5 as
proposers). Training ran on one NVIDIA P100 (16 GB, fp32): about 15–60 minutes
per distilled student and about one hour per 200-step GRPO run.

```bash
python -m certver.pool --task ie --split admit --models <models> --candidates 3 --max-cost <usd>
python -m certver.propose --task ie --round 0 --n 25
TRAIN_PYTHON=python bash scripts/runs/run_distill_v41.sh   # students
TRAIN_PYTHON=python bash scripts/runs/run_rl2_seeds.sh     # RL policies
```

## Data

| Dataset | Source (pinned) | Licence |
|---|---|---|
| CoNLL-2003 | converted JSON in a private Hugging Face dataset | Reuters RCV1 terms; not redistributable |
| Few-NERD | `DFKI-SLT/few-nerd` @ 205f3e9 | CC BY-SA 4.0 |
| Glaive function calling v2 | `glaiveai/glaive-function-calling-v2` @ e7f4b64 | Apache-2.0 |
| Spider 1.0 | official release zip (yale-lily.github.io/spider) | CC BY-SA 4.0 |
| GSM8K | `openai/gsm8k` @ 740312a (converted to JSON, byte-identical) | MIT |
| SIGMORPHON 2022 segmentation | `sigmorphon/2022SegmentationST` @ ac161e1 | see the task repository |

`scripts/download_data.sh` fetches these versions and checks them against
`scripts/data_checksums.sha256` (the files used for the paper). Generated
data (model outputs, candidate checks, distillation sets, RL generations) is
in `data/` and `out/`; files over 5 MB are on Hugging Face at
[rasulkhanbayov/verifier-category-deletion](https://huggingface.co/datasets/rasulkhanbayov/verifier-category-deletion)
(`data/MANIFEST.md`; the CoNLL-2003 files are in a separate private dataset, access on request).

## Citation

See `CITATION.cff`.

## Licence

Code: MIT (`LICENSE`). Datasets keep their own licences (table above).
