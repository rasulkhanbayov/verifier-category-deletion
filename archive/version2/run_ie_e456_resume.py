#!/usr/bin/env python3
"""One-off resume: only llama-3.1-70b, appended to the existing 3-model
pilot_ie_e456_results.json after the original run died silently
mid-model (no traceback captured -- likely killed externally on this
shared machine, not a code bug)."""
import json
import run_ie_e456_pilot as p

OUT_PATH = p.OUT_PATH
MODEL = "llama-3.1-70b"

with open(OUT_PATH) as f:
    results = json.load(f)

assert all(r.get("model") != MODEL for r in results), f"{MODEL} already present"

try:
    result = p.run_for_model(MODEL)
except Exception as e:
    print(f"[{MODEL}] FAILED: {e}", flush=True)
    result = {"model": MODEL, "error": str(e)}

results.append(result)
with open(OUT_PATH, "w") as f:
    json.dump(results, f, indent=2)
print(f"[{MODEL}] done, appended to {OUT_PATH}", flush=True)
