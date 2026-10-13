#!/bin/bash
# Upload the large generated files listed in data/manifest.json to Hugging Face.
#
#   bash scripts/hf_upload.sh                 # public data + private CoNLL
#   bash scripts/hf_upload.sh public          # only the public dataset
#   bash scripts/hf_upload.sh private         # only the private CoNLL dataset
#   bash scripts/hf_upload.sh all --dry-run   # stage and list, upload nothing
#
# Repositories come from data/manifest.json:
#   public : rasulkhanbayov/verifier-category-deletion        (dataset)
#   private: rasulkhanbayov/verifier-category-deletion-conll  (dataset, private;
#            CoNLL-2003 is not redistributable)
# Files keep their repository paths, so scripts/hf_download.py restores them in
# place. Staging uses hard links (no extra disk space). An interrupted upload
# resumes if the same command is run again.
#
# Needs: the `hf` CLI (pip install huggingface_hub), python3, and `hf auth login`.
set -euo pipefail
cd "$(dirname "$0")/.."              # repository root

WHICH="${1:-all}"
DRY_RUN=false
[ "${2:-}" = "--dry-run" ] || [ "${1:-}" = "--dry-run" ] && DRY_RUN=true
[ "$WHICH" = "--dry-run" ] && WHICH=all
case "$WHICH" in all|public|private) ;; *) echo "usage: $0 [all|public|private] [--dry-run]"; exit 1;; esac

MANIFEST=data/manifest.json
[ -f "$MANIFEST" ] || { echo "missing $MANIFEST"; exit 1; }
if ! $DRY_RUN; then
  command -v hf >/dev/null || { echo "the 'hf' CLI is not installed: pip install huggingface_hub"; exit 1; }
  hf auth whoami >/dev/null 2>&1 || { echo "not logged in: run 'hf auth login' first"; exit 1; }
fi

repo_of()  { python3 -c "import json,sys; print(json.load(open('$MANIFEST'))[sys.argv[1] + '_repo'])" "$1"; }
paths_of() { python3 -c "import json,sys; [print(e['path']) for e in json.load(open('$MANIFEST'))['files'] if e['repo'] == sys.argv[1]]" "$1"; }

STAGE=""
cleanup() { [ -n "$STAGE" ] && rm -rf "$STAGE"; }
trap cleanup EXIT

for KIND in public private; do
  [ "$WHICH" = all ] || [ "$WHICH" = "$KIND" ] || continue
  REPO="$(repo_of "$KIND")"
  STAGE="$(mktemp -d "$PWD/.hf_stage_${KIND}_XXXX")"

  # stage every file of this kind at its repository path (hard link, else copy)
  n=0; missing=0; bytes=0
  while IFS= read -r P; do
    if [ ! -f "$P" ]; then echo "MISSING: $P"; missing=$((missing + 1)); continue; fi
    mkdir -p "$STAGE/$(dirname "$P")"
    ln "$P" "$STAGE/$P" 2>/dev/null || cp -p "$P" "$STAGE/$P"
    n=$((n + 1)); bytes=$((bytes + $(stat -c %s "$P")))
  done < <(paths_of "$KIND")
  cp "$MANIFEST" "$STAGE/manifest.json"
  [ "$missing" -eq 0 ] || { echo "$missing files missing; nothing uploaded for $KIND"; exit 1; }
  echo "$KIND: $n files, $((bytes / 1000000)) MB -> https://huggingface.co/datasets/$REPO"

  if $DRY_RUN; then
    echo "  (dry run) top-level folders staged: $(cd "$STAGE" && ls | tr '\n' ' ')"
  else
    PRIVATE_FLAG="--no-private"; [ "$KIND" = private ] && PRIVATE_FLAG="--private"
    hf upload "$REPO" "$STAGE" . --repo-type dataset $PRIVATE_FLAG \
      --commit-message "Add generated data for 'When Verifiers Delete Categories'"
  fi
  rm -rf "$STAGE"; STAGE=""
done
echo "done"
