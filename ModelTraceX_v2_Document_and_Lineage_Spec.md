# ModelTraceX v2 — Document & Lineage Workbook Specification

**Document type:** Output specification (companion to *ModelTraceX v2 — Requirements Document*).
**Intended reader:** An AI assistant (Claude) producing the design and, later, the implementation.
**Covers:** FR-4 (standard model document), FR-5 (enhanced lineage), FR-6 (DQ rule inference), and the canonical structured state that all outputs project from.

This document is the **contract** for what the model documentation file and the lineage workbook must contain. The requirements document defines *why*; this defines *exactly what*.

---

## Part A — Standard model documentation structure

Each analyzed model produces one documentation file (default DOCX) following the fixed section order below. The structure is aligned to model-risk / governance documentation conventions so the output is suitable for a validator or CRO/CCO-level reader. Every section is a **projection of the structured state** (Part D); the generator never free-writes facts that are not in the state.

**Source legend** for each field:
`E` = LLM-extracted from code · `H` = heuristic/parser-derived · `I` = LLM-inferred (lower confidence) · `U` = user-provided/overridden.

| # | Section | Contents | Typical source |
|---|---|---|---|
| 1 | **Cover / metadata** | Model label, language, file name(s), analysis timestamp, run ID, tool version, provider/model used | H / system |
| 2 | **Executive summary** | 3–6 sentence plain-language description of what the model does and produces | E/I |
| 3 | **Purpose and scope** | Business/analytical purpose; what is and is not covered by this code | E/I |
| 4 | **Data inputs** | Each input table: name, source system (if identifiable), grain, and attribute list with inferred types | E/H |
| 5 | **Assumptions and dependencies** | Hard-coded values, external lookups, libname/library references, environment assumptions | E/H/I |
| 6 | **Methodology / processing logic** | Ordered narrative of the transformation steps (the "what happens") | E |
| 7 | **Calculation logic** | Key derived fields and the expressions/formulas that produce them | E |
| 8 | **Data outputs** | Each output table: name, grain, attribute list, and which inputs each output draws from | E/H |
| 9 | **Data lineage summary** | Narrative + reference to the lineage workbook; the end-to-end flow for this model | E/H |
| 10 | **Data quality considerations** | Summary of inferred DQ rules (Part C), grouped by DQ dimension, with severity | I/H |
| 11 | **Limitations and risks** | Gaps, ambiguous logic, items the tool could not resolve, low-confidence extractions | I/system |
| 12 | **Provenance and confidence** | Per-section note of LLM-vs-heuristic origin and confidence; list of user overrides applied | system |
| 13 | **Appendix: source listing** | The analyzed code (optionally redacted per security mode) | U/system |

**Formatting requirements**

- Consistent heading hierarchy, a table of contents, page numbers, and a document title block.
- Tables for inputs, outputs, and DQ rules (not prose lists).
- A short **confidence/provenance callout** wherever a section relies on low-confidence inference.
- Sections with no content render an explicit "Not identified from code" rather than being omitted, so the structure stays repeatable across models.

A **project-level summary document** (across all models) is also produced, containing: model inventory, the end-to-end cross-model lineage narrative, an aggregated DQ rule register, and a list of source systems and outputs.

---

## Part B — Lineage workbook specification

Default format **XLSX**, multi-sheet. Sheet order and columns below are the contract. Column `Source` uses the same legend as Part A (`E/H/I/U`). A legacy flat 5-column CSV may be offered as a compatibility export but does not replace this workbook.

### Sheet 1 — `Run Summary`
Run-level metadata and counts.

| Column | Type | Description |
|---|---|---|
| Run ID | string | Unique run identifier |
| Timestamp | datetime | When the run executed |
| Tool version | string | ModelTraceX version |
| LLM provider / model | string | Provider and model used |
| Languages detected | string | Distinct languages across models |
| # Models | int | Count of models analyzed |
| # Input tables / # Output tables | int | Distinct counts |
| # Table-level edges / # Column-level edges | int | Counts |
| # DQ rules | int | Count of inferred rules |
| Tokens / est. cost | number | Telemetry (NFR-6) |

### Sheet 2 — `Model Inventory`
One row per model.

| Column | Type | Description |
|---|---|---|
| Model ID | string | Stable ID |
| Model label | string | Display name |
| Language | enum | SAS / Python / R / VBA |
| Source file(s) | string | File name(s) |
| Purpose | text | One-line purpose |
| # Inputs / # Outputs | int | Counts |
| Confidence | enum | High / Medium / Low |
| Status | enum | Analyzed / Partial / Failed |

### Sheet 3 — `Tables`
One row per distinct table/dataset (input, output, or intermediate).

| Column | Type | Description |
|---|---|---|
| Table ID | string | Stable ID |
| Table name | string | As referenced in code |
| Role | enum | Source / Intermediate / Output |
| Source system | string | If identifiable (libname, schema, connection) |
| Produced by model(s) | string | Model IDs that write it |
| Consumed by model(s) | string | Model IDs that read it |
| Grain | text | Row grain if inferable |
| Source | enum | E/H/I/U |

### Sheet 4 — `Columns`
One row per (table, column) pair.

| Column | Type | Description |
|---|---|---|
| Table ID | string | FK → Tables |
| Column name | string | Attribute name |
| Inferred type | string | e.g. numeric/char/date |
| Role | enum | Key / Measure / Attribute / Derived |
| Used in | string | filter / join / aggregate / calc / output (multi) |
| Source | enum | E/H/I/U |

### Sheet 5 — `Table Lineage`
One row per table-level edge.

| Column | Type | Description |
|---|---|---|
| Edge ID | string | Stable ID |
| Source table ID | string | FK → Tables |
| Target table ID | string | FK → Tables |
| Model ID | string | Model that creates the edge |
| Transformation type | enum | filter / join / aggregate / derive / rename / cast / passthrough / union |
| Notes | text | Short description |
| Source | enum | E/H/I/U |
| Confidence | enum | High / Medium / Low |

### Sheet 6 — `Column Lineage`
One row per column-level edge — the detailed lineage.

| Column | Type | Description |
|---|---|---|
| Edge ID | string | Stable ID |
| Source table.column | string | Origin element |
| Target table.column | string | Destination element |
| Model ID | string | Model that creates the edge |
| Transformation type | enum | as Sheet 5 |
| Transformation expression | text | The extracted expression/formula, where available |
| Join key(s) | string | For join edges |
| Source | enum | E/H/I/U |
| Confidence | enum | High / Medium / Low |

### Sheet 7 — `Data Quality Rules`
One row per inferred rule (see Part C).

| Column | Type | Description |
|---|---|---|
| Rule ID | string | Stable ID |
| Table.column | string | Element the rule applies to |
| DQ dimension | enum | Completeness / Validity / Uniqueness / Consistency / Accuracy / Timeliness |
| Rule | text | Human-readable rule statement |
| Rationale / usage | text | How the element is used that motivates the rule |
| Code evidence | text | The code snippet/pattern that triggered it |
| Suggested severity | enum | High / Medium / Low |
| Source | enum | E/H/I |
| Status | enum | Proposed / Accepted / Rejected (NFR-5) |

### Sheet 8 — `Source Systems`
One row per identified source system / library / schema, with the tables it provides.

### Sheet 9 — `Issues & Confidence Log`
Low-confidence extractions, ambiguities, partial-model warnings, and merge notes — for reviewer attention.

> The interactive web graph (FR-7.1) and the OpenLineage export (NFR-8) read from the same underlying graph as Sheets 3–6.

---

## Part C — Data quality rule inference

DQ rules are inferred from **how each element is used in the code**, then mapped to a DQ dimension and severity. The engine combines deterministic heuristics (high confidence) with LLM proposals (review-required). Every rule carries its triggering **code evidence**.

### DQ dimensions
Completeness, Validity, Uniqueness, Consistency, Accuracy, Timeliness.

### Inference rules (starting set — design may extend)

| Observed usage in code | Inferred DQ rule | Dimension | Default severity |
|---|---|---|---|
| Element used as a **denominator / divisor** | Must be non-null and non-zero | Validity | High |
| Element used as a **join / merge key** | Uniqueness on key; referential integrity to joined table | Uniqueness / Consistency | High |
| Element passed to a **date function** or parsed as date | Valid date; within plausible range | Validity | Medium |
| Element used in a **range/threshold filter** (`> < BETWEEN`) | Value within expected domain/range | Validity | Medium |
| Element **aggregated** (sum/avg/count by group) | Completeness on the aggregation grain (no missing rows) | Completeness | Medium |
| Element **type-cast or parsed** (to numeric/date) | Format/type conformance | Accuracy | Medium |
| Element used in **equality filter against a fixed set** | Domain/code-value validity (allowed values) | Validity | Medium |
| Element is a **primary output measure** | Non-null; not all-zero/all-null | Completeness | Medium |
| Element drives a **time-window / as-of filter** | Timeliness / freshness expectation | Timeliness | Low |
| Element joined across systems with same business meaning | Cross-system consistency | Consistency | Medium |

### Rule object (what each inferred rule must capture)
`rule_id`, `element` (table.column), `dimension`, `rule_statement`, `rationale`, `code_evidence`, `severity`, `source` (heuristic/LLM), `confidence`, `status` (proposed/accepted/rejected).

Severities are **defaults**; the LLM may adjust with justification, and a reviewer may override (NFR-5). Rules are **candidates** — the tool proposes, the human disposes.

---

## Part D — Canonical structured state (source of truth)

The model document, the lineage workbook, the diagrams, and the OpenLineage export are all **projections of this object**. The design phase should formalize it (recommended: Pydantic), but the entities and key fields below are the intended shape.

```jsonc
{
  "run": {
    "run_id": "string",
    "timestamp": "datetime",
    "tool_version": "string",
    "llm_provider": "string",
    "llm_model": "string",
    "tokens": 0,
    "est_cost": 0.0,
    "security_mode": "cloud | local"
  },
  "models": [
    {
      "model_id": "string",
      "label": "string",
      "language": "SAS | Python | R | VBA",
      "source_files": ["string"],
      "purpose": "string",
      "executive_summary": "string",
      "assumptions": ["string"],
      "methodology_steps": ["string"],
      "calculations": [
        { "target": "table.column", "expression": "string", "source": "E|H|I|U", "confidence": "High|Medium|Low" }
      ],
      "limitations": ["string"],
      "status": "Analyzed | Partial | Failed",
      "confidence": "High | Medium | Low"
    }
  ],
  "tables": [
    {
      "table_id": "string",
      "name": "string",
      "role": "Source | Intermediate | Output",
      "source_system": "string|null",
      "grain": "string|null",
      "produced_by": ["model_id"],
      "consumed_by": ["model_id"],
      "columns": [
        {
          "name": "string",
          "inferred_type": "string|null",
          "role": "Key | Measure | Attribute | Derived",
          "used_in": ["filter|join|aggregate|calc|output"],
          "source": "E|H|I|U"
        }
      ],
      "source": "E|H|I|U"
    }
  ],
  "table_edges": [
    {
      "edge_id": "string",
      "source_table_id": "string",
      "target_table_id": "string",
      "model_id": "string",
      "transformation_type": "filter|join|aggregate|derive|rename|cast|passthrough|union",
      "notes": "string",
      "source": "E|H|I|U",
      "confidence": "High|Medium|Low"
    }
  ],
  "column_edges": [
    {
      "edge_id": "string",
      "source_element": "table.column",
      "target_element": "table.column",
      "model_id": "string",
      "transformation_type": "filter|join|aggregate|derive|rename|cast|passthrough|union",
      "expression": "string|null",
      "join_keys": ["string"],
      "source": "E|H|I|U",
      "confidence": "High|Medium|Low"
    }
  ],
  "dq_rules": [
    {
      "rule_id": "string",
      "element": "table.column",
      "dimension": "Completeness|Validity|Uniqueness|Consistency|Accuracy|Timeliness",
      "rule_statement": "string",
      "rationale": "string",
      "code_evidence": "string",
      "severity": "High|Medium|Low",
      "source": "E|H|I",
      "confidence": "High|Medium|Low",
      "status": "Proposed|Accepted|Rejected"
    }
  ],
  "source_systems": [
    { "name": "string", "tables": ["table_id"] }
  ],
  "issues": [
    { "model_id": "string|null", "severity": "string", "message": "string" }
  ],
  "overrides": [
    { "target": "string", "field": "string", "old": "any", "new": "any", "by": "user", "timestamp": "datetime" }
  ]
}
```

**Design notes**

- IDs are stable so re-runs and diffs (NFR-4) can track elements across runs.
- `source` and `confidence` appear on every extracted entity to satisfy provenance/human-in-the-loop (NFR-5).
- The whole-project cross-model graph (FR-5.3) is `tables` + `table_edges` + `column_edges` traversed end to end; per-model views are filters on `model_id`.
- `overrides` is the persisted record of human accept/reject/edit actions, and is what the chat loop (FR-9) writes when the user changes parameters.
