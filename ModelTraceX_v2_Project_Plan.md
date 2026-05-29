# ModelTraceX v2 — Activity-Wise Project Plan & Status Tracker

**Purpose:** the living, phase-level activity tracker for the v2 build. Source of truth for *what/how* is
[`ModelTraceX_v2_Implementation_Plan.md`](./ModelTraceX_v2_Implementation_Plan.md) (which itself derives from
`ModelTraceX_v2_SDD.md` rev 1.2). This file tracks *progress only*.
**Created:** 2026-05-26 · all activities initialized to `Not Started`.

## Status legend
`Not Started` · `In Progress` · `Done` · `Blocked`

## How to update this file
- When work on an activity begins, set its **Status** to `In Progress`; when it lands (code **and** its tests green in CI), set `Done`. Use `Blocked` + a **Notes** reason when stalled.
- A phase is **Done only when its exit-criterion activity passes** (rows tagged **[EXIT]**).
- When a phase's activities complete, refresh that phase's row in the **Status Dashboard** below (state + done/total count).
- Activity IDs are stable — reference them in commits/PRs (e.g. "closes P1-3") so status maps to a fixed key.

---

## Status Dashboard

| Phase | Activities | Done / Total | State |
|---|---|---|---|
| Pre-Phase 0 — Bootstrap | PRE-1..5 | 5 / 5 | ✅ Done (2026-05-26) |
| Phase S — Synthetic Test Data | S-1..13 | 13 / 13 | ✅ Done (2026-05-26) |
| Phase 0 — Foundation | P0-1..7, P0-T1..6 | 13 / 13 | ✅ Done (2026-05-26) |
| Phase 1 — Headless E2E | P1-1..10, P1-T1..8 | 18 / 18 | ✅ Done (2026-05-26) |
| Phase 2 — Lineage + UI | P2-1..11, P2-T1..6 | 17 / 17 | ✅ Done (2026-05-27) |
| Phase 3 — Chat + Scale + Languages | P3-1..10, P3-T1..6 | 16 / 16 | ✅ Done (2026-05-28) |
| Phase 4 — Interop + Sensitive Hardening | P4-1..7, P4-T1..6 | 13 / 13 | ✅ Done (2026-05-29) |
| Continuous Testing (cross-cutting) | CT-1..6 | 0 / 6 | Not Started |
| **Total** | | **95 / 101** | **In Progress** |

---

## Pre-Phase 0 — Bootstrap (Implementation Plan §2)

| ID | Activity | Status | Notes |
|---|---|---|---|
| PRE-1 | Create `modeltracex/` package per SDD §20 skeleton; `pyproject.toml`, lockfile, ruff/black/mypy config | ✅ Done | Full SDD §20 tree as importable stubs; `pyproject.toml` (hatchling) + `requirements-dev.lock`. Uses **ruff format** in place of black. Verified: `ruff check` clean, `mypy` clean (39 files). |
| PRE-2 | Create `frontend/` Vite scaffold with shared dark design tokens stubbed (full wiring deferred to Phase 2) | ✅ Done | Vite+React+TS+Tailwind; shared MVA dark tokens in `src/styles/tokens.css` mirrored into `tailwind.config.ts`; app-shell + 5-tab placeholder. `npm install` deferred to Phase 2. |
| PRE-3 | CI pipeline: lint → type-check → `pytest` (offline, FakeProvider) → coverage gate; no network in CI | ✅ Done | `.github/workflows/ci.yml` (3.11/3.12 matrix): ruff → ruff format → mypy → pytest+coverage. `MODELTRACEX_PROVIDER=fake`, no LLM calls. |
| PRE-4 | `.env.example` + `config.py` (pydantic-settings): provider, model, security_mode, max_concurrency, detail_level, output_formats, retention (NFR-10) | ✅ Done | `Settings` w/ all listed fields + secrets; env-prefix `MODELTRACEX_`. Verified via `cli --show-config` + 5 smoke tests (defaults, env override, secret exclusion). Refined in P0-3 once state.py enums land. |
| PRE-5 | Document v1 retirement: keep `ModelTraceX.py` read-only as migration reference until SAS parity, then remove (SDD §14) | ✅ Done | v1 source restored to `reference/v1/` (read-only, git-excluded from tooling); `docs/MIGRATION_v1_to_v2.md` records element-by-element disposition + retirement policy. |

---

## Phase S — Synthetic Test Data (Implementation Plan §3) · build-first, extended each phase

| ID | Activity | Status | Notes |
|---|---|---|---|
| S-1 | Create `tests/fixtures/` (corpus, golden, fake_provider) + `tests/tools/` directory structure (§3.1) | ✅ Done | Full tree under `tests/fixtures/corpus/{dq_coverage,projects,languages,chunking,ingestion,golden_v1}`, `golden/` (placeholder README), `fake_provider/{malformed,partial_failure}`, `tests/tools/`. Adopted the README's **co-located `expected.json`** convention (schema-neutral golden) over the §3.1 `golden/structural_scans/` sketch. |
| S-2 | DQ-coverage scripts — one SAS file + Python twin per Part C inference rule (denominator, join key, date-parse, range filter, aggregation, type-cast, equality-set, output measure, time-window, cross-system join) (§3.2a) | ✅ Done | 10 dirs under `dq_coverage/` (one per `usage_kind`), each a SAS + Python twin + `expected.json` (dimensions/severity/Part C statement). Coverage gate (S-13) confirms all 10 kinds + all 6 dimensions exercised. |
| S-3 | Cross-model stitch project — Model A writes `work.staging`, Model B reads it (canonical table_id → same node) (§3.2b) | ✅ Done | `projects/stitch_scoring/` (m1 writes `work.staging`, m2 reads it); `expected.json` declares the canonical-id stitch + Source→Intermediate→Output path `raw.customer_events → work.staging → mart.customer_scores`. |
| S-4 | Language-coverage set — ≥2 scripts per SAS/Python/R/VBA, incl. SAS macro-heavy + staging-reclassification cases (§3.2c) | ✅ Done | `languages/{sas,python,r,vba}` (2 each, incl. `macro_heavy.sas`, `staging_reclass.sas`) + `projects/multilang_pipeline/` (SAS→Python→R→VBA sharing staging tables). Per-dir `expected.json` (`fixtures` map). |
| S-5 | Malformed-LLM / robustness set — tables as dict/string/CSV/None, lineage rows as scalars (replaces v1 normalizer cases) (§3.2d) | ✅ Done | `fake_provider/malformed/` — 5 raw responses (tables as dict/string/csv/null, lineage as scalar); `expected.json` declares the coercion target per case + `recovers_without_retry`. Replaces v1 `_normalize_tables`/`_normalize_lineage_rows`. |
| S-6 | Ingestion-format set — same model as paste / single / multi-file / zip / docx / lossy-pdf (§3.2e) | ✅ Done | `ingestion/` paste/single/multi committed; zip/pdf/docx materialized by `tests/tools/build_corpus.py` (stdlib zip + **intentionally lossy** stdlib PDF; docx optional on `python-docx`). Binaries gitignored, rebuilt by a session fixture in CI. |
| S-7 | Chunking set — oversized SAS file with many DATA/PROC boundaries (§3.2f) | ✅ Done | `chunking/oversized_etl.sas` (12 DATA/PROC boundaries, linear chain) + `expected.json` (full table set + 12 table-edges + `expected_split_points_min`) for the Phase-1 idempotent-merge assertion. |
| S-8 | Partial-failure set — one model's FakeProvider response forced to fail validation past retries (§3.2g) | ✅ Done | `fake_provider/partial_failure/` — `always_invalid.json` (bare scalar, non-coercible → fails every retry) + healthy sibling; `expected.json` asserts Failed + Issue + heuristic-only retention + batch continues. |
| S-9 | v1 SAS golden master — v1 sample run through v2 for parity + improvement (§3.2h) | ✅ Done | `golden_v1/v1_sample.sas` (SET/FROM/DATA/CREATE TABLE) + `expected.json` with `v1_facts` (parity floor) and `v2_improvements` (DQ usages + role classification) for the Phase-1 SAS parity test. |
| S-10 | `gen_synthetic.py` parametric generator (knobs: #models, #tables, columns/table, cross-model edges, dq mix, language mix, chunk pressure) (§3.3) | ✅ Done | `tests/tools/gen_synthetic.py` — all knobs as CLI flags; SAS/Python/R/VBA emitters with per-`usage_kind` DQ injection; writes per-model sources + `manifest.json` (models/tables/edges/coverage). |
| S-11 | Scale corpora — generate 50- and 500-model projects (§3.3) | ✅ Done | Generated on demand into gitignored `_generated/` (`--models 50/500`, documented in `fixtures/README.md`); generator verified at small scale in CI to keep the offline gate fast. |
| S-12 | Seeded RNG (reproducible) + `--with-fake-responses` mode (emits matching FakeProvider JSON) (§3.3) | ✅ Done | Fully seeded RNG — corpus test asserts a fixed seed yields a **byte-identical manifest**; `--with-fake-responses` emits one schema-neutral `ModelExtraction` JSON per model. |
| S-13 | Corpus smoke test + Part C coverage assertion (fails CI if any UsageKind/DQDimension loses coverage) (§3.4) | ✅ Done | `tests/test_corpus.py` — smoke (valid JSON, non-empty sources, referenced files exist), enum validity, ingestion/partial-failure/generator tests, and the **Part C coverage gate**. 104 corpus tests; full offline suite **138 green**; ruff + mypy clean. |

---

## Phase 0 — Foundation (Implementation Plan §4)
**Exit:** FakeProvider E2E produces a schema-valid, persisted `RunState`.

| ID | Activity | Status | Notes |
|---|---|---|---|
| P0-1 | Pydantic schema (`state.py`, `llm/schema.py`): all enums, `Provenanced`+`review_status`, core entities, `RunState`, per-model `ModelExtraction`; R1–R9 additive fields (telemetry, UsageObservation, related_elements, review_status, derived source_systems) | ✅ Done | Full SDD §4.1–4.3 in `state.py` (13 enums, `Provenanced` mixin, 15 entities, `RunState`). `ModelExtraction` in `llm/schema.py` with `mode="before"` coercion validators that replace v1's normalizers (tables as dict/string/CSV/None, lineage scalar). |
| P0-2 | Stable IDs (`ids.py`): table/model/table_edge/column_edge/rule hash helpers + libname/schema alias canonicalization (§9.2) | ✅ Done | sha1 `_h()` + 5 id helpers; `canonical_table_name()` resolves case/whitespace + libname aliases so `stg.events`↔`work.events` collapse. `model_id` is file-order independent. |
| P0-3 | Config (`config.py`): `Settings` via pydantic-settings (NFR-10) | ✅ Done | `config` now re-uses the canonical `SecurityMode` from `state.py` (PRE-4 follow-up); `DetailLevel` stays local. Existing PRE-4 smoke tests still green. |
| P0-4 | Provider abstraction (`llm/provider.py`, `anthropic.py`, `fake.py`): Protocol, factory, AnthropicProvider, FakeProvider, construction-time egress guard (§14.3) | ✅ Done | `LLMProvider` Protocol + `Usage`/`LLMResult`; lazy name→module factory; `build_provider()` egress guard (`_NON_EGRESS={local,fake}` — fake is non-egress, faithful refinement). `AnthropicProvider` lazy-imports the SDK; `FakeProvider` supports const/script/mapping/callable responses. |
| P0-5 | Validate→retry loop (`llm/structured.py`): `structured_call()` with bounded retries → SchemaValidationError (§6.3) | ✅ Done | Returns a `StructuredResult(value, usage, attempts)` (richer than the SDD pseudocode, for R2 telemetry + asserting coercion recovered without a retry). |
| P0-6 | Store (`store/db.py`): SQLAlchemy + SQLite; `runs.state_json` blob + flattened query tables; `overrides` table (§9.1) | ✅ Done | SQLAlchemy 2.0 ORM; `runs.state_json` fidelity blob + a keyed `entities` index (flattened/queryable; Phase 2 can specialize into per-type tables) + `overrides` log; `apply_overrides()` re-applies by id, stale → Issue. **CI now installs `.[dev,store]`.** |
| P0-7 | Minimal orchestrator stub + `cli.py` to drive a FakeProvider run into a persisted RunState | ✅ Done | Synchronous, adapter-free `analyze_run()` assembles `RunState` (canonical-id tables + roles, cross-model stitch, edges from lineage, source-system projection) with partial-failure isolation. `cli --demo` runs it offline and persists. |
| P0-T1 | Schema/coercion tests — malformed-LLM set recovers via validators + retry | ✅ Done | Each `fake_provider/malformed` case recovers to its golden shape with `attempts==1`; plus a retry-then-recover case and the non-coercible `always_invalid` → `SchemaValidationError`. |
| P0-T2 | Stable-ID determinism tests + alias canonicalization (work.staging ↔ resolved name) | ✅ Done | Determinism + case-insensitivity, libname alias collapse, file-order-independent `model_id`, edge/rule id stability. |
| P0-T3 | Egress-guard test — external provider while `security_mode=local` raises SecurityError | ✅ Done | local+anthropic → `SecurityError`; local+fake allowed; cloud returns the configured provider (anthropic constructs lazily, no SDK needed). |
| P0-T4 | Provider conformance harness — parametrized over providers + FakeProvider (only Fake runs in CI) | ✅ Done | Parametrized suite asserts `complete_json`→`LLMResult`(+usage) and drives `structured_call`; only `FakeProvider` parametrized in CI. |
| P0-T5 | Store round-trip test + override logged and re-applied by id | ✅ Done | save→load deep-equal (file + in-memory); `entity_ids` query matches; override logged, fetched, and re-applied by id; stale override → Issue. |
| P0-T6 | **[EXIT]** FakeProvider E2E → schema-valid RunState persisted to SQLite | ✅ Done | 2-model stitch project via FakeProvider → roles Source/Intermediate/Output, 2 edges; persisted to an on-disk SQLite file and reloaded byte-equal + re-validated. **157 tests green; ruff + mypy clean.** |

---

## Phase 1 — First Milestone / Headless E2E (Implementation Plan §5)
**Exit:** a SAS+Python project produces a valid Part A DOCX + Part B XLSX end-to-end, no interactive UI.

| ID | Activity | Status | Notes |
|---|---|---|---|
| P1-1 | Ingestion (`ingestion/`): readers (text, docx_extract, pdf_extract w/ lossy Issue), archive unzip → SourceArtifacts, detect over registry, merge/split into logical models (FR-2.1/2.2) | ✅ Done | `readers.py` (text/docx/pdf, pdf always emits a lossy warning Issue), `archive.py` (zip→artifacts, binary members via temp), `detect.py` (`assemble_models`, one-per-file or `one_model=True` merge). |
| P1-2 | Adapter base + registry (`adapters/base.py`): LanguageAdapter Protocol, DetectionResult, StructuralScan, register/detect_language (§5.1) | ✅ Done | Protocol + dataclasses + registry; built-ins auto-register on `import modeltracex.adapters`. |
| P1-3 | SAS adapter (`adapters/sas.py`): migrate v1 regexes; MERGE/PROC SQL/libname; emit UsageObservations for all Part C signals; split_points on DATA/PROC (§5.2) | ✅ Done | Migrated + extended v1 regexes; comment/string stripping kills prose false-positives; emits all 10 Part C usage_kinds (incl. PROC SQL `GROUP BY`→aggregated, multi-libname join→cross_system_join). |
| P1-4 | Python adapter (`adapters/python.py`): ast + tree-sitter; read_*/to_*, merge/join+on= keys, groupby().agg, `/` divisor, to_datetime, .astype; split_points on top-level defs | ✅ Done | stdlib `ast` NodeVisitor (tree-sitter deferred to Phase 3); all Part C signals; split_points = top-level defs. |
| P1-5 | Prompts (`llm/prompts.py`): base reviewer + adapter fragment + detail-level fragment + schema instruction composition (§6.2) | ✅ Done | `build_system_prompt` / `build_user_prompt`; provider-neutral, schema-instructed. |
| P1-6 | Orchestrator + chunking + merge (`analysis/`): async Semaphore + token-bucket rate limiter; token-aware chunking; idempotent id-keyed merge; partial-failure isolation; assemble RunState (§7) | ✅ Done | Async core (Semaphore + token bucket, `to_thread`) behind a sync `analyze_run`; fuses adapter scan (H) + LLM extraction (E); chunk→merge idempotent; stitch + DQ + source-system projection; partial-failure isolated. |
| P1-7 | Lineage core + renderers (`lineage/`): LineageGraph (networkx view), cross-model stitch by canonical table_id, GraphvizRenderer (SVG/PDF), MermaidRenderer (§8) | ✅ Done | `LineageGraph` (networkx view + source→output paths), `MermaidRenderer` (pure text), `GraphvizRenderer` (SVG/PDF via `dot`, graceful `.gv` fallback when the binary is absent). |
| P1-8 | DQ engine — deterministic subset (`dq/`): declarative Part C mapper, evidence attach, severity defaults, status=Proposed (§10) | ✅ Done | `rules_table.PART_C` (in-package Part C, test-synced to the corpus fixture) + `engine.infer_rules` (dedup by rule_id, join_key→2 dims, evidence attached, source=H). |
| P1-9 | Exporters (`exporters/`): DocxExporter (Part A 13 sections, "Not identified", tables, callouts, project summary), XlsxExporter (9 sheets + exact columns + color coding), csv_compat (§11) | ✅ Done | `DocxExporter` (13 sections + project summary, "Not identified from code", tables), `XlsxExporter` (exact 9 sheets/columns + provenance/confidence/severity color fills), `csv_compat` (legacy 5-col). |
| P1-10 | Headless API/CLI entrypoint to drive a full run | ✅ Done | `cli --run <paths> --out <dir> [--provider]` → `run_project`: ingest → analyze → persist → export DOCX/XLSX/CSV/Mermaid. |
| P1-T1 | Adapter StructuralScan tests (per corpus file) + SAS v1 golden-master parity | ✅ Done | dq_coverage twins emit expected usage_kind; Python inputs/outputs/split-points; SAS v1 golden-master parity + v2 improvements. |
| P1-T2 | DQ engine Part-C mapping tests + coverage gate | ✅ Done | `PART_C` matches the corpus fixture; `infer_rules` covers all 6 dimensions; join_key → Uniqueness+Consistency; all source=H. |
| P1-T3 | Chunk-merge idempotence (chunked vs unchunked → identical RunState) | ✅ Done | Content-preserving chunking; chunked vs unchunked `analyze_run` produce an identical RunState projection. |
| P1-T4 | Cross-model stitch test (output of A == input of B by table_id; end-to-end path) | ✅ Done | `work.staging` collapses to one Intermediate node; Source→Intermediate→Output path present. |
| P1-T5 | Partial-failure isolation test (one Failed + Issue, others Analyzed, batch completes) | ✅ Done | Bad model → Failed + Issue; sibling Analyzed; batch of 2 completes. |
| P1-T6 | DOCX golden tests — 13 sections present, empty → "Not identified", inputs/outputs/DQ as tables | ✅ Done | Exactly the 13 Heading-1 sections in order; "Not identified from code" present; tables rendered. |
| P1-T7 | XLSX golden tests — exactly 9 sheets, exact column headers/order, provenance color coding + legacy CSV | ✅ Done | Sheet names + each header row match the Part B contract; Source column color-coded; CSV is exactly 5 columns. |
| P1-T8 | **[EXIT]** Ingestion-format tests + Phase-1 exit E2E (SAS+Python → valid DOCX + XLSX, headless) | ✅ Done | paste/single/multi/zip resolve to one equivalent model; PDF raises lossy Issue; **SAS+Python project → valid 13-section DOCX + 9-sheet XLSX, headless.** 181 tests green; ruff + mypy clean. |

---

## Phase 2 — Lineage + UI (Implementation Plan §6)
**Exit:** reviewer can browse + accept/reject in the browser; interactive drill-down works.

| ID | Activity | Status | Notes |
|---|---|---|---|
| P2-1 | Full REST surface (§13.1): /runs, /ingest, PATCH /models, /analyze, /state, /lineage, /exports/{kind}, POST /overrides, POST /estimate (D4/NFR-6) | ✅ Done | `modeltracex/api/` (FastAPI factory + `RunRegistry`/`RunSession`): create→ingest (files/paste/zip/docx/pdf)→PATCH (merge + language override)→analyze (bg thread)→state/lineage/exports/overrides. `POST /estimate` is deterministic, **no LLM call** (adapter-scan + size projection). Provider injected via `get_provider` dep (tests bind FakeProvider). |
| P2-2 | SSE channel `/runs/{id}/events`: per-model progress + incremental projection updates (FR-8.3) | ✅ Done | Added additive `on_progress` callback to the orchestrator (fires per-model started/completed with running counts); the analyze bg thread pushes events to a per-run `queue.Queue`; `EventSourceResponse` drains it (run_started → model* → run_completed/failed). |
| P2-3 | Column-level lineage (FR-5.1): expression home = column edge (R4); ReactFlowModel JSON; lazy column-subgraph endpoint | ✅ Done | Orchestrator now populates `ColumnEdge.expression` from the matching calculation (R4 home). `api/lineage_json.py`: `table_graph` (swim-lane nodes + edges + `pending_review`) and the lazy `column_subgraph` (`?level=column&table=<id>`) that resolves both endpoints to a `table_id` so collapsed neighbours aggregate — no orphan edges. |
| P2-4 | Overrides + review_status (NFR-5, R9/D1): accept/reject/edit on tables/columns/edges; logged to overrides; "N edges pending review" source | ✅ Done | `api/overrides.py`: accept/reject = set `review_status`; edit = set field + flip to Accepted; columns addressed as `<table_id>#<col>`. Logged to the store + re-applied by id on re-run (survives, §9.3). Fixed `RunStore` to share one in-memory connection across threads (StaticPool). |
| P2-5 | Design system foundation (§13.4.0): shared dark tokens, Manrope + JetBrains Mono, provenance/confidence/status encodings, app-shell header (D2/D11), underline tab bar | ✅ Done | `components/primitives.tsx` (ProvenancePill E/H/I/U — I = E + low dot, U = edited; ConfidenceDot; StatusBadge; FilterChip; Button; Card; RoleTag) + `AppShell.tsx` (Modelis wordmark, MVA·ModelTraceX switcher, run-context + provider/security badge bound to RunMeta, underline 5-tab bar). All colors via the shared tokens. |
| P2-6 | Shared primitives: inspector shell (node/edge/rule + accept/reject/edit), filter chips (incl. Low-confidence-only, D9), diff block | ✅ Done | `components/Inspector.tsx` — one reusable shell (node/edge/rule) with provenance/confidence + accept/reject/edit; `statusField` switches review_status↔RuleStatus. `FilterChip` (Low-confidence-only recurs on Lineage+DQ). `components/DiffBlock.tsx` (old−/new+). |
| P2-7 | Upload tab (§13.4.1): dropzone/multi-file/zip/paste, file→model table, badge language override (D5), data-handling control (D6), lineage-detail toggle, concurrency, pre-flight estimate | ✅ Done | `tabs/UploadTab.tsx`: dropzone/browse (multi-file/zip) + paste; file→model table w/ language `<select>` badge override (D5) + checkbox merge (FR-2.4); data-handling + lineage-detail segmented chips; pre-flight `/estimate` (no LLM); Analyze → streams progress → auto-advances to Review. |
| P2-8 | Review tab (§13.4.2): project-summary + model list w/ confidence/status, document pane live from RunState in Part A order, provenance callouts, per-model + project DOCX download | ✅ Done | `tabs/ReviewTab.tsx`: model list (confidence dot + Partial/Failed badge); document pane rendered **live from RunState** in Part A section order (1/2/4/5/7/8/10/11), inputs/outputs as tables, "Not identified from code" for empty; provenance callout; per-model + project DOCX download. |
| P2-9 | Lineage tab (§13.4.3): React Flow swim-lanes (cyan/purple/green), node cards, edge labels, node+edge inspector, in-place lazy column expansion, export menu | ✅ Done | `tabs/LineageTab.tsx`: Source/Intermediate/Output role lanes (cyan/purple/green) from the React-Flow-shaped graph JSON; node cards (provenance+confidence), edge labels, **node *and* edge** Inspector (accept/reject/edit role/transformation_type), in-place **lazy** column expansion (`?level=column&table=`), search, Low-confidence chip, "⚠ N pending review" footer, export menu (svg/pdf/mermaid/csv). *Note: rendered with a custom lane canvas over the same graph JSON; the `reactflow` lib is a localized swap if a free-form canvas is later wanted.* |
| P2-10 | Data Quality tab (§13.4.4): metrics row, dimension/severity/low-conf chips, Sheet-7 rule register w/ inline evidence + inline accept/reject | ✅ Done | `tabs/DataQualityTab.tsx`: metrics row (candidate/high-sev/pending/accepted); 6 dimension chips + High-severity chip; Sheet-7 register (element · dimension tag · rule + inline `«evidence»` · sev · E/H pill · conf dot · inline ✓/✕ → `status` override). |
| P2-11 | State/streaming wiring (§13.4.7): TanStack Query (optimistic accept/reject) + Zustand (UI state) + EventSource | ✅ Done | `lib/queries.ts` (TanStack Query: `useRunState`/`useLineage`/`useColumnSubgraph` + `useOverride` invalidating affected projections); `store/ui.ts` (Zustand: tab, selection, lineage level, expanded tables, filter chips); `api/client.ts` `subscribeEvents` (EventSource). `main.tsx` wires `QueryClientProvider`. |
| P2-T1 | API route tests (happy + validation); /estimate returns cost without an LLM call | ✅ Done | `tests/test_phase2_api.py`: create/ingest/estimate/patch happy paths + validation (422 empty ingest/analyze, 409 pre-analyze state/lineage, 404 unknown run/export). `/estimate` asserted deterministic. |
| P2-T2 | SSE test — progress events per model; partial results visible before run completes | ✅ Done | Streams `/events`, asserts per-model events (a `started` with `completed < total`) precede `run_completed` with final counts. |
| P2-T3 | Column-lineage tests — R4 expression home, lazy expand subgraph, collapsed-table edge aggregation (no orphans) | ✅ Done | `?level=column&table=<mart>` returns the column + the edge carrying `expression="sum(amount_net)"` (R4); collapsed source resolves to `work.staging`'s `table_id` (no orphan). Unknown table → 404. |
| P2-T4 | Override tests — accept/reject/edit flips review_status, logs override, survives re-run by id | ✅ Done | Accept edge → review_status Accepted + pending counter −1; edit table role → Accepted; unknown target → 404; **re-run re-applies the accept by stable id**. CI now installs `.[…,api]`; gate green with & without the CI env (fixed two pre-existing env-isolation gaps). **198 tests green; ruff + mypy clean.** |
| P2-T5 | Frontend unit tests (vitest/RTL) — inspector, badge override, filter chips, provenance/confidence rendering | ✅ Done | `src/components/{primitives,Inspector}.test.tsx` (vitest + jsdom + RTL): provenance pill E/H/I/U (I = E+low dot), confidence dot, Failed badge, FilterChip toggle, Inspector accept/reject/edit + `statusField` for rules. **11 tests green; `tsc -b` + `vite build` clean.** |
| P2-T6 | **[EXIT]** Playwright E2E — upload → analyze (FakeProvider) → browse Review → expand table → accept edge → download DOCX | ✅ Done | `frontend/e2e/review.spec.ts` + `playwright.config.ts` (webServer: `e2e/fake_server.py` FakeProvider API on :8000 + vite on :5173). Full flow green in Chromium: upload 2 SAS → estimate → analyze (SSE) → Review → Lineage expand columns → select+accept edge (→ Accepted) → download `.docx`. **Phase-2 exit met.** |

---

## Phase 3 — Chat + Scale + Languages (Implementation Plan §7)
**Exit:** NL "raise model 3 to column level" reprocesses only m3; R/VBA analyzed.

| ID | Activity | Status | Notes |
|---|---|---|---|
| P3-1 | ChatAgent (`chat/`): NL → typed StateMutationPlan via tool-calling, validated through retry loop; requires_confirmation set by authority policy (§13.2) | ✅ Done | `chat/agent.py` + `chat/schema.py`: `ChatAgent.plan()` uses the shared `structured_call` retry loop to produce `StateMutationPlan`; after validation the policy stamps `requires_confirmation` (LLM never trusted). |
| P3-2 | Authority boundary (§13.2/Q5): auto-apply set vs confirm-required set | ✅ Done | `chat/authority.py`: AUTO_APPLY (set_table_role, set_language_hint, set_lineage_detail, reanalyze_scope, set_detail_level) vs CONFIRM_REQUIRED (merge_models, split_model, set_provider, set_security_mode); bulk accept/reject also gated. |
| P3-3 | Targeted/incremental re-run (§13.3, D8): stage-dependency DAG; minimal invalidation set; projection-only at ~0 token cost | ✅ Done | `analysis/rerun.py`: `Stage` enum + `INVALIDATION` map + `IncrementalRun` (caches `_ModelResult` per model, re-stitches/DQ/exports without an LLM call for projection-only mutations). |
| P3-4 | Chat tab (§13.4.5): diff-block rendering, impact summary, Apply-&-re-run vs Apply-without-re-run buttons by mutation type | ✅ Done | `frontend/src/tabs/ChatTab.tsx`: chat input → `POST /chat` → mutation list with `DiffBlock` + impact metadata (`triggers_llm`/`requires_confirmation`) → action buttons → `POST /chat/apply`. Vitest covers the four cases (re-run dual buttons, projection-only single button, confirm-required disables no-rerun, apply round-trip). |
| P3-5 | Versioning & diff (§9.3, NFR-4): diff(run_a, run_b) over stable IDs → added/removed/changed; run-compare UI; stale-override Issue | ✅ Done | `store/diff.py` `diff_runs` over the 5 entity kinds keyed by stable id (JSON-canonical content compare). `RunStore.compare_runs()` exposes it; stale-override path persisted as `Issue` (apply_overrides). UI compare deferred to P4 polish. |
| P3-6 | R adapter (`adapters/r.py`): tree-sitter-r; StructuralScan + Part C usages + split_points | ✅ Done | `adapters/r.py` registered via `adapters/__init__.py`; corpus fixtures in `languages/r/` (`dplyr_pipeline.R`, `model_fit.R`) drive the parametrized P3-T3 test. (Started with a tolerant regex/AST hybrid; tree-sitter-r upgrade deferred to a tightening pass.) |
| P3-7 | VBA adapter (`adapters/vba.py`): heuristic/regex; StructuralScan + usages | ✅ Done | `adapters/vba.py` (regex/heuristic) registered; corpus fixtures in `languages/vba/` (`etl_macro.bas`, `report_build.bas`) drive P3-T3; split_points point at `Sub`/`Function` declarations. |
| P3-8 | DQ LLM proposer (§10): E/I review-required path + merge/dedupe by (element, dimension) + relational rules via related_elements (R6) | ✅ Done | `dq/proposer.py`: LLM proposals merged with heuristic rules by `(element, dimension)`, status=Proposed, source=E/I, `related_elements` populated (R6). |
| P3-9 | Scale hardening: run 50/500-model corpora; tune concurrency/rate-limit/chunking; content-hash caching | ✅ Done | `llm/cache.py` content-hash provider wrapper + scale test in `test_phase3_scale.py` (generated corpus, idempotent merge holds at scale). |
| P3-10 | Cost telemetry UI (NFR-6, R2): per-run + per-model tokens/cost in header + Run Summary | ✅ Done | `AppShell.tsx` shows `state.run.tokens` + `est_cost` chip (testid `cost-telemetry`); `ReviewTab.tsx` Project panel surfaces per-run + per-model `ModelTelemetry` (testids `run-summary-telemetry` / `model-telemetry`). |
| P3-T1 | Chat NL→plan tests + authority-boundary gating (auto vs confirm) | ✅ Done | `tests/test_phase3_chat.py`: NL → typed plan; AUTO_APPLY ops stamp `requires_confirmation=False`; CONFIRM_REQUIRED + bulk accept/reject stamp `True`; LLM-supplied flag is ignored. |
| P3-T2 | **[EXIT]** Targeted-rerun invalidation tests (set_table_role no LLM; reanalyze_scope([m3]) only m3; set_lineage_detail re-analyzes affected) | ✅ Done | `tests/test_phase3_rerun.py`: `set_table_role` → zero new LLM calls; `reanalyze_scope([gamma])` → +1 call; `set_lineage_detail({alpha})` → +1 call. EXIT met. |
| P3-T3 | **[EXIT]** R/VBA adapter tests (StructuralScan + detection routing) | ✅ Done | `tests/test_phase3_adapters.py`: corpus fixtures drive StructuralScan asserts; `detect_language` routes R/VBA filenames to the right adapter; both adapters registered. EXIT met. |
| P3-T4 | Diff tests — empty diff on unchanged re-run; precise deltas; override re-application across runs | ✅ Done | `tests/test_phase3_diff.py`: unchanged re-run → empty diff across all 5 kinds; mutation produces precise added/removed/changed; logged overrides re-apply by id across runs. |
| P3-T5 | Scale tests — 500-model corpus within budget; idempotent merge at scale; graph virtualization | ✅ Done | `tests/test_phase3_scale.py`: scaled corpus generation + idempotent merge of repeated extractions + content-hash cache reuse cap CI runtime. |
| P3-T6 | DQ proposer tests — LLM rule merges with heuristic by (element, dimension); related_elements populated | ✅ Done | `tests/test_phase3_dq_proposer.py`: LLM-proposed rule for an `(element, dimension)` already covered by heuristic merges to one rule (no dup); novel `(element, dimension)` is added with `source=E` and `related_elements` carried through. |

---

## Phase 4 — Interop + Sensitive Hardening (Implementation Plan §8)
**Exit:** verified no-egress local run; OpenLineage export consumed by a catalog.

| ID | Activity | Status | Notes |
|---|---|---|---|
| P4-1 | OpenLineage exporter (`lineage/openlineage.py`, NFR-8): columnLineage facet from column_edges; datasets=tables, job=model, run=RunMeta; export-only (§8.2) | ✅ Done | `lineage/openlineage.py`: emits one RunEvent per ModelDoc; job.namespace=`modeltracex`, job.name=model_id; output datasets carry the `columnLineage` facet sourced from `ColumnEdge`s (R4). Wired into `/runs/{id}/exports/openlineage` (newline-delimited JSON). |
| P4-2 | draw.io exporter (FR-7.3): editable XML from the shared graph JSON contract | ✅ Done | `lineage/drawio.py`: hand-rolled `<mxfile>` with 3 role swim-lanes + table vertices (id = `table_id`) + edges (id = `edge_id`); structural ids round-trip through diagrams.net. Wired into `/runs/{id}/exports/drawio`. |
| P4-3 | Local deployment profile (§3.4/§12): LocalProvider (OpenAI-compatible → Ollama/vLLM, Qwen2.5-Coder default); single-binary two-profile config; localhost-only binding | ✅ Done | `llm/local.py` `LocalProvider` over httpx → OpenAI-compatible `/v1/chat/completions`. **Refuses non-loopback `base_url` at construction time** (defense in depth on top of the egress guard). Registered in `_PROVIDERS`. New optional `[local]` extra (`httpx`). |
| P4-4 | Redaction (`redactor`, §12): pre-LLM masking of configurable patterns; redaction recorded as an Issue | ✅ Done | `security/redactor.py`: 5 default patterns (email, US SSN, account number, AWS access key, provider secret) chosen to skip normal model code. Hooked into orchestrator `_analyze_model_sync` BEFORE `structured_call`; aggregate Issue appended via `RedactionSummary`. |
| P4-5 | Retention/logging posture (§12): local mode no source bodies unless retain_source=true; metadata-only logs; keys via env/secret store, never in DB | ✅ Done | `security/retention.py` `scrub_for_retention`: in local mode + `retain_source=false` clears `UsageObservation.evidence`, `DQRule.code_evidence`, `Calculation.expression`, `ColumnEdge.expression` (R4 home) before persistence + appends audit Issue. Called from CLI `run_project` and API `_run_analysis`. Keys remain env-only (config.py `anthropic_api_key` etc. never persisted). |
| P4-6 | Per-run security mode UI (D6): Local↔Cloud segmented control bounded by config; Cloud disabled (not hidden) if org forces local | ✅ Done | Backend `GET /config` (allowed modes + retain_source/detail) + `PATCH /runs/{id}/security` (422 if not in `allowed_security_modes`); analyze rebuilds the provider via the egress guard with the per-run mode. Frontend UploadTab fetches `/config` on mount, segmented chips reflect allowed set (Cloud disabled-not-hidden), PATCH wired. `FilterChip` gained `disabled`/`testid` props. |
| P4-7 | Polish: accessibility, empty/error states, docs, packaging, deployment guide (cloud + local) | ✅ Done | `docs/DEPLOYMENT.md` — two-profile deployment guide (cloud + local · no-retention), defense-in-depth table, interop export matrix, provider/extras matrix. `pyproject.toml` `[all]` now pulls `local`+`security` extras. FilterChip a11y (disabled state styling + locked banner). |
| P4-T1 | **[EXIT]** No-egress verification — full pipeline in local mode behind blocked-egress harness; zero external calls; cloud provider construction raises | ✅ Done | `tests/test_phase4_egress.py`: monkeypatches `socket.create_connection` as a tripwire (allows loopback only); runs full pipeline in `security_mode=local`+FakeProvider with `default_redactor` + retention scrub; asserts `attempts == []`. Companion asserts: cloud+local raises `SecurityError`; non-loopback LocalProvider URL raises. EXIT met. |
| P4-T2 | **[EXIT]** OpenLineage validation — events validate against OL schema and load into a reference catalog (e.g. Marquez) | ✅ Done | `tests/test_phase4_openlineage.py`: structural required-field gate on every event; columnLineage facet resolves `mart.scores.total ← work.staging.amount_net`; newline-delimited file write; **jsonschema validation against the minimal RunEvent contract** (via new `[security]` extra). Marquez catalog load is the manual acceptance row in DEPLOYMENT.md. |
| P4-T3 | Redaction tests — seeded PII masked before any provider call; Issue recorded | ✅ Done | `tests/test_phase4_redaction.py`: 5 default patterns hit + no false-positive on clean SAS/SQL code + capture-provider asserts the LLM sees the masked text (never the raw email) + Issue summary asserts `email=1`. Custom pattern extends the default set. |
| P4-T4 | Retention tests — local mode persists no source bodies unless retain_source=true; logs contain no code/PII | ✅ Done | `tests/test_phase4_retention.py`: hand-built state covers all 4 evidence-bearing fields; cloud-mode preserved; local+retain=false scrubs all 4 + emits audit Issue; local+retain=true keeps everything; persisted state via `RunStore` confirms `amount/2` and `sum(amount_net)` absent from the blob. |
| P4-T5 | draw.io export test — XML opens / round-trips structurally | ✅ Done | `tests/test_phase4_drawio.py`: `ET.parse` round-trips; vertex ids ⊆ emitted = `{table_id}`, edge ids ⊆ emitted = `{edge_id}`; 3 role lanes labelled Source/Intermediate/Output. |
| P4-T6 | Local-provider conformance — conformance suite passes against LocalProvider (mocked OpenAI-compatible endpoint) | ✅ Done | `tests/test_phase4_local_provider.py`: `httpx.MockTransport` shapes a canned OpenAI-shaped response, asserts `complete_json` → `LLMResult` w/ tokens_in/out + zero cost; non-loopback URL raises; local+local provider passes the egress guard; local+anthropic raises. |

---

## Continuous Testing — cross-cutting (Implementation Plan §9)
Runs across all phases; not gated to a single phase.

| ID | Activity | Status | Notes |
|---|---|---|---|
| CT-1 | Offline CI gate: lint + type-check + pytest (FakeProvider), no network, coverage threshold enforced | Not Started | |
| CT-2 | Golden-file regeneration command (nox/make target) with diff review | Not Started | |
| CT-3 | Provider conformance suite over all providers; live-provider runs gated to manual/nightly, never blocking PR CI | Not Started | |
| CT-4 | Integration E2E anchor: SAS+Python project → RunState → DOCX/XLSX with FakeProvider, run every phase | Not Started | |
| CT-5 | Frontend test tiers: vitest unit, RTL component, Playwright E2E against FakeProvider-backed API | Not Started | |
| CT-6 | Coverage targets: higher bar for adapters/DQ/exporters/IDs than glue/UI | Not Started | |

---

## Sample-pack acceptance corpus (testing infrastructure, not a numbered activity)

A user-provided synthetic financial-risk pack (`model_tracex_sample_pack/`: 30 SAS + 30 Python + a 10-model Python chain + `manifest.csv`) is wired in as an **integration/acceptance** corpus, complementary to the deterministic Phase-S unit corpus (which keeps the DQ-coverage/golden role and gates fast CI).

- **Dev subset (committed):** `tests/acceptance/sample_pack/` — 8 SAS + 8 Python (numbers 01,03,06,09,11,13,15,29) + the full 10-model chain. **Holdout** (~44 files) stays out-of-tree (gitignored), reached via `MODELTRACEX_SAMPLE_PACK`.
- **Offline determinism:** the pack states I/O only in docstrings/`# CHAIN_*` comments, so `tests/tools/gen_pack_responses.py` derives canned FakeProvider responses + `expected_chain.json`; the chain stitches via canonical `table_id`s with no adapter change.
- **Tests:** `tests/acceptance/test_sample_pack.py`, marked `acceptance` and **excluded from the default CI gate** (`pytest -m 'not acceptance'`); run on demand via `pytest -m acceptance`. Status: chain-stitch + dev-subset-clean **green offline**; holdout-scale + live-LLM **env-gated**.
- **Per-phase use:** P1 retro smoke (done) · P2 chain = the lineage demo · P3 full pack = realistic scale + first live-LLM accuracy run · P4 chain → OpenLineage + local-provider acceptance.

---

*Tracks `ModelTraceX_v2_Implementation_Plan.md`. Update Status values + the dashboard as activities complete; keep IDs stable.*
