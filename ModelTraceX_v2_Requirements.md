# ModelTraceX v2 — Requirements Document

**Document type:** Requirements specification (input to a design phase)
**Intended reader:** An AI assistant (Claude) tasked with producing a Software Design Document from these requirements.
**Status:** For design. Technology suggestions are *recommendations*; the design phase may propose alternatives with justification.

---

## 0. How to use this document

You (Claude) are being asked to turn this requirements document into a **Software Design Document (SDD)**. Treat the requirements below as authoritative intent. Where this document recommends a specific technology, you may either adopt it or propose a better-justified alternative — but every functional requirement (FR-*) and non-functional requirement (NFR-*) must be addressed in your design.

A companion specification — *ModelTraceX v2 — Document & Lineage Workbook Specification* — defines the exact structure of two key outputs (the model documentation file and the lineage workbook) and the canonical data model that underpins them. Read it alongside this document; it is the contract for FR-4, FR-5, and FR-6.

The expected contents of your SDD are listed in Section 12.

---

## 1. Background and current state

ModelTraceX is an existing single-module Python application (`ModelTraceX.py`) that reviews **SAS** modeling code using an LLM and produces three artifacts:

- a plain-text per-model review (`output.txt`),
- a 5-column data-lineage CSV (`lineage_table.csv`), and
- a Graphviz swim-lane lineage diagram (`lineage_clustered.png`).

It runs as a Gradio web UI or a terminal CLI. Internally it is a linear pipeline: per-model LLM extraction (JSON mode) cross-checked against SAS regex heuristics, defensive normalizer functions to coerce unpredictable LLM JSON, then writers for each artifact and an orchestrator that synthesizes cross-model lineage.

**Key limitations driving this rework:**

- SAS only.
- Limited input (paste/CLI only); hard cap of 5 models (`range(1,6)` and fixed UI wiring).
- Output is unstructured text plus a thin CSV and a static PNG.
- Monolithic single file; Gradio front end; OpenAI hard-coded.
- Fragile JSON handling held together by hand-written normalizers.

v2 reframes the tool from a per-script SAS reviewer into a **multi-language model-documentation and data-lineage platform**.

---

## 2. Vision and objectives

Build a modular, multi-language platform that ingests modeling/analytics code in several languages, produces standardized model documentation and rich, governance-grade data lineage, infers candidate data quality rules from how data elements are used, renders interactive lineage in modern formats, and exposes all of this through a professional web UI with a chat-driven re-run loop.

**Primary objectives**

1. Support multiple source languages (SAS, Python, R, VBA) behind a common interface.
2. Accept code from many input formats and an arbitrary number of models.
3. Produce documentation against a **standard, repeatable structure**.
4. Produce **detailed table- and column-level lineage** plus **inferred data quality rules**.
5. Render lineage in **interactive, scalable formats** (not only PNG).
6. Replace Gradio with a **modern, elegant, professional web front end** with task-specific tabs and a chat feature.
7. Re-architect from a monolith into a **modular codebase**.
8. Be **provider-agnostic** and deployable in environments where source code is sensitive client IP.

---

## 3. Scope

**In scope (v2):** ingestion and language detection; SAS/Python/R/VBA analysis; standardized model documentation; table- and column-level lineage; DQ rule inference; multi-format lineage rendering; web UI with tabs and chat; modular backend; run persistence and provenance; provider-agnostic LLM layer.

**Out of scope (v2, see Section 11):** automatic remediation of code; executing/running the analyzed code; full data catalog product features; multi-tenant SaaS hardening; languages beyond the four named (the design must, however, make adding a language straightforward).

---

## 4. Functional requirements

### FR-1 — Multi-language support
- **FR-1.1** The system shall analyze code written in **SAS, Python, R, and VBA**.
- **FR-1.2** Each language shall be handled by a **language adapter** behind a common interface (a plugin pattern), so a new language can be added without modifying core analysis logic.
- **FR-1.3** Each adapter shall provide: (a) a **detector** (file-extension + content signature), (b) a **structural scanner** for inputs/outputs/transformations, and (c) a **language-specific prompt fragment** that primes the LLM on that language's data-access idioms.
- **FR-1.4** Where practical, adapters shall use real parsing rather than regex alone: Python and R should use AST-based parsing (e.g. Python `ast`, or `tree-sitter` for a uniform approach across languages); SAS and VBA may remain heuristic/regex-based where AST tooling is impractical. The design shall state the chosen approach per language.
- **FR-1.5** Language-specific idioms the scanners/prompts must recognize at minimum:
  - **SAS:** `SET`, `MERGE`, `FROM`, `DATA …;`, `PROC SQL`, `CREATE TABLE`, `libname`.
  - **Python:** `pandas.read_*` / `to_*`, `DataFrame.merge`/`join`, SQLAlchemy, Spark reads/writes.
  - **R:** `read.csv`/`readr`, `dplyr`/`data.table` verbs, `DBI` queries.
  - **VBA:** `Range`/`Cells` references, worksheet sources, `ADODB` queries.

### FR-2 — Input and ingestion
- **FR-2.1** The system shall accept code via: direct paste, single-file upload, multi-file upload, and a **zipped project/folder**.
- **FR-2.2** The system shall extract code from these container/document formats: raw source files (`.sas`, `.py`, `.r`/`.R`, `.bas`/`.vba`, `.sql`, `.txt`), **Word** (`.docx`, extracting code from paragraphs and code-styled runs), and **PDF** (text extraction, with a clear warning that code-in-PDF extraction is lossy).
- **FR-2.3** Language shall be **auto-detected per file** (FR-1.3); the user may override the detected language.
- **FR-2.4** For folder/zip input, each file shall be treated as a candidate "model"; the user shall be able to **merge or split** candidates into logical models.

### FR-3 — Scale / unlimited models
- **FR-3.1** There shall be **no fixed limit** on the number of models (the v1 cap of 5 is removed).
- **FR-3.2** Models shall be processed with **bounded concurrency** and an LLM **rate-limiting** mechanism; per-model progress shall be reported to the UI.
- **FR-3.3** The system shall implement **token-aware chunking**: scripts exceeding the model context window shall be split along logical boundaries (DATA step / function / proc / chunk), analyzed in parts, and merged into one model result.

### FR-4 — Standardized model documentation
- **FR-4.1** For each model, the system shall generate a documentation file following a **fixed, repeatable section structure** (defined in the companion specification, Part A), suitable for a model-risk / governance audience.
- **FR-4.2** The documentation shall be a **projection of the canonical structured state** (see companion spec, Part D), not free-form text — i.e. the document, the workbook, and the diagram all render from one validated object.
- **FR-4.3** Default output format is **DOCX**; the design should keep the renderer pluggable so additional formats (e.g. Markdown, PDF) can be added.

### FR-5 — Enhanced data lineage
- **FR-5.1** Lineage shall be captured at **both table level and column/element level**.
- **FR-5.2** Each lineage edge shall record at minimum: source element, target element, **transformation type** (filter / join / aggregate / derive / rename / cast / passthrough), the **transformation expression** (where extractable), join keys (where applicable), and direction.
- **FR-5.3** The system shall build an **end-to-end, cross-model lineage graph** (source system → intermediate datasets → outputs) spanning all submitted models — this whole-project view is a primary deliverable, not a by-product.
- **FR-5.4** Lineage shall be exported as a **multi-sheet workbook** per the companion specification (Part B). The legacy flat 5-column CSV is superseded but may be offered as a compatibility export.
- **FR-5.5** Each lineage row and DQ rule shall carry **provenance** (LLM-derived vs heuristic-derived) and a **confidence indicator** (see NFR-5).

### FR-6 — Data quality rule inference
- **FR-6.1** The system shall infer **candidate data quality rules** for data elements based on **how each element is used in the code**, mapped to standard DQ dimensions (completeness, validity, uniqueness, consistency, accuracy, timeliness).
- **FR-6.2** Inference shall combine LLM proposals with deterministic heuristics; the rule inference logic is specified in the companion specification (Part C).
- **FR-6.3** Each inferred rule shall include the **code evidence** that triggered it and a suggested **severity**, so the rule is defensible in review.

### FR-7 — Lineage visualization formats
- **FR-7.1** Lineage rendering shall not be limited to PNG. The system shall produce, at minimum: **SVG** and **PDF** (scalable, embeddable), **Mermaid** (portable, version-controllable text), and an **interactive web graph** (zoom, pan, filter by model/system, click to expand table → column level).
- **FR-7.2** The interactive graph shall be exportable to a static format (SVG/PNG/PDF).
- **FR-7.3** An **editable** export (e.g. draw.io / diagrams.net XML) should be offered for reviewers who need to hand-edit the diagram. Optional but recommended.

### FR-8 — Modern front end
- **FR-8.1** Gradio shall be replaced by a **modern web front end** (recommended: React + Vite + Tailwind, with a component library such as shadcn/ui) backed by a Python API (recommended: FastAPI, to keep analysis code in Python).
- **FR-8.2** The UI shall be **elegant, professional, and responsive**, suitable for presenting to a senior/technical audience.
- **FR-8.3** Long-running analysis and chat responses shall stream to the UI (SSE or WebSocket) with visible progress.

### FR-9 — UI tabs and chat-driven re-run
- **FR-9.1** The UI shall provide at least these tabs: **Upload** (submit/organize models), **Review** (read the generated documentation), **Lineage** (interactive graph + downloads), **Data Quality** (inferred rules with evidence), and **Chat**.
- **FR-9.2** The **Chat** tab shall let the user change analysis parameters in natural language and **re-run**. It shall operate on the **structured state**, not as a free-form chatbot — e.g. "treat staging tables as intermediate, not outputs", "raise lineage to column level", "re-analyze model 3 only", "switch language hint for file X to R".
- **FR-9.3** Re-runs shall be **targeted/incremental** where possible — only affected models or stages are reprocessed, not the whole batch.
- **FR-9.4** Results in each tab shall be viewable in the front end directly (not only as file downloads), with downloads available for every artifact.

---

## 5. Non-functional requirements

### NFR-1 — Provider-agnostic LLM layer
- The LLM client shall sit behind one interface supporting multiple providers (**Anthropic Claude, OpenAI, Azure OpenAI, and a local/self-hosted model**). Provider and model shall be configurable. No provider shall be hard-coded into analysis logic.

### NFR-2 — Security and data sensitivity
- Source code submitted may be **sensitive client intellectual property**. The design shall support a deployment mode that uses a **local/on-prem model with no external calls and no retention**, support redaction/exclusion of sensitive content, and avoid writing inputs to durable logs by default. State the data-handling and retention posture explicitly.

### NFR-3 — Robust structured outputs
- LLM outputs shall be validated against a typed schema (recommended: **Pydantic**) with a **validate → retry-on-failure** loop. The v1 defensive normalizers should be re-expressed as schema coercion/validators rather than ad-hoc functions.

### NFR-4 — Persistence and versioning
- Analysis runs shall be **persisted** (recommended: SQLite or DuckDB) so chat edits and re-runs do not reprocess everything and so a run history exists. The system shall support **versioning and diffing** between runs for reproducibility/audit.

### NFR-5 — Provenance, confidence, human-in-the-loop
- Every extracted fact, lineage edge, and DQ rule shall be tagged **LLM-derived vs heuristic-derived** with a confidence indicator. The UI shall let a reviewer **accept/reject/edit** items, and accepted edits shall persist into the structured state.

### NFR-6 — Observability and cost
- The system shall surface **token usage and cost per run** (and per model), and expose basic run telemetry/logs for debugging.

### NFR-7 — Resilience
- A failure analyzing one model shall **not abort the batch**; partial results shall be produced and the failed item clearly flagged.

### NFR-8 — Interoperability / standards
- Lineage should be exportable in a recognized standard (recommended: **OpenLineage**) so output can feed an external catalog (e.g. Collibra) rather than remaining a one-off artifact. Optional but recommended.

### NFR-9 — Testability and maintainability
- Adapters, schema coercion, DQ inference, and exporters shall be unit-testable in isolation. The modular structure (Section 7) is intended to make this straightforward.

### NFR-10 — Configuration
- All operational settings (provider/model, concurrency, detail level, output formats, retention mode) shall be configurable via environment/config file, not code edits.

---

## 6. Recommended architecture (direction)

A layered pipeline in which a **central structured model state is the single source of truth**; every output and the chat loop read from and write to it.

```
Input (paste / files / zip)
        │
        ▼
Ingestion + per-file language detection
        │
        ▼
Language adapters  [ SAS | Python | R | VBA ]   (plugin pattern)
        │
        ▼
LLM engine  (provider-agnostic + schema validation)
        │
        ▼
Analysis orchestrator  →  Structured model state (JSON / DB)   ◄── chat re-run loop
        │
        ▼
Exporters:  Model doc (DOCX) | Lineage (XLSX) | DQ rules | Diagram (SVG/HTML/Mermaid/PDF)
        │
        ▼
API (FastAPI) + React front end  [ Upload · Review · Lineage · DQ · Chat ]
```

The design phase should formalize this (or justify deviations), define the structured-state schema (companion spec Part D), and specify the chat-to-state mapping for FR-9.2.

---

## 7. Recommended module layout (direction)

```
modeltracex/
  ingestion/      file readers (.docx, .pdf, source files), zip/folder handling
  adapters/       base.py + sas.py / python.py / r.py / vba.py (detect, scan, prompt-fragment)
  llm/            provider.py (Claude/OpenAI/Azure/local), prompts/, schema.py (Pydantic)
  analysis/       orchestrator.py, chunking.py, merge.py
  lineage/        graph model, dq_rules.py, exporters (mermaid, svg, openlineage)
  exporters/      docx_report.py, xlsx_workbook.py
  store/          run persistence (SQLite/DuckDB), versioning/diff
  api/            FastAPI routes + SSE/WebSocket
frontend/         React + Vite + Tailwind + shadcn/ui
tests/            unit tests for adapters, schema, dq inference, exporters
```

The single most important separation is **adapters / LLM-provider / schema / exporters**, so each can change independently.

---

## 8. Technology recommendations (non-binding)

| Area | Recommendation | Notes |
|---|---|---|
| Backend | Python + FastAPI | keeps analysis code in Python; SSE/WebSocket for streaming |
| Frontend | React + Vite + Tailwind + shadcn/ui | modern, professional, component-driven |
| Parsing | `tree-sitter` (uniform) or per-language (`ast`, regex) | AST preferred for Python/R |
| LLM | provider-agnostic client | Claude/OpenAI/Azure/local |
| Output validation | Pydantic | schema + retry loop |
| Persistence | SQLite or DuckDB | run history, versioning |
| Diagrams | Graphviz (SVG/PDF) + React Flow or Cytoscape.js (interactive) + Mermaid | beyond PNG |
| Lineage standard | OpenLineage export | optional, for catalog interop |

The design phase owns the final choices and must justify any departures.

---

## 9. Constraints and assumptions

- The platform analyzes code **statically**; it does not execute the submitted code, nor does it require access to the underlying data.
- LLM access is available via at least one configured provider; a local-model path must exist for sensitive deployments (NFR-2).
- Users are technical (model developers, validators, consultants) familiar with the analyzed languages and with model-risk/lineage concepts.

---

## 10. Cross-cutting concerns the design must address

1. **Chat-to-state contract** (FR-9.2/9.3): how natural-language requests map to concrete edits/targeted re-runs.
2. **Confidence & provenance model** (NFR-5): representation, surfacing in UI, persistence of human overrides.
3. **Chunking & merge correctness** (FR-3.3): how partial-model results are merged without losing or duplicating lineage.
4. **Security/retention modes** (NFR-2): local vs cloud, redaction, logging posture.
5. **Extensibility**: adding a new language or a new exporter without touching the core.

---

## 11. Out of scope / future

- Automatic code remediation or rewriting.
- Executing analyzed code or profiling actual data.
- Full data-catalog/governance product features beyond lineage export.
- Multi-tenant SaaS hardening, SSO, RBAC (note as future).
- Languages beyond SAS/Python/R/VBA (design must make adding one easy).

---

## 12. Deliverables expected from the design document

Your SDD should include:

1. **Architecture overview** — components, responsibilities, data flow, deployment view (cloud vs local-model mode).
2. **Canonical data model** — the structured-state schema (entities, fields, relationships), aligned to the companion specification Part D, as concrete type/Pydantic definitions.
3. **Language-adapter interface** — the common contract and one fully worked example adapter (recommend SAS or Python).
4. **LLM-provider abstraction** — interface, prompt-fragment composition, schema-validation/retry loop.
5. **Orchestration & concurrency** — batch processing, rate limiting, chunking/merge, partial-failure handling.
6. **Lineage subsystem** — graph model, table↔column levels, cross-model stitching, and the renderer interfaces (SVG/PDF/Mermaid/interactive/OpenLineage).
7. **DQ inference engine** — how heuristics + LLM proposals combine, evidence capture, severity assignment.
8. **Exporters** — DOCX (per companion Part A) and XLSX (per companion Part B) generation approach.
9. **Persistence & versioning** — schema for runs, diff/versioning approach, human-override storage.
10. **API design** — endpoints, streaming, and the chat-to-state mechanism (FR-9).
11. **Front-end design** — tab structure, key screens/wireframes, state management, streaming UX.
12. **Security & data-handling design** — addressing NFR-2 explicitly.
13. **Testing strategy** — unit/integration coverage for adapters, schema, DQ, exporters.
14. **Migration notes** — what is reused/retired from `ModelTraceX.py` (normalizers → schema validators; regex heuristics → SAS adapter; Graphviz writer → SVG/PDF renderer).
15. **Phasing** — a build sequence (a sensible first milestone: ingestion + SAS & Python adapters + structured state + DOCX/XLSX exporters running end-to-end, before the interactive UI).
16. **Open questions / decisions** — anything requiring a product decision, with a recommended option.

---

## 13. Open questions to resolve in design

- Single uniform parser (`tree-sitter`) vs per-language parsing — recommend and justify.
- Default LLM provider/model for cloud mode, and the local-model option for sensitive mode.
- Interactive graph library: React Flow vs Cytoscape.js vs vis.js — recommend one.
- Whether OpenLineage export is in v2 or deferred.
- Where the chat agent's authority ends (which parameters it may change without explicit confirmation).
