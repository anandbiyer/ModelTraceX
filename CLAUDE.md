# CLAUDE.md — ModelTraceX.py

Documentation for `ModelTraceX.py`. This file is a single-module application that reviews **SAS modeling code** with an LLM and produces a human-readable review, a data-lineage CSV, and a clustered lineage diagram.

---

## 1. What the code does

`ModelTraceX.py` takes one or more blocks of **SAS code** (each representing a "model") and, for each one, asks an OpenAI model to extract:

- **Purpose** of the code
- **Input tables** (with column/attribute lists)
- **Data transformation logic**
- **Calculation logic**
- **Output tables** (with attributes)
- **Lineage rows** (how source data elements flow to output data elements)

It then combines the per-model results into a project-wide **data lineage** and emits three artifacts:

| Artifact | File | Purpose |
|----------|------|---------|
| Plain-text review | `output.txt` | Readable per-model summary (inputs, purpose, transforms, calc logic, outputs) |
| Lineage table | `lineage_table.csv` | Source code/element → output code/element mapping |
| Lineage diagram | `lineage_clustered.png` | Graphviz swim-lane diagram: **Sources → Models → Outputs** |

The tool runs either as a **Gradio web UI** (default) or a **terminal CLI** (`--cli`).

---

## 2. Underlying architecture

The script is organized as a linear pipeline with clearly separated stages:

```
SAS code (UI textbox or CLI paste)
        │
        ▼
┌─────────────────────────────────────────────┐
│ llm_analyze_single_model(label, sas_code)    │   ← per model
│  • OpenAI chat call (JSON mode)               │
│  • heuristic regex scan of table names        │
│  • normalize + merge LLM + regex results      │
│  → ModelAnalysis dataclass                    │
└─────────────────────────────────────────────┘
        │  (list of ModelAnalysis)
        ▼
┌─────────────────────────────────────────────┐
│ analyze_models(...)  — orchestrator           │
│  ├─ write_model_review_txt → output.txt       │
│  ├─ llm_synthesize_lineage → cross-model rows │
│  ├─ write_lineage_csv      → lineage_table.csv│
│  └─ draw_lineage_clustered → lineage_*.png    │
└─────────────────────────────────────────────┘
        │
        ▼
  output.txt, lineage_table.csv, lineage_clustered.png
```

### Key components

- **Data structures** (`@dataclass`)
  - `TableSpec` — a table name plus a list of attributes (columns).
  - `ModelAnalysis` — the full extracted result for one model: label, purpose, input/output tables, transforms, calc logic, lineage rows.

- **Normalizers** (`_normalize_tables`, `_to_tablespec_list`, `_normalize_lineage_rows`, `_norm_lines`)
  - Defensive coercion layer. The LLM may return tables as dicts, strings, comma-separated lists, single values, or `None`. These functions force everything into a clean, predictable shape so downstream code never crashes on malformed JSON. This is the most important robustness mechanism in the file.

- **SAS heuristics** (`heuristic_scan_tables` + four compiled regexes)
  - A non-LLM fallback/cross-check. Regexes detect SAS `SET`, `FROM` (inputs) and `DATA ...;`, `CREATE TABLE` (outputs). Results are **merged** with the LLM output (union of attributes by table name) so table names aren't missed if the LLM overlooks them.

- **LLM layer**
  - Two system prompts: `SYSTEM_PROMPT_REVIEWER` (per-model extraction) and `SYSTEM_PROMPT_LINEAGE` (cross-model lineage synthesis).
  - Both calls use `response_format={"type": "json_object"}` to **enforce JSON output**, then `json.loads` the response.

- **Writers**
  - `write_model_review_txt` — formats `output.txt`; carefully handles strings vs. lists so multi-line text isn't accidentally split character-by-character.
  - `write_lineage_csv` — fixed 5-column lineage CSV.
  - `draw_lineage_clustered` — builds a Graphviz `Digraph` with three colored clusters (swim-lanes), HTML-like table "cards" for nodes, and edges flowing left→right. Includes Windows-specific hardening (`_safe_id` for valid node IDs, `_esc` for HTML escaping, avoids `<HR/>` rows that break some Windows Graphviz builds).

- **Orchestration** (`analyze_models`)
  - Glue function: runs analysis on all models, then calls every writer. Returns the three output paths.

- **Interfaces**
  - `launch_ui()` — Gradio Blocks UI: a slider for 1–5 models, accordions with label + SAS code textboxes, an Analyze button, and file/image outputs.
  - CLI path (`__main__` with `--cli`) — prompts for model count, labels, and pasted SAS code (terminated by a `<<<END>>>` sentinel via `read_sas_block`).

---

## 3. Technology used

| Area | Technology | Role |
|------|-----------|------|
| Language | **Python 3** | `dataclasses`, `typing`, f-strings |
| LLM | **OpenAI API** (`openai` SDK) | `client.chat.completions.create` with JSON mode; model from `OPENAI_MODEL` env (default `gpt-4.1-mini`) |
| Config | **python-dotenv** | Loads `OPENAI_API_KEY` / `OPENAI_MODEL` from `.env` |
| Web UI | **Gradio** (`gr.Blocks`) | Interactive browser front-end |
| Diagrams | **Graphviz** (`graphviz.Digraph`) | Clustered swim-lane lineage rendering (requires Graphviz binary installed on the system) |
| Parsing | **`re` (regex)** | SAS table-name heuristics, line splitting |
| Output | **`csv`, `json`, `html`** stdlib | CSV writing, JSON parse, HTML-label escaping |
| CLI | **`argparse`** | `--cli` flag to switch UI ↔ terminal |

> **Declared but effectively unused:** `networkx` and `matplotlib` are imported at the top but the active diagram path uses Graphviz (`draw_lineage_clustered`). They appear to be leftovers from an earlier spring-layout implementation (see the note in `analyze_models`).

---

## 4. How to run

```bash
# Web UI (default)
python ModelTraceX.py

# Terminal mode
python ModelTraceX.py --cli
```

**Prerequisites:**
- `OPENAI_API_KEY` set in environment or `.env`
- Graphviz binaries installed and on `PATH` (the `graphviz` Python package is only a wrapper)
- `pip install` of: `openai`, `python-dotenv`, `gradio`, `networkx`, `matplotlib`, `graphviz`

---

## 5. Notes for future edits

- The **normalizer functions are the safety net** for unpredictable LLM JSON — keep them in sync if the prompt schema changes.
- LLM output and regex heuristics are **merged**, not exclusive; changing one affects completeness of tables.
- `draw_lineage_clustered` writes Graphviz body lines manually (`dot.body.append(...)`) for cluster styling — edit with care to keep valid DOT syntax.
- The UI is hard-capped at **5 models** (loop `range(1, 6)` and the `sum([...for i in range(5)])` input wiring); changing the limit requires updating both the slider max and these loops.
- Output filenames (`output.txt`, `lineage_table.csv`, `lineage_clustered.png`) are written to the working directory and overwritten on each run.
