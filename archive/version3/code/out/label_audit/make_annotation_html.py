#!/usr/bin/env python3
"""
make_annotation_html.py -- convert annotation_sheet_{1,2}.csv into standalone
HTML annotation forms so a human annotator can score items in a browser
instead of editing CSV cells directly, then export the result back to the
exact CSV format b8_v1_collect_annotations.py expects.

Usage:
    python3 make_annotation_html.py
    -> writes annotate_sheet_1.html and annotate_sheet_2.html in this dir.

Each HTML file is self-contained (data embedded inline, no server needed).
Progress is saved to the browser's localStorage as you go, and the
"Download CSV" button produces a file with the same columns/order as the
original sheet, ready to overwrite annotation_sheet_{1,2}.csv.
"""
import csv
import html
import json
import os

AUDIT_DIR = os.path.dirname(os.path.abspath(__file__))

TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Annotation -- __SHEET_NAME__</title>
<style>
  :root { color-scheme: light dark; }
  body { font-family: -apple-system, Segoe UI, Helvetica, Arial, sans-serif; max-width: 900px; margin: 0 auto; padding: 16px; }
  h1 { font-size: 1.1rem; }
  #progress { position: sticky; top: 0; background: Canvas; padding: 8px 0; border-bottom: 1px solid #8884; z-index: 10; }
  .item { border: 1px solid #8884; border-radius: 8px; padding: 12px; margin: 12px 0; }
  .item.done { border-left: 4px solid #2a7; }
  .meta { font-size: 0.8rem; opacity: 0.7; margin-bottom: 6px; }
  .block-label { font-weight: 600; font-size: 0.8rem; text-transform: uppercase; opacity: 0.6; margin-top: 8px; }
  pre, .text { white-space: pre-wrap; word-break: break-word; background: #80808014; padding: 8px; border-radius: 6px; font-size: 0.9rem; margin: 4px 0; }
  .labels { display: flex; gap: 14px; margin: 8px 0; flex-wrap: wrap; }
  .labels label { cursor: pointer; }
  .notes { width: 100%; box-sizing: border-box; font-family: inherit; font-size: 0.85rem; padding: 4px; }
  #toolbar { position: sticky; top: 38px; background: Canvas; padding: 8px 0; z-index: 9; display: flex; gap: 8px; align-items: center; }
  button { padding: 6px 12px; cursor: pointer; }
  #filter { margin-left: auto; }
  .hidden { display: none; }
</style>
</head>
<body>
<h1>Annotation sheet: __SHEET_NAME__</h1>
<div id="progress">Loading...</div>
<div id="toolbar">
  <button id="downloadBtn">Download CSV</button>
  <button id="clearBtn">Clear saved progress</button>
  <label id="filter"><input type="checkbox" id="onlyUnlabeled"> show only unlabeled</label>
</div>
<div id="items"></div>

<script>
const SHEET_NAME = __SHEET_NAME_JSON__;
const STORAGE_KEY = "soundver_annotations_" + SHEET_NAME;
const ROWS = __ROWS_JSON__;
const FIELDNAMES = __FIELDNAMES_JSON__;

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch (e) { return {}; }
}
function saveState(state) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); } catch (e) {}
}

let state = loadState();

function updateProgress() {
  const total = ROWS.length;
  const done = ROWS.filter(r => state[r.row_id] && state[r.row_id].label).length;
  document.getElementById("progress").textContent = `${done} / ${total} labeled`;
}

function renderItems() {
  const container = document.getElementById("items");
  container.innerHTML = "";
  const onlyUnlabeled = document.getElementById("onlyUnlabeled").checked;
  for (const row of ROWS) {
    const cur = state[row.row_id] || {label: "", notes: ""};
    if (onlyUnlabeled && cur.label) continue;
    const div = document.createElement("div");
    div.className = "item" + (cur.label ? " done" : "");
    div.innerHTML = `
      <div class="meta">row_id=${row.row_id} &middot; task=${esc(row.task)}</div>
      <div class="block-label">task_input</div>
      <div class="text">${esc(row.task_input)}</div>
      <div class="block-label">candidate_output</div>
      <div class="text">${esc(row.candidate_output)}</div>
      <div class="labels">
        ${["correct","incorrect","unsure"].map(opt => `
          <label>
            <input type="radio" name="label_${row.row_id}" value="${opt}" ${cur.label === opt ? "checked" : ""}>
            ${opt}
          </label>`).join("")}
      </div>
      <input class="notes" type="text" placeholder="notes (optional)" value="${esc(cur.notes || "")}">
    `;
    const radios = div.querySelectorAll(`input[name="label_${row.row_id}"]`);
    radios.forEach(r => r.addEventListener("change", () => {
      state[row.row_id] = state[row.row_id] || {};
      state[row.row_id].label = r.value;
      saveState(state);
      updateProgress();
      div.classList.add("done");
    }));
    const notesInput = div.querySelector(".notes");
    notesInput.addEventListener("input", () => {
      state[row.row_id] = state[row.row_id] || {};
      state[row.row_id].notes = notesInput.value;
      saveState(state);
    });
    container.appendChild(div);
  }
}

function esc(s) {
  const d = document.createElement("div");
  d.textContent = s == null ? "" : s;
  return d.innerHTML;
}

function toCsvField(v) {
  v = v == null ? "" : String(v);
  if (/[",\\n]/.test(v)) {
    return '"' + v.replace(/"/g, '""') + '"';
  }
  return v;
}

document.getElementById("downloadBtn").addEventListener("click", () => {
  const lines = [FIELDNAMES.map(toCsvField).join(",")];
  for (const row of ROWS) {
    const cur = state[row.row_id] || {label: "", notes: ""};
    const record = {
      row_id: row.row_id,
      task: row.task,
      task_input: row.task_input,
      candidate_output: row.candidate_output,
      "human_label(correct|incorrect|unsure)": cur.label || "",
      notes: cur.notes || "",
    };
    lines.push(FIELDNAMES.map(f => toCsvField(record[f])).join(","));
  }
  const blob = new Blob([lines.join("\\r\\n")], {type: "text/csv"});
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = SHEET_NAME + ".csv";
  a.click();
  URL.revokeObjectURL(url);
});

document.getElementById("clearBtn").addEventListener("click", () => {
  if (confirm("Clear all saved progress for this sheet in this browser?")) {
    state = {};
    saveState(state);
    renderItems();
    updateProgress();
  }
});

document.getElementById("onlyUnlabeled").addEventListener("change", renderItems);

renderItems();
updateProgress();
</script>
</body>
</html>
"""


def build(sheet_path, out_path, sheet_name):
    with open(sheet_path, newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = []
        for r in reader:
            rows.append({
                "row_id": int(r["row_id"]),
                "task": r["task"],
                "task_input": r["task_input"],
                "candidate_output": r["candidate_output"],
            })

    out = TEMPLATE
    out = out.replace("__SHEET_NAME__", html.escape(sheet_name))
    out = out.replace("__SHEET_NAME_JSON__", json.dumps(sheet_name))
    out = out.replace("__ROWS_JSON__", json.dumps(rows))
    out = out.replace("__FIELDNAMES_JSON__", json.dumps(fieldnames))

    with open(out_path, "w") as f:
        f.write(out)
    print(f"wrote {out_path} ({len(rows)} items)")


def main():
    for n in (1, 2):
        sheet = os.path.join(AUDIT_DIR, f"annotation_sheet_{n}.csv")
        out = os.path.join(AUDIT_DIR, f"annotate_sheet_{n}.html")
        build(sheet, out, f"annotation_sheet_{n}")


if __name__ == "__main__":
    main()
