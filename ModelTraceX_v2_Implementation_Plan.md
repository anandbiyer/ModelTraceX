# ModelTraceX v2 — Implementation Plan

**Status:** For execution. Derived from `ModelTraceX_v2_SDD.md` (rev 1.2), `ModelTraceX_v2_Requirements.md`, and `ModelTraceX_v2_Document_and_Lineage_Spec.md`.
**Predecessor:** `ModelTraceX.py` (v1, single-module SAS reviewer — migration targets per SDD §14).
**Purpose:** Turn the SDD's 5-phase roadmap (SDD §16) into concrete, sequenced, testable work items. **Testing is embedded in every phase**, and a **synthetic test-data corpus** is built first so every phase has deterministic fixtures to develop and verify against.

---

## 0. How to read this document

- The phase numbering (**0–4**) maps 1:1 to the SDD's phased roadmap (SDD §16). Each phase here adds: a **task breakdown**, a **testing block** (what to test + how), and the **exit criteria** (lifted from the SDD, made checkable).
- **Phase S (Synthetic Test Data)** is a cross-cutting, build-first workstream (§3 below). It lands during Phase 0 and is extended every phase so the corpus always covers the newest feature.
- Section references like *(SDD §7.3)* point back to the design doc; *(FR-x / NFR-x)* point to requirements; *(Spec Part C)* points to the workbook spec.
- Effort sizing assumes the SDD's team assumption (A3: 3–5 engineers, ~2-week increments). Durations are planning estimates, not commitments.
- `[ ]` checkboxes are the unit of tracking. A phase is "done" only when its exit criteria **and** its testing block are green in CI.

---

## 1. Guiding principles for the build

1. **Canonical-state-first.** `RunState` (SDD §4) is the single source of truth; every artifact is a pure projection. Build and freeze the schema (Phase 0) before anything that reads or writes it.
2. **`FakeProvider`-first, offline CI (SDD §15).** No test depends on a live LLM. `FakeProvider` returns canned, fixture-keyed JSON so the entire pipeline runs deterministically, for free, offline — the same code path local/sensitive deployments use.
3. **Test-alongside, not test-after.** Each task ships with its unit tests in the same PR. Golden-master tests (DOCX 13 sections, XLSX 9 sheets, stable IDs, DQ rule mapping) are written from the synthetic corpus.
4. **Determinism is load-bearing (SDD §9.2, R7).** Stable content-addressed IDs make re-runs diffable and merges idempotent; tests assert ID stability explicitly.
5. **Vertical slice early.** Phase 1 is a headless end-to-end slice (ingest → state → DOCX/XLSX) **before** any UI, validating the spine (SDD §16 note).
6. **Additive schema discipline.** The reconciliations R1–R9 (SDD §2) are already in the schema; new fields are added to `RunState`, never bolted onto projections.

---

## 2. Tech stack & repo bootstrap (precedes Phase 0)

Confirmed from SDD §1 (A2, A6), §3.2, §6, §9.1, §13.4.0.

| Area | Choice | Source |
|---|---|---|
| Backend | Python 3.11+, FastAPI, Pydantic v2, pydantic-settings | SDD A6, §3, §4 |
| Async/concurrency | `asyncio` + `Semaphore` + token-bucket rate limiter | SDD §7.2 |
| LLM providers | Anthropic (`claude-sonnet-4-6` default, `claude-opus-4-7` escalation), OpenAI, Azure OpenAI, Local (Ollama/vLLM, OpenAI-compatible) | SDD §6.1 |
| Parsing | `tree-sitter` (+ stdlib `ast` for Python), `tree-sitter-r`, regex for SAS/VBA | SDD §5.1 |
| Persistence | SQLite via SQLAlchemy (optional DuckDB mirror) | SDD §9.1 |
| Lineage | `networkx` (view only), `graphviz` (SVG/PDF), Mermaid templates, React Flow JSON, `openlineage-python` | SDD §8 |
| Exporters | `python-docx` + `docxtpl` (DOCX), `openpyxl` (XLSX), stdlib `csv` | SDD §11 |
| Frontend | React + Vite + TypeScript + Tailwind (shared MVA dark tokens) + Radix/shadcn; TanStack Query + Zustand; `EventSource` (SSE) | SDD §13.4.0 |
| Testing | `pytest`, `pytest-asyncio`, `coverage`; `vitest` + React Testing Library + Playwright (FE); `FakeProvider` fixture | SDD §15 |

**Bootstrap tasks (Week 0):**
- [ ] Create `modeltracex/` package per the SDD §20 skeleton; `pyproject.toml`, lockfile, `ruff`/`black`/`mypy` config.
- [ ] Create `frontend/` Vite scaffold (deferred wiring until Phase 2) with the shared dark design tokens stubbed.
- [ ] CI pipeline: lint → type-check → `pytest` (offline, `FakeProvider`) → coverage gate. No network calls in CI.
- [ ] `.env.example` + `config.py` (`pydantic-settings`) with `provider`, `model`, `security_mode`, `max_concurrency`, `detail_level`, `output_formats`, `retention` (NFR-10).
- [ ] Decide and document the v1 retirement: keep `ModelTraceX.py` read-only as a migration reference until Phase 1 SAS adapter reaches parity (SDD §14), then remove.

---

## 3. Phase S — Synthetic test-data corpus (build-first, extended every phase)

> **Goal:** a versioned, deterministic corpus of synthetic source code + expected outputs that lets every phase be developed and verified without real client IP and without a live LLM. This is the backbone of the "test alongside" principle. Real client SAS/Python is **never** committed.

### 3.1 Where it lives
```
tests/
├─ fixtures/
│  ├─ corpus/                  # synthetic input source files
│  │  ├─ sas/                  # *.sas
│  │  ├─ python/               # *.py
│  │  ├─ r/                    # *.R
│  │  ├─ vba/                  # *.bas / *.vba
│  │  ├─ docx/  pdf/  zip/     # ingestion-format fixtures
│  │  └─ projects/             # multi-file, multi-language projects (cross-model)
│  ├─ golden/                  # expected outputs
│  │  ├─ runstate/             # canonical RunState JSON per project
│  │  ├─ structural_scans/     # expected StructuralScan per source file
│  │  ├─ dq/                   # expected DQRule sets (Part C coverage)
│  │  ├─ docx/                 # golden structural assertions (13 sections)
│  │  └─ xlsx/                 # golden structural assertions (9 sheets)
│  └─ fake_provider/           # canned LLM JSON keyed by (model_id, chunk_hash)
└─ tools/
   └─ gen_synthetic.py         # parametric generator (scale + randomized corpora)
```

### 3.2 Corpus design — each fixture targets a specific behaviour

**(a) DQ-coverage scripts — one usage per Part C row (Spec Part C).** A small SAS file (and a Python twin) per inference rule, so the DQ engine's heuristic mapper is provably exercised end to end:

| Synthetic snippet | Triggers `UsageKind` | Expected rule / dimension / severity (Part C) |
|---|---|---|
| `ratio = revenue / headcount;` | `DENOMINATOR` | non-null & non-zero / Validity / High |
| `merge a b; by cust_id;` / `df.merge(on="cust_id")` | `JOIN_KEY` | uniqueness + ref-integrity / Uniqueness·Consistency / High |
| `dt = datepart(ts);` / `pd.to_datetime(col)` | `DATE_PARSE` | valid date in range / Validity / Medium |
| `where amt > 1000;` | `RANGE_FILTER` | within expected range / Validity / Medium |
| `proc means; by region;` / `groupby().agg` | `AGGREGATED` | completeness on grain / Completeness / Medium |
| `x = input(s, 8.);` / `.astype(float)` | `TYPE_CAST` | type conformance / Accuracy / Medium |
| `where status in ('A','B');` | `EQUALITY_SET` | allowed-value domain / Validity / Medium |
| output `score` column | `OUTPUT_MEASURE` | non-null, not all-zero / Completeness / Medium |
| `where asof between ...;` | `TIME_WINDOW` | timeliness / Timeliness / Low |
| cross-libname join | `CROSS_SYSTEM_JOIN` | cross-system consistency / Consistency / Medium |

**(b) Cross-model stitch project (SDD §8.1, FR-5.3).** A multi-file project where Model A writes `work.staging` and Model B reads `work.staging` — the corpus must prove canonical `table_id` makes them the **same node** and that end-to-end Source→Intermediate→Output lineage stitches.

**(c) Language-coverage set.** At least 2 scripts per language (SAS, Python, R, VBA) exercising each adapter's detect / scan / split-points, including the SAS macro-heavy case that defeats AST (SDD §5.1) and the staging-as-intermediate reclassification case (for the Chat role-change test in Phase 3).

**(d) Robustness / malformed-LLM set (SDD §15 "Schema/coercion").** The exact malformed-JSON shapes v1's hand-written normalizers had to absorb (tables as dict/string/CSV/`None`, lineage rows as scalars). Stored as `FakeProvider` responses to prove the Pydantic validators + retry loop (SDD §6.3) recover them.

**(e) Ingestion-format set (FR-2.1/2.2).** Same logical model delivered as paste, single file, multi-file, zipped project, `.docx`, and `.pdf` (the PDF intentionally lossy, to assert the lossy-extraction `Issue`).

**(f) Chunking set (FR-3.3).** An oversized SAS file with many DATA/PROC boundaries to force `split_points` chunking and assert idempotent id-keyed merge (no lost/duplicated lineage).

**(g) Partial-failure set (NFR-7).** A project where one model's `FakeProvider` response is forced to fail validation past retries — asserts `status=Failed`, an `Issue`, heuristic-only retention, and **batch continuation**.

**(h) Golden master from v1 (SDD §15).** The v1 SAS sample run through v2 to confirm SAS-adapter parity + improvement.

### 3.3 The generator — `tests/tools/gen_synthetic.py`
- [ ] Parametric generator that emits valid synthetic SAS/Python/R/VBA from templates with controllable knobs: `#models`, `#tables`, `columns/table`, `cross_model_edges`, `dq_usage_mix`, `language_mix`, `chunk_pressure` (file size).
- [ ] **Scale corpora** for Phase 3: generate 50- and 500-model projects to exercise bounded concurrency, rate limiting, chunking, and large-graph rendering/virtualization.
- [ ] Seeded RNG so generated corpora are reproducible and golden outputs are stable.
- [ ] A `--with-fake-responses` mode that also emits matching `FakeProvider` JSON, so generated projects run headless E2E with no live LLM.

### 3.4 Testing of the corpus itself
- [ ] A "corpus smoke" test asserts every fixture file parses and every golden file is valid JSON/schema-valid.
- [ ] A coverage assertion: the DQ-coverage set collectively triggers **every** `UsageKind` and **every** `DQDimension` (fails CI if a Part C row loses coverage).

> **Why first:** the corpus is the substrate for Phase 0's `FakeProvider` E2E and every subsequent golden test. Building it first means no phase is ever blocked on "what do we test against."

---

## 4. Phase 0 — Foundation

**SDD scope:** Repo/module scaffold (SDD §20 layout), config (NFR-10), Pydantic schema (SDD §4), `LLMProvider` + Anthropic + `FakeProvider`, retry loop, SQLite store, stable IDs.
**SDD exit criterion:** `FakeProvider` E2E produces a valid `RunState`.

### 4.1 Tasks
- [ ] **Schema (`state.py`, `llm/schema.py`).** All enums (SDD §4.1), `Provenanced` mixin with `review_status` (R9/D1), all core entities, `RunState`, and the narrower per-model `ModelExtraction` LLM target (SDD §4 decision). Include the R1–R9 additive fields (`telemetry`, `UsageObservation`, `related_elements`, `review_status`, derived `source_systems`).
- [ ] **Stable IDs (`ids.py`, SDD §9.2).** `table_id/model_id/table_edge_id/column_edge_id/rule_id` content-hash helpers + canonicalization that resolves libname/schema aliases to one id.
- [ ] **Config (`config.py`, NFR-10).** `Settings` via pydantic-settings; provider/model/security_mode/concurrency/detail_level/output_formats/retention.
- [ ] **Provider abstraction (`llm/provider.py`, `anthropic.py`, `fake.py`, SDD §6.1).** `LLMProvider` Protocol, factory, `AnthropicProvider`, `FakeProvider`, and the **egress guard** (SDD §14.3) at construction time.
- [ ] **Validate→retry loop (`llm/structured.py`, SDD §6.3).** `structured_call()` with bounded retries → `SchemaValidationError` on exhaustion (caller degrades to heuristic-only).
- [ ] **Store (`store/db.py`, SDD §9.1).** SQLAlchemy models + SQLite; `runs.state_json` (full validated blob) plus flattened query tables; `overrides` table.
- [ ] **Minimal orchestrator stub + `cli.py`.** Enough to drive a `FakeProvider` run through assembly into a persisted `RunState` (full orchestrator lands in Phase 1).

### 4.2 Testing (Phase 0)
- [ ] **Schema/coercion tests** — feed the malformed-LLM set (§3.2d) through Pydantic validators + retry; assert recovery (replaces v1 normalizers; SDD §15).
- [ ] **Stable-ID determinism** — same input → identical IDs across runs; alias canonicalization collapses `work.staging` ↔ resolved name (SDD §15 Lineage row).
- [ ] **Egress guard** — constructing any external provider while `security_mode=local` raises `SecurityError` (NFR-2, SDD §14.3).
- [ ] **Provider conformance harness** — shared suite parametrized over providers + `FakeProvider`; only `FakeProvider` runs in CI (SDD §15).
- [ ] **Store round-trip** — persist `RunState` → reload → deep-equal; overrides logged and re-applied by id.
- [ ] **Phase-0 exit test:** `FakeProvider` E2E (using a §3.2 fixture) produces a schema-valid `RunState` persisted to SQLite. ✅ matches SDD exit criterion.

---

## 5. Phase 1 — First milestone (headless E2E)

**SDD scope:** Ingestion (paste/file/zip/docx/pdf) + **SAS & Python adapters** + structured state + **DOCX & XLSX exporters** + Graphviz SVG/Mermaid + deterministic DQ subset. Run via CLI/headless API.
**SDD exit criterion:** A SAS+Python project produces a valid Part A DOCX + Part B XLSX end-to-end, **no interactive UI**.

### 5.1 Tasks
- [ ] **Ingestion (`ingestion/`, FR-2.1/2.2).** `readers.py` (text, `docx_extract`, `pdf_extract` w/ lossy `Issue`), `archive.py` (unzip → `SourceArtifact`s), `detect.py` over the adapter registry; merge/split into logical models.
- [ ] **Adapter base + registry (`adapters/base.py`, SDD §5.1).** `LanguageAdapter` Protocol, `DetectionResult`, `StructuralScan`, `register()`/`detect_language()`.
- [ ] **SAS adapter (`adapters/sas.py`, SDD §5.2).** Migrate v1 `SAS_*_REGEX`/`heuristic_scan_tables`; expand for `MERGE`/`PROC SQL`/`libname`; emit `UsageObservation`s for all Part C signals; `split_points` on DATA/PROC.
- [ ] **Python adapter (`adapters/python.py`, SDD §5.1/§5.2 sketch).** `ast` + tree-sitter; detect `pd.read_*`/`to_*`, `merge`/`join` (+`on=` keys), `groupby().agg`, `/` divisor, `to_datetime`, `.astype`; `split_points` on top-level defs.
- [ ] **Prompts (`llm/prompts.py`, SDD §6.2).** Base reviewer prompt + adapter `prompt_fragment()` + detail-level fragment + schema instruction composition.
- [ ] **Orchestrator (`analysis/orchestrator.py`, `chunking.py`, `merge.py`, SDD §7).** Async batch with `Semaphore` + token-bucket rate limiter; token-aware chunking via `adapter.split_points`; idempotent id-keyed merge; partial-failure isolation (NFR-7); assemble `RunState` from `ModelExtraction`s + scans.
- [ ] **Lineage core + renderers (`lineage/`, SDD §8).** `LineageGraph` (networkx view), cross-model stitch by canonical `table_id`, `GraphvizRenderer` (SVG/PDF, migrates v1 swim-lanes), `MermaidRenderer`.
- [ ] **DQ engine — deterministic subset (`dq/rules_table.py`, `engine.py`, SDD §10, Spec Part C).** Declarative Part C mapping (heuristic mapper only this phase; LLM proposer deferred to richer use later); evidence attachment; severity defaults; `status=Proposed`.
- [ ] **Exporters (`exporters/`, SDD §11).** `DocxExporter` (Part A 13 sections, "Not identified from code" rule, tables not prose, provenance callouts, project-level summary doc), `XlsxExporter` (exact 9 sheets + columns, color-coded provenance/confidence), `csv_compat.py` (legacy 5-col).
- [ ] **Headless API/CLI.** `cli.py` end-to-end entrypoint + the headless subset of FastAPI routes needed to drive a run (full REST in Phase 2).

### 5.2 Testing (Phase 1)
- [ ] **Adapter tests (NFR-9)** — each corpus source file → expected `StructuralScan` (golden §3.2); SAS golden-master parity vs v1 (§3.2h).
- [ ] **DQ engine tests** — DQ-coverage set (§3.2a) → expected rule/dimension/severity per Part C row; coverage assertion (§3.4) gates CI.
- [ ] **Chunk-merge idempotence** — chunking set (§3.2f): chunked vs unchunked run produce identical `RunState` (no lost/dup lineage; SDD §7.3).
- [ ] **Cross-model stitch** — stitch project (§3.2b): output of A == input of B by `table_id`; end-to-end path exists.
- [ ] **Partial-failure** — failure set (§3.2g): one model `Failed` + `Issue`, others `Analyzed`, batch completes (NFR-7).
- [ ] **Exporter golden tests (SDD §15)** — DOCX: all 13 sections present, empty → "Not identified from code", inputs/outputs/DQ as tables; XLSX: exactly 9 sheets, exact column headers/order, provenance color coding; CSV: 5-column compat.
- [ ] **Ingestion tests** — format set (§3.2e): paste/file/zip/docx all yield equivalent models; PDF raises lossy `Issue`.
- [ ] **Phase-1 exit test:** the SAS+Python stitch project (FakeProvider) → valid Part A DOCX + Part B XLSX, fully headless. ✅ matches SDD exit criterion and Requirements §12.15.

---

## 6. Phase 2 — Lineage + UI

**SDD scope:** Full column-level lineage + cross-model stitch; interactive React Flow graph; FastAPI + React (Upload/Review/Lineage/DQ tabs); SSE progress; provenance + accept/reject (NFR-5).
**SDD exit criterion:** Reviewer can browse + accept/reject in the browser; interactive drill-down works.

### 6.1 Backend tasks
- [ ] **Full REST surface (SDD §13.1).** `/runs`, `/runs/{id}/ingest`, `PATCH /models`, `/analyze`, `/state`, `/lineage?level=`, `/exports/{kind}`, `POST /overrides`, `POST /estimate` (pre-flight token/cost, D4/NFR-6).
- [ ] **SSE channel (`/runs/{id}/events`, FR-8.3).** Multiplex per-model progress (`model_id/status/pct`), incremental projection updates.
- [ ] **Column-level lineage (FR-5.1).** Column edges as authoritative home of expressions (R4); `ReactFlowModel` JSON serializer with provenance/confidence on nodes; lazy column-subgraph endpoint (`level=column&table=<id>`).
- [ ] **Overrides + review_status (NFR-5, R9/D1).** Accept/reject/edit on tables, columns, **and** edges; writes logged to `overrides`, flips `review_status`; "N edges pending review" counter source.

### 6.2 Frontend tasks (SDD §13.4)
- [ ] **Design system foundation (§13.4.0).** Shared MVA dark tokens, Manrope + JetBrains Mono, provenance pill / confidence dot / status encodings, app-shell header (D2/D11), underline tab bar.
- [ ] **Shared primitives.** Inspector shell (node/edge/rule + accept/reject/edit), filter chips (incl. "Low-confidence only", D9), diff block.
- [ ] **Upload tab (§13.4.1).** Dropzone/multi-file/zip/paste, file→model table, language badge override (D5), data-handling segmented control (D6), lineage-detail toggle, concurrency, pre-flight estimate.
- [ ] **Review tab (§13.4.2).** Project-summary + model list with confidence/status, document pane rendered live from `RunState` in Part A section order, provenance callouts, per-model + project DOCX download.
- [ ] **Lineage tab (§13.4.3).** React Flow swim-lanes (cyan/purple/green), node cards, edge labels, edge **and** node inspector, in-place column expansion (lazy), "N edges pending review", export menu.
- [ ] **Data Quality tab (§13.4.4).** Metrics row, dimension/severity/low-conf filter chips, Sheet-7 rule register with inline evidence + inline accept/reject.
- [ ] **State/streaming (§13.4.7).** TanStack Query (server state, optimistic accept/reject) + Zustand (UI state); `EventSource` wiring.

### 6.3 Testing (Phase 2)
- [ ] **API tests** — each route: happy path + validation errors; `/estimate` returns a token/cost figure from adapter scans without an LLM call.
- [ ] **SSE test** — progress events emitted per model; partial results visible before run completes (NFR-7).
- [ ] **Column-lineage tests** — expression home is the column edge (R4); table→column lazy expand returns correct subgraph; collapsed tables aggregate edges (no orphans, SDD §13.4.3b).
- [ ] **Override tests** — accept/reject/edit flips `review_status`, logs `override`, survives re-run by id (SDD §9.3).
- [ ] **Frontend unit tests (vitest/RTL)** — inspector accept/reject, badge override, filter chips, provenance/confidence rendering.
- [ ] **E2E (Playwright)** — upload corpus project → analyze (FakeProvider backend) → browse Review → expand a table in Lineage → accept an edge → download DOCX. ✅ matches SDD exit criterion.

---

## 7. Phase 3 — Chat + scale + languages

**SDD scope:** Chat-driven re-run + targeted re-runs + authority boundary; versioning/diff UI; **R & VBA adapters**; token-aware chunking at scale; cost telemetry UI (NFR-6).
**SDD exit criterion:** NL "raise model 3 to column level" reprocesses only m3; R/VBA analyzed.

### 7.1 Tasks
- [ ] **ChatAgent (`chat/`, SDD §13.2).** NL → typed `StateMutationPlan` via tool-calling, validated through the §6.3 loop; `requires_confirmation` set by the **authority policy**, never the LLM.
- [ ] **Authority boundary (SDD §13.2/§13.4.5, Q5).** Auto-apply set (`set_table_role`, `set_language_hint`, `set_lineage_detail`, `reanalyze_scope`, `set_detail_level`); confirm-required set (`merge_models`, `split_model`, bulk accept/reject, `set_provider`, `security_mode`).
- [ ] **Targeted/incremental re-run (SDD §13.3, FR-9.3).** Stage-dependency DAG (ingest → per-model → stitch → DQ → export); compute minimal invalidation set per mutation; projection-only mutations re-stitch/DQ/export at ~0 token cost (D8).
- [ ] **Chat tab (§13.4.5).** Diff-block rendering of mutations, impact summary, Apply-&-re-run vs Apply-without-re-run buttons derived from mutation type.
- [ ] **Versioning & diff (SDD §9.3, NFR-4).** `diff(run_a, run_b)` set comparison over stable IDs → added/removed/changed; run-compare UI; stale-override `Issue` handling.
- [ ] **R adapter (`adapters/r.py`).** `tree-sitter-r`; `StructuralScan` + Part C usages + `split_points`.
- [ ] **VBA adapter (`adapters/vba.py`).** Heuristic/regex (no robust grammar, SDD §5.1); `StructuralScan` + usages.
- [ ] **DQ LLM proposer (SDD §10).** Add the LLM proposal path (E/I, review-required) + merge/dedupe by `(element, dimension)` + relational rules via `related_elements` (R6).
- [ ] **Scale hardening.** Run the 50- & 500-model generated corpora (§3.3); tune concurrency/rate-limit/chunking; content-hash caching (R4 risk control).
- [ ] **Cost telemetry UI (NFR-6, R2).** Per-run **and** per-model tokens/cost from `ModelTelemetry`; surfaced in header + Run Summary.

### 7.2 Testing (Phase 3)
- [ ] **Chat NL→plan tests (SDD §15)** — fixture NL commands → expected `StateMutationPlan`; authority-boundary gating asserted (auto vs confirm).
- [ ] **Targeted-rerun invalidation tests** — `set_table_role` triggers no LLM call (re-stitch/DQ/export only); `reanalyze_scope([m3])` re-runs only m3; `set_lineage_detail("column")` re-analyzes affected models. ✅ exit criterion.
- [ ] **R/VBA adapter tests** — language-coverage set (§3.2c) → expected `StructuralScan`; detection picks correct adapter.
- [ ] **Diff tests** — re-run unchanged project → empty diff; targeted change → precise added/removed/changed; override re-application across runs.
- [ ] **Scale tests** — 500-model corpus completes within concurrency/rate budget; chunk-merge stays idempotent at scale; graph renders with virtualization.
- [ ] **DQ proposer tests** — LLM-proposed rule merges with heuristic by `(element, dimension)`; relational rule populates `related_elements`.

---

## 8. Phase 4 — Interop + sensitive hardening

**SDD scope:** OpenLineage export; draw.io export; local-model deployment + egress guard + redaction (NFR-2) hardened; polish.
**SDD exit criterion:** Verified no-egress local run; OL export consumed by a catalog.

### 8.1 Tasks
- [ ] **OpenLineage exporter (`lineage/openlineage.py`, NFR-8, SDD §8.2, Q4).** `columnLineage` facet from `column_edges`; datasets=tables, job=model, run=`RunMeta`; export-only (no live push).
- [ ] **draw.io exporter (FR-7.3).** Editable XML from the same graph JSON contract.
- [ ] **Local deployment profile (SDD §3.4, §12).** `LocalProvider` (OpenAI-compatible → Ollama/vLLM, default Qwen2.5-Coder-32B); single-binary, two-profile config; localhost-only binding.
- [ ] **Redaction (`redactor`, SDD §12).** Pre-LLM masking of configurable patterns (emails/account#/secrets); redaction recorded as an `Issue`.
- [ ] **Retention/logging posture (SDD §12).** Local mode: no source bodies in `state_json` unless `retain_source=true`; metadata-only logs; keys via env/secret store, never in DB.
- [ ] **Per-run security mode UI (D6).** Local↔Cloud segmented control bounded by config; Cloud rendered **disabled** (not hidden) if org forces local.
- [ ] **Polish.** Accessibility, empty/error states, docs, packaging, deployment guide (cloud + local).

### 8.2 Testing (Phase 4)
- [ ] **No-egress verification** — run the full pipeline in `security_mode=local` behind a blocked-egress test harness; assert zero external calls and that constructing a cloud provider raises (SDD §14.3). ✅ exit criterion.
- [ ] **OpenLineage validation** — emitted events validate against the OL schema and load into a reference catalog (e.g. Marquez) in CI. ✅ exit criterion.
- [ ] **Redaction tests** — seeded PII patterns masked before any provider call; `Issue` recorded.
- [ ] **Retention tests** — local mode persists no source bodies unless `retain_source=true`; logs contain no code/PII.
- [ ] **draw.io test** — exported XML opens / round-trips structurally.
- [ ] **Local-provider conformance** — provider conformance suite (SDD §15) passes against `LocalProvider` (mocked OpenAI-compatible endpoint in CI).

---

## 9. Continuous testing infrastructure (all phases)

- [ ] **Offline CI gate (SDD §15).** Lint + type-check + `pytest` with `FakeProvider`; **no network**. Coverage threshold enforced.
- [ ] **Golden-file regeneration command** — a make/nox target to regenerate goldens from the corpus when schema/templates change intentionally, with diff review.
- [ ] **Provider conformance suite** — one shared parametrized suite over all providers; live-provider runs gated to a manual/nightly job with secrets, never blocking PR CI.
- [ ] **Integration E2E (SDD §15)** — SAS+Python project → `RunState` → DOCX/XLSX with `FakeProvider`, run every phase as a regression anchor.
- [ ] **Frontend test tiers** — vitest unit, RTL component, Playwright E2E against a `FakeProvider`-backed API.
- [ ] **Coverage targets** — adapters/DQ/exporters/IDs (the determinism-critical core) held to a higher bar than glue/UI.

---

## 10. Traceability — phase → SDD deliverables → requirements

| Phase | SDD deliverables covered | Key FR/NFR |
|---|---|---|
| S (corpus) | §15 testing substrate | NFR-9; FR-6 (Part C coverage) |
| 0 | D2 schema (§4), D4 provider abstraction (§6), D9 persistence/IDs (§9), egress guard (§14.3) | NFR-1, NFR-3, NFR-4, NFR-10, NFR-2 (guard) |
| 1 | D1 architecture (§3), D3 adapters (§5), D5 orchestration (§7), D6 lineage (§8), D7 DQ (§10), D8 exporters (§11) | FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7 (static), NFR-7 |
| 2 | D10 API (§13.1), D11 front end (§13.4), D6 lineage interactive | FR-5.1, FR-7.1, FR-8.3, FR-9.1/9.4, NFR-5, NFR-6 (estimate) |
| 3 | D16 chat-to-state (§13.2/13.3), R & VBA adapters, versioning/diff | FR-9.2/9.3, NFR-4, NFR-6 |
| 4 | OpenLineage + draw.io (§8.2), security/data-handling (§12) | FR-7.3, NFR-2, NFR-8 |

Full FR/NFR ↔ design traceability remains SDD §19; full UI↔requirement traceability remains SDD §19.1. This table maps **when** each is implemented.

---

## 11. Sequencing, dependencies & risk controls

- **Hard dependency chain:** Phase S corpus + Phase 0 schema/IDs/provider gate everything. Do not start adapters or exporters before the schema is frozen and stable IDs pass determinism tests.
- **Spine-before-UI (SDD §16 note, R7):** Phase 1 must produce real DOCX/XLSX headless before any Phase 2 UI investment — validates the canonical-state design at lowest cost.
- **Risk controls map to SDD §18:**
  - Hallucinated lineage (R1) → heuristic cross-check + provenance/confidence + golden tests (Phases 1–2).
  - SAS/VBA defeat static analysis (R2) → heuristic + "Not identified" + `Issues` (Phases 1, 3).
  - Chunk/merge loss (R3) → stable-ID idempotent merge + chunking tests (Phase 1).
  - Token cost/scale (R4) → concurrency/rate-limit/chunk/caching + scale corpora (Phase 3).
  - Sensitive egress (R5) → local mode + egress guard + redaction (Phases 0 guard, 4 hardening).
  - Chat destructive edits (R6) → typed plan + authority boundary + reversible overrides (Phase 3).
  - Scope (R7) → this phased plan with a headless first milestone.
- **Non-blocking product calls to confirm (SDD §17):** firm phase durations once team size is set; redaction default-on vs off in cloud mode; exact cloud model tier vs budget; final suite name ("Modelis" is a placeholder); lineage-lane green retained (SDD §17 resolution).

---

## 12. Milestone acceptance checklist (one line per phase exit)

- [ ] **Phase S:** corpus committed; coverage test proves every `UsageKind`/`DQDimension` exercised; generator produces scale + fake-response corpora.
- [ ] **Phase 0:** `FakeProvider` E2E produces a schema-valid, persisted `RunState`; stable-ID and egress-guard tests green.
- [ ] **Phase 1:** SAS+Python project → valid Part A DOCX + Part B XLSX, fully headless; adapter/DQ/exporter goldens green.
- [ ] **Phase 2:** reviewer can upload → browse Review → drill into column lineage → accept/reject edges in the browser; Playwright E2E green.
- [ ] **Phase 3:** "raise model 3 to column level" re-runs only m3; R/VBA analyzed; diff + scale tests green.
- [ ] **Phase 4:** verified no-egress local run; OpenLineage export validates and loads into a catalog; redaction/retention tests green.

---

*End of implementation plan. Tracks `ModelTraceX_v2_SDD.md` rev 1.2; update in lockstep if the SDD revises.*
