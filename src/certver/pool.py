"""
certver.pool -- generate candidate pools WITH raw text, for any split.

  python -m certver.pool --task sql --split test --models openai/gpt-4o-mini-2024-07-18 \
      --instances 100 --candidates 32 --max-cost 2.0

One JSON line per (task, model, split, seed, instance, candidate):
  raw text, admissible label `correct`, version3's hand-written check verdicts,
  serving provider, prompt/completion tokens and the call's dollar cost.
Instance context (schema, db path, text, gold) goes to a side file once per
instance, so synthesized checks can later be run on (raw, item) offline.

Differences from soundver.generate, each fixing a known version3 gap:
  - raw text is kept (version3 stored only booleans, so new checks could not
    be evaluated on its records);
  - each instance is appended as soon as it finishes, and a re-run skips
    instances already complete (version3 wrote once per model, so a kill lost
    everything for that model);
  - every call's cost is logged and the run stops at --max-cost;
  - SQL is labelled with certver.sqllabel (original DB + distilled copies,
    multiset, column-permutation tolerant), not version2's subsample-only
    test_suite_accuracy, which mislabels about 3-4% of outputs each way;
    instances whose gold query fails on the original DB are excluded.
"""
from __future__ import annotations
import argparse, concurrent.futures, json, os, sys, threading, time

from soundver import generate as g
from soundver.checks import sql_extract
from .data import load_split
from .sqllabel import sql_correct, GoldError

PRICE_CHECK_URL = "https://openrouter.ai/api/v1/auth/key"


def key_usage() -> float:
    import requests
    r = requests.get(PRICE_CHECK_URL, headers={"Authorization": f"Bearer {g._api_key()}"},
                     timeout=30)
    r.raise_for_status()
    return float(r.json()["data"]["usage"])


def complete(model: str, prompt: str, temperature: float, max_tokens: int,
             retries: int = 6, reasoning: dict | None = None) -> dict:
    """One chat completion. Same retry policy as soundver.generate._complete,
    plus token usage and cost from OpenRouter's usage accounting."""
    import requests
    headers = {"Authorization": f"Bearer {g._api_key()}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}],
               "temperature": temperature, "max_tokens": max_tokens,
               "usage": {"include": True}}
    if reasoning is not None:
        payload["reasoning"] = reasoning
    last_err = None
    for attempt in range(retries):
        try:
            resp = requests.post("https://openrouter.ai/api/v1/chat/completions",
                                 headers=headers, json=payload, timeout=600 if reasoning is not None else 60)
            if resp.status_code in (429, 504):
                ra = resp.headers.get("Retry-After")
                try:
                    delay = float(ra) if ra is not None else 10.0 * 2 ** attempt
                except ValueError:
                    delay = 10.0 * 2 ** attempt
                last_err = f"{resp.status_code} rate/gateway limited"
                time.sleep(min(delay, 120.0))
                continue
            resp.raise_for_status()
            data = resp.json()
            u = data.get("usage") or {}
            return {"text": data["choices"][0]["message"]["content"] or "",
                    "provider": data.get("provider"),
                    "prompt_tokens": u.get("prompt_tokens"),
                    "completion_tokens": u.get("completion_tokens"),
                    "cost": float(u.get("cost") or 0.0),
                    "finish_reason": data["choices"][0].get("finish_reason")}
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"OpenRouter call failed after {retries} attempts: {last_err}")


def _item_context(task: str, item: dict) -> dict:
    ctx = dict(item)
    if task == "sql":
        ctx["schema"] = {t: sorted(cs) for t, cs in item["schema"].items()}
    return ctx


def _done_instances(path: str, n_per_instance: int) -> set:
    counts = {}
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                if line.strip():
                    d = json.loads(line)
                    k = (d["model"], d["seed"], d["instance_id"])
                    counts[k] = counts.get(k, 0) + 1
    return {k for k, c in counts.items() if c >= n_per_instance}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", required=True, choices=["sql", "ie", "morph", "math", "fewnerd", "fc"])
    ap.add_argument("--split", required=True, choices=["proposal", "admit", "certify", "distill", "test", "fresh"])
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--seeds", nargs="+", type=int, default=[0])
    ap.add_argument("--instances", type=int, default=None)
    ap.add_argument("--candidates", type=int, default=32)
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--max-cost", type=float, required=True,
                    help="stop submitting new instances once this run's logged cost reaches it")
    ap.add_argument("--global-cap", type=float, default=427.70,
                    help="abort before starting if the key's total usage is at or above this")
    ap.add_argument("--out-dir", default="data")
    a = ap.parse_args(argv)

    for m in a.models:
        g.check_snapshot(m)
    start_usage = key_usage()
    print(f"key usage at start: ${start_usage:.4f} (global cap ${a.global_cap:.2f})", flush=True)
    if start_usage >= a.global_cap:
        print("global cap reached; nothing run.")
        return 3

    os.makedirs(a.out_dir, exist_ok=True)
    max_tokens = {"sql": 256, "ie": 512, "morph": 64, "math": 512, "fewnerd": 512, "fc": 256}[a.task]
    n_per = 1 + a.candidates
    lock = threading.Lock()
    spent = [0.0]
    stop = threading.Event()

    for seed in a.seeds:
        items = load_split(a.task, a.split, a.instances, seed)
        base = os.path.join(a.out_dir, f"pool_{a.task}_{a.split}_seed{seed}")
        rec_path, ctx_path, skip_path = base + ".jsonl", base + ".items.jsonl", base + ".skipped.jsonl"
        with open(ctx_path, "w") as f:
            for it in items:
                f.write(json.dumps(_item_context(a.task, it)) + "\n")
        done = _done_instances(rec_path, n_per)

        for model in a.models:
            todo = [it for it in items if (model, seed, it["instance_id"]) not in done]
            print(f"\nseed={seed} model={model}: {len(items)} instances, "
                  f"{len(items) - len(todo)} already done, {len(todo)} to run", flush=True)

            def process_one(item):
                if stop.is_set():
                    return None, (item["instance_id"], "budget stop")
                conn = None
                try:
                    local = item
                    if a.task == "sql":
                        import sqlite3
                        try:
                            sql_correct(item["gold_sql"], item["gold_sql"], item["db_path"])
                        except GoldError:
                            return None, (item["instance_id"], "gold fails on original DB")
                        conn = sqlite3.connect(item["db_path"], timeout=5.0)
                        conn.text_factory = lambda b: b.decode("utf-8", errors="replace")
                        local = {**item, "conn": conn}
                    prompt = g.PROMPTS[a.task](item, "base")
                    rows = []
                    for c in range(-1, a.candidates):
                        r = complete(model, prompt, 0.0 if c == -1 else a.temperature, max_tokens)
                        checks, parsed = g.score_checks(a.task, r["text"], local)
                        correct = (sql_correct(sql_extract(r["text"]), item["gold_sql"], item["db_path"])
                                   if a.task == "sql" else
                                   g._label_correct(a.task, local, r["text"], parsed))
                        rows.append({"task": a.task, "model": model, "split": a.split,
                                     "seed": seed, "instance_id": item["instance_id"],
                                     "cand_idx": c, "raw": r["text"], "correct": bool(correct),
                                     "checks": {k: bool(v) for k, v in checks.items()},
                                     "provider": r["provider"],
                                     "prompt_tokens": r["prompt_tokens"],
                                     "completion_tokens": r["completion_tokens"],
                                     "cost": r["cost"]})
                    return rows, None
                except Exception as e:  # noqa: BLE001
                    return None, (item["instance_id"], str(e)[:200])
                finally:
                    if conn is not None:
                        conn.close()

            workers = int(os.environ.get("CERTVER_WORKERS", "8"))
            timeout_s = int(os.environ.get("CERTVER_INSTANCE_TIMEOUT", "900"))
            pool = concurrent.futures.ThreadPoolExecutor(max_workers=workers)
            futs = {pool.submit(process_one, it): it for it in todo}
            pending, n_done, t0 = set(futs), 0, time.time()
            with open(rec_path, "a") as rf, open(skip_path, "a") as sf:
                while pending:
                    finished, pending = concurrent.futures.wait(
                        pending, timeout=timeout_s, return_when=concurrent.futures.FIRST_COMPLETED)
                    if not finished:
                        for fu in pending:
                            sf.write(json.dumps({"model": model, "instance_id":
                                                 futs[fu]["instance_id"],
                                                 "reason": f"hard timeout {timeout_s}s"}) + "\n")
                        break
                    for fu in finished:
                        rows, err = fu.result()
                        with lock:
                            if err:
                                sf.write(json.dumps({"model": model, "instance_id": err[0],
                                                     "reason": err[1]}) + "\n")
                            else:
                                for row in rows:
                                    rf.write(json.dumps(row) + "\n")
                                spent[0] += sum(row["cost"] for row in rows)
                            rf.flush(); sf.flush()
                            n_done += 1
                            if spent[0] >= a.max_cost and not stop.is_set():
                                stop.set()
                                print(f"  max-cost ${a.max_cost:.2f} reached; "
                                      f"stopping new instances", flush=True)
                            if n_done % 10 == 0:
                                print(f"  {n_done}/{len(todo)} instances, "
                                      f"${spent[0]:.4f} logged, {time.time() - t0:.0f}s", flush=True)
            pool.shutdown(wait=False)

    end_usage = key_usage()
    print(f"\nlogged cost this run: ${spent[0]:.4f}; key usage delta: "
          f"${end_usage - start_usage:.4f} (now ${end_usage:.4f})", flush=True)
    return 0


if __name__ == "__main__":
    code = main()
    sys.stdout.flush(); sys.stderr.flush()
    os._exit(code)
