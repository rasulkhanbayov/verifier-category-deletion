#!/bin/bash
# Download the public datasets into data/raw/ at the exact versions used in the
# paper, then verify them against scripts/data_checksums.sha256.
#
#   bash scripts/download_data.sh            # all datasets
#   bash scripts/download_data.sh gsm8k      # one dataset: spider gsm8k fewnerd glaive sigmorphon conll
#
# Needs: python3 with huggingface_hub and pyarrow (requirements.txt), curl,
# gdown (only for Spider: pip install gdown), unzip.
set -euo pipefail
cd "$(dirname "$0")/.."
RAW=data/raw
mkdir -p "$RAW"
want="${1:-all}"
run() { [ "$want" = all ] || [ "$want" = "$1" ]; }

hf_get() {  # repo_id revision filename local_dir
  python3 - "$@" <<'PY'
import sys
from huggingface_hub import hf_hub_download
repo, rev, fn, out = sys.argv[1:5]
hf_hub_download(repo_id=repo, repo_type="dataset", revision=rev, filename=fn, local_dir=out)
print("downloaded", repo, fn)
PY
}

if run gsm8k; then   # openai/gsm8k, licence MIT
  for s in train test; do hf_get openai/gsm8k 740312add88f781978c0658806c59bc2815b9866 "main/$s-00000-of-00001.parquet" "$RAW/math_data"; done
  # the loaders read JSON lists; this conversion reproduces the files used in the paper byte for byte
  python3 - <<'PY'
import json, pyarrow.parquet as pq
for s in ("train", "test"):
    rows = pq.read_table(f"data/raw/math_data/main/{s}-00000-of-00001.parquet").to_pylist()
    open(f"data/raw/math_data/{s}.json", "w").write(json.dumps(rows))
PY
fi

if run fewnerd; then   # DFKI-SLT/few-nerd, supervised split, licence CC BY-SA 4.0
  for s in train validation test; do hf_get DFKI-SLT/few-nerd 205f3e9c9f3577ea2561d43f2f62dc249ab92d5b "supervised/$s-00000-of-00001.parquet" "$RAW/fewnerd_data"; done
fi

if run glaive; then   # glaiveai/glaive-function-calling-v2, licence Apache-2.0
  hf_get glaiveai/glaive-function-calling-v2 e7f4b6456019f5d8bcb991ef0dd67d8ff23221ac glaive-function-calling-v2.json "$RAW/fc_data"
fi

if run sigmorphon; then   # SIGMORPHON 2022 shared task 1 (English word level), licence: see the task repository
  mkdir -p "$RAW/morph_data"
  C=ac161e1107e423577e922b05f8c43c6ebad6722a
  for f in eng.word.train.tsv eng.word.dev.tsv eng.word.test.gold.tsv; do
    curl -sL -o "$RAW/morph_data/$f" "https://raw.githubusercontent.com/sigmorphon/2022SegmentationST/$C/data/$f"
  done
fi

if run spider; then   # Spider 1.0 (Yu et al., 2018), licence CC BY-SA 4.0; official release zip
  # official download page: https://yale-lily.github.io/spider (Google Drive file "spider_data.zip")
  mkdir -p "$RAW/spider_data"
  if [ ! -f "$RAW/spider_data/spider_data.zip" ]; then
    gdown 1403EGqzIDoHMdQF4c9Bkyl7dZLZ5Wt6J -O "$RAW/spider_data/spider_data.zip" || {
      echo "Automatic download failed: download spider_data.zip from https://yale-lily.github.io/spider"
      echo "into $RAW/spider_data/ and rerun this step."; exit 1; }
  fi
  unzip -q -o "$RAW/spider_data/spider_data.zip" -d "$RAW/spider_data"
fi

if run conll; then   # CoNLL-2003 in the JSON format used here (Reuters licence: not redistributable)
  # The converted files are in a PRIVATE Hugging Face dataset; request access, then:
  python3 scripts/hf_download.py --only data/raw/ie_data || {
    echo "CoNLL-2003: see README.md (Data) for access; the original corpus requires the Reuters RCV1 licence."; }
fi

echo "verifying checksums (only files that are present) ..."
( cd "$RAW" && while read -r sum path; do
    [ -f "$path" ] || continue
    echo "$sum  $path" | sha256sum -c --quiet - || echo "MISMATCH: $path"
  done < ../../scripts/data_checksums.sha256 )
echo "done"
