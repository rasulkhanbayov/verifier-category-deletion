"""
Restore the large generated files from Hugging Face into their repository
paths and verify them against data/manifest.json.

  python scripts/hf_download.py                  # public data
  python scripts/hf_download.py --private         # also CoNLL (needs access)
  python scripts/hf_download.py --only out/verdicts

Repositories: data/manifest.json (public data and private CoNLL).
"""
import argparse, hashlib, json, os
from huggingface_hub import snapshot_download

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--user", default=None, help="only to override the repositories in data/manifest.json")
    ap.add_argument("--private", action="store_true"); ap.add_argument("--only", default=None,
                    help="path prefix, e.g. out/verdicts or data/raw/ie_data")
    a = ap.parse_args()
    man = json.load(open(os.path.join(ROOT, "data", "manifest.json")))
    kinds = ["public"] + (["private"] if a.private or (a.only or "").startswith("data/raw/ie_data") else [])
    for kind in kinds:
        files = [e for e in man["files"] if e["repo"] == kind and (not a.only or e["path"].startswith(a.only))]
        if not files:
            continue
        repo = man[f"{kind}_repo"].replace("<HF_USER>", a.user or "")
        snapshot_download(repo_id=repo, repo_type="dataset", local_dir=ROOT,
                          allow_patterns=[e["path"] for e in files])
        bad = [e["path"] for e in files if not os.path.exists(os.path.join(ROOT, e["path"]))
               or sha(os.path.join(ROOT, e["path"])) != e["sha256"]]
        print(f"{kind}: {len(files) - len(bad)}/{len(files)} files verified" + (f"; FAILED: {bad[:5]}" if bad else ""))


if __name__ == "__main__":
    main()
