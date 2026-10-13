"""
certver.propose -- ask an LLM for candidate checks.

  python -m certver.propose --task sql --round 0 --n 25
  python -m certver.propose --task sql --round 1 --n 25 --feedback out/admit_sql_round0.json

Writes out/candidates/{task}_round{r}.jsonl, one candidate per line:
  {"id", "task", "round", "name", "rationale", "source"}
Candidates are refused here only if they fail the sandbox's static checks;
soundness is decided later, by admission on split A.

The proposer sees training examples WITH gold (the proposal split). That is
allowed: admission and certification use disjoint splits, so what the
proposer saw cannot inflate either.
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, sys

from soundver import generate as g
from .data import load_split
from .pool import complete
from .sandbox import validate_source, UnsafeCheck

PROPOSER = "openai/gpt-4o-2024-11-20"

TASK_SPECS = {
    "sql": {
        "what": ("Text-to-SQL on Spider (SQLite). A model reads a database schema "
                 "and an English question and writes one SQLite query."),
        "label": ("An output is CORRECT iff extract_sql(output) returns the same "
                  "result set as the gold query on several perturbed copies of the "
                  "database (test-suite accuracy). Formatting, aliases, keyword case, "
                  "join order, equivalent formulations, code fences or prose around "
                  "the query are all allowed in a correct output, as long as "
                  "extract_sql recovers a query with the right results. Correct "
                  "queries routinely use DIFFERENT CONSTRUCTS for the same question: "
                  "ORDER BY ... LIMIT 1 instead of MAX/MIN, a subquery or IN instead of "
                  "a JOIN, NOT IN or EXCEPT or LEFT JOIN ... IS NULL for negation, no "
                  "DISTINCT where duplicates cannot occur, no aliases, correlated "
                  "subqueries that reference outer aliases, and question words "
                  "('how many', 'average', 'sorted') that a correct query satisfies "
                  "without the keyword you might expect. Rules of the form 'question "
                  "word X implies SQL keyword Y' are almost always UNSOUND. Prefer "
                  "checks grounded in the database itself via execute(), e.g. on the "
                  "result shape, or in values the question quotes literally."),
        "ctx": ("ctx['question'] (str), ctx['schema'] ({table: [columns]}, lower-case), "
                "ctx['db_id'], ctx['db_path']"),
        "helpers": ("extract_sql(output) -> str (the query, as the label sees it); "
                    "execute(sql) -> list of up to 200 rows from the real database "
                    "(read-only, raises on error, 2 s limit). Imports allowed: re, json, "
                    "math, string, collections, itertools, unicodedata, functools, "
                    "sqlglot, difflib."),
        "existing": "the query parses; every table/column it names exists in the schema; it executes.",
    },
    "ie": {
        "what": ("Named-entity extraction on CoNLL2003 as slot filling. A model "
                 "reads a sentence and returns a JSON object with four list fields: "
                 "person, location, organization, else (other named entities)."),
        "label": ("An output is CORRECT iff parse_json(output) gives an object whose "
                  "four fields, each lower-cased, stripped and sorted, equal the gold "
                  "lists. Missing fields count as empty lists. Code fences around the "
                  "JSON are allowed. Entity strings are exact substrings of the text "
                  "in the gold data, but the label compares lower-cased values."),
        "ctx": "ctx['text'] (str, tokens separated by spaces)",
        "helpers": ("parse_json(output) -> dict or None (the parse the label uses). "
                    "Imports allowed: re, json, math, string, collections, itertools, "
                    "unicodedata, functools, difflib."),
        "existing": ("it parses as JSON; all four fields are present; every field is a "
                     "list; no two extracted entities overlap in the text."),
    },
    "fewnerd": {
        "what": ("Named-entity extraction on Few-NERD (Wikipedia sentences) as slot filling. "
                 "A model reads a sentence and returns a JSON object with eight list fields: "
                 "art, building, event, location, organization, other, person, product."),
        "label": ("An output is CORRECT iff parse_json(output) gives an object whose eight "
                  "fields, each lower-cased, stripped and sorted, equal the gold lists. Missing "
                  "fields count as empty lists. Code fences around the JSON are allowed. Gold "
                  "entities are token spans of the text (tokens separated by spaces)."),
        "ctx": "ctx['text'] (str, tokens separated by spaces)",
        "helpers": ("parse_json(output) -> dict or None (the parse the label uses). "
                    "Imports allowed: re, json, math, string, collections, itertools, "
                    "unicodedata, functools, difflib."),
        "existing": ("it parses as JSON; all eight fields are present; every field is a list; "
                     "no two extracted entities overlap in the text."),
    },
    "fc": {
        "what": ("Function calling (Glaive function-calling v2). A model sees JSON schemas of "
                 "available functions and a user request, and must output one call as JSON "
                 "{\"name\": ..., \"arguments\": {...}}."),
        "label": ("An output is CORRECT iff parse_call(output) has the gold function name and "
                  "argument dict equal to gold after normalisation (keys and string values "
                  "lower-cased and stripped, numbers compared as floats; a number written as a "
                  "string is NOT equal to the number, since a typed API rejects it). NOTE: "
                  "round-0 fc candidates were proposed under an earlier, lenient wording. Code fences are allowed; 'arguments' may be a JSON string."),
        "ctx": ("ctx['request'] (str, the user request), ctx['functions'] (list of function "
                "schemas: name, description, parameters with properties/types/required/enum)"),
        "helpers": ("parse_call(output) -> dict or None (the parse the label uses). "
                    "Imports allowed: re, json, math, string, collections, itertools, "
                    "unicodedata, functools, difflib."),
        "existing": ("it parses; it has a string name and a dict of arguments; the name is one "
                     "of the functions; required parameters are present; argument types match "
                     "the schema; no argument outside the schema."),
    },
    "math": {
        "what": ("Grade-school math word problems (GSM8K). A model writes step-by-step "
                 "reasoning in free text and ends with a line '#### <number>'."),
        "label": ("An output is CORRECT iff final_answer(output) equals the gold number "
                  "(commas and '$' ignored, compared as floats). final_answer reads the "
                  "last '#### x' line, or, if there is none, the last number in the text. "
                  "The label looks ONLY at the final answer: a correct output may contain "
                  "arithmetic written in many styles (a*b=c, 'a times b is c', <<a*b=c>>), "
                  "units, currency, percentages, intermediate rounding, restated "
                  "numbers from the problem, and even a harmless slip that it later fixes."),
        "ctx": "ctx['question'] (str, the problem text)",
        "helpers": ("final_answer(output) -> str or None (the answer the label reads). "
                    "Imports allowed: re, json, math, string, collections, itertools, "
                    "unicodedata, functools, difflib."),
        "existing": ("there is a '#### ' line; the final answer parses as a number. "
                     "Note that the output contains the full reasoning, not only the "
                     "answer: checks may test the internal consistency of that reasoning "
                     "as well as properties of the final answer."),
    },
    "morph": {
        "what": ("English morphological segmentation (SIGMORPHON 2022, word level). "
                 "A model splits a word into morphemes joined by '+'. Gold "
                 "segmentations are CANONICAL, not surface: e.g. 'subsidised' -> "
                 "subside+y+ise+ed, 'bummiest' -> bum+y+est, so morphemes need not "
                 "concatenate back to the word."),
        "label": ("An output is CORRECT iff segments(output) equals the gold morpheme "
                  "list exactly (case-sensitive, order-sensitive)."),
        "ctx": "ctx['surface'] (str, the word)",
        "helpers": ("segments(output) -> list[str] (the parse the label uses). "
                    "Imports allowed: re, json, math, string, collections, itertools, "
                    "unicodedata, functools, difflib."),
        "existing": ("no empty segment; segments concatenate to the word (this one is "
                     "UNSOUND: canonical gold segmentations often do not concatenate)."),
    },
}


def _examples(task: str, k: int) -> str:
    items = load_split(task, "proposal")[:k]
    lines = []
    for it in items:
        if task == "sql":
            schema = "; ".join(f"{t}({', '.join(sorted(c))})" for t, c in it["schema"].items())
            lines.append(f"Schema: {schema}\nQuestion: {it['question']}\nGold SQL: {it['gold_sql']}")
        elif task == "ie":
            lines.append(f"Text: {it['text']}\nGold: {json.dumps(it['gold'])}")
        elif task == "math":
            lines.append(f"Problem: {it['question']}\nGold solution: {it['gold_solution']}")
        elif task == "fewnerd":
            lines.append(f"Text: {it['text']}\nGold: {json.dumps(it['gold'])}")
        elif task == "fc":
            lines.append(f"Functions: {json.dumps(it['functions'])[:1500]}\nUser: {it['request']}\n"
                         f"Gold call: {json.dumps(it['gold_call'])}")
        else:
            lines.append(f"Word: {it['surface']}\nGold: {'+'.join(it['gold_segments'])}")
    return "\n\n".join(lines)


def _normalise(task: str, raw: str) -> str:
    return " ".join(raw.lower().split())


def _contrast(task: str, k_wrong: int = 10, k_right: int = 8) -> str:
    """Model outputs from the proposal-split pool: wrong ones beside gold, and
    correct ones written differently from gold. Empty if no pool exists."""
    pool = os.path.join("data", "pools", f"pool_{task}_proposal_seed0.jsonl")
    if not os.path.exists(pool):
        return ""
    items = {it["instance_id"]: it for it in load_split(task, "proposal")}
    wrong, right, seen_w, seen_r = [], [], set(), set()
    with open(pool) as f:
        for line in f:
            r = json.loads(line)
            it = items[r["instance_id"]]
            gold = (it.get("gold_sql") if task == "sql" else
                    json.dumps(it["gold"]) if task in ("ie", "fewnerd") else
                    json.dumps(it["gold_call"]) if task == "fc" else
                    it["gold_solution"] if task == "math" else "+".join(it["gold_segments"]))
            src = (f"Question: {it['question']}" if task in ("sql", "math") else
                   f"Text: {it['text']}" if task in ("ie", "fewnerd") else
                   f"User: {it['request']}" if task == "fc" else f"Word: {it['surface']}")
            out = r["raw"].strip()[:400]
            if not r["correct"] and r["instance_id"] not in seen_w and len(wrong) < k_wrong:
                seen_w.add(r["instance_id"])
                wrong.append(f"{src}\nGold: {gold}\nINCORRECT model output: {out}")
            elif (r["correct"] and r["instance_id"] not in seen_r and len(right) < k_right
                  and _normalise(task, out) != _normalise(task, gold)):
                seen_r.add(r["instance_id"])
                right.append(f"{src}\nGold: {gold}\nCORRECT model output (differs from gold): {out}")
    return ("\n\nINCORRECT MODEL OUTPUTS (what checks should catch):\n\n" + "\n\n".join(wrong)
            + "\n\nCORRECT MODEL OUTPUTS WRITTEN DIFFERENTLY FROM GOLD (what checks must "
            "accept):\n\n" + "\n\n".join(right))


def build_prompt(task: str, n: int, feedback: list | None, hint: str = "") -> str:
    s = TASK_SPECS[task]
    focus = ("\n\nFOCUS FOR THIS ROUND. " + hint) if hint else ""
    fb = ""
    if feedback:
        fb = ("\n\nFEEDBACK FROM THE PREVIOUS ROUND. These checks rejected outputs that "
              "were actually CORRECT, so they are unsound and were not admitted. "
              "Study why; either propose a repaired version that cannot make that "
              "mistake, or drop the idea.\n\n" + json.dumps(feedback, indent=1)[:12000])
    return f"""You are designing VERIFIER CHECKS for a structured NLP task.

TASK. {s['what']}

HOW CORRECTNESS IS DECIDED. {s['label']}

WHAT A CHECK IS. A Python function

    def check(output: str, ctx: dict) -> bool

that returns False to REJECT a model output. It never sees the gold answer.
ctx contains: {s['ctx']}.
Available helpers: {s['helpers']}
An exception, timeout or non-bool return counts as a rejection, so wrap your
logic in try/except and return True whenever the check cannot decide (the
output is unparseable for your purpose, a helper raises, the pattern you look
for is absent). Return False only when the output definitely violates a
constraint every correct answer satisfies.

THE ONE HARD REQUIREMENT: SOUNDNESS. A check must return True for EVERY
correct output, including correct outputs written differently from the gold
examples below. A check that rejects even a small fraction of correct
outputs will be discarded. When in doubt, accept.

THE GOAL: among checks that are sound, catch as many INCORRECT outputs as
possible. We already have these checks, so do not repeat them: {s['existing']}
Look for constraints that the question/text/word itself imposes on any
correct answer, beyond well-formedness.

EXAMPLES (training data, with gold):

{(_examples(task, 6) if task in ("math", "fc") else _examples(task, 12))}{_contrast(task)}{fb}{focus}

Propose {n} diverse candidate checks. Use exactly this format for each, and
nothing else between checks:

### CHECK <snake_case_name>
RATIONALE: <one or two sentences: why every correct output passes, and which
wrong outputs it catches>
```python
def check(output, ctx):
    ...
```"""


_BLOCK = re.compile(r"###\s*CHECK[\s_:-]+(\S+)\s*\n(.*?)```(?:python)?\s*\n(.*?)```", re.DOTALL)


def _parse_candidates(text: str) -> list:
    out = []
    for name, middle, src in _BLOCK.findall(text):
        m = re.search(r"RATIONALE:\s*(.*)", middle, re.DOTALL)
        out.append({"name": name.strip(), "rationale": (m.group(1) if m else middle).strip(),
                    "source": src.strip() + "\n"})
    if not out:
        raise ValueError("no ### CHECK blocks found")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", required=True, choices=sorted(TASK_SPECS))
    ap.add_argument("--round", type=int, default=0)
    ap.add_argument("--n", type=int, default=25)
    ap.add_argument("--calls", type=int, default=2, help="independent proposer calls, merged")
    ap.add_argument("--feedback", default=None, help="admission report from the previous round")
    ap.add_argument("--out-dir", default="out/candidates")
    ap.add_argument("--proposer", default=PROPOSER)
    ap.add_argument("--tag", default="", help="suffix for the output file, e.g. the proposer")
    ap.add_argument("--reasoning-effort", default=None, choices=["low", "medium", "high"],
                    help="for reasoning models; max-token caps were ignored in testing")
    ap.add_argument("--max-tokens", type=int, default=24000)
    ap.add_argument("--hint", default="", help="extra focus sentence (a GUIDED round; report as such)")
    a = ap.parse_args(argv)

    feedback = None
    if a.feedback:
        with open(a.feedback) as f:
            feedback = json.load(f).get("feedback")
    prompt = build_prompt(a.task, a.n, feedback, a.hint)
    os.makedirs(a.out_dir, exist_ok=True)
    out_path = os.path.join(a.out_dir, f"{a.task}_round{a.round}{a.tag}.jsonl")
    kept, refused, cost = [], [], 0.0
    seen = set()
    for call in range(a.calls):
        r = complete(a.proposer, prompt, temperature=0.7, max_tokens=a.max_tokens,
                     reasoning={"effort": a.reasoning_effort} if a.reasoning_effort else None)
        if r.get("finish_reason") == "length":
            print(f"call {call}: hit max_tokens; output may be truncated", file=sys.stderr)
        cost += r["cost"]
        with open(out_path.replace(".jsonl", f".raw{call}.txt"), "w") as rf:
            rf.write(r["text"])
        try:
            cands = _parse_candidates(r["text"])
        except Exception as e:  # noqa: BLE001
            print(f"call {call}: could not parse proposer output ({e})", file=sys.stderr)
            continue
        for c in cands:
            src = c.get("source", "")
            h = hashlib.sha1(src.encode()).hexdigest()[:10]
            if h in seen:
                continue
            seen.add(h)
            try:
                validate_source(src)
            except UnsafeCheck as e:
                refused.append({"name": c.get("name"), "reason": str(e)})
                continue
            kept.append({"id": f"{a.task}-r{a.round}{a.tag}-{h}", "task": a.task, "round": a.round,
                         "name": c.get("name"), "rationale": c.get("rationale"), "source": src})
    with open(out_path, "w") as f:
        for c in kept:
            f.write(json.dumps(c) + "\n")
    print(f"{len(kept)} candidates written to {out_path}; {len(refused)} refused "
          f"by static checks; proposer cost ${cost:.4f}")
    for r in refused:
        print(f"  refused {r['name']}: {r['reason']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
