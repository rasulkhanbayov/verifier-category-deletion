# Large generated files (Hugging Face)

Files over 5 MB, the verdict cache and the SFT adapter are not in git. They are
listed file by file, with size and sha256, in `data/manifest.json`, and hosted on
Hugging Face (public: `rasulkhanbayov/verifier-category-deletion`; private,
CoNLL-2003 only: `rasulkhanbayov/verifier-category-deletion-conll`).

Restore: `python scripts/hf_download.py` (add `--private` for CoNLL).
Upload (maintainers): `bash scripts/hf_upload.sh`.

| Folder | Dataset | Files | Size (MB) | Contents |
|---|---|---|---|---|
| `data/distill` | public | 4 | 41.1 | distillation pool and SFT sets |
| `data/distill_fewnerd` | public | 4 | 44.7 | Few-NERD distillation data |
| `data/fresh` | public | 4 | 72.8 | fresh test draws (300 inputs) |
| `data/fresh_weak` | public | 2 | 30.4 | fresh draws from weaker models |
| `data/pools` | public | 10 | 76.9 | splits A and B (gold + greedy + 3 samples per model) |
| `data/pools_weak` | public | 2 | 17.6 | weaker-model pools |
| `data/raw/ie_data` | private | 4 | 4.6 | CoNLL-2003 in the JSON format used (private) |
| `data/rl` | public | 3 | 40.4 | RL generations, logs and the SFT starting adapter |
| `data/test` | public | 18 | 206.8 | development test draws (3 x 200 inputs, greedy + 32 samples per model) |
| `out/verdicts` | public | 3827 | 206.1 | cached check verdicts per candidate and pool (regenerable, several CPU hours) |
| **total** | | 3878 | 742 | |
