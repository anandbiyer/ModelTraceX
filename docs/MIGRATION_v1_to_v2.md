# Migration: v1 → v2 (PRE-5)

v1 (`ModelTraceX.py`, single module) is a **rewrite target**, not a base to extend. Concepts
migrate; code does not. This note records the disposition of every v1 element (SDD §14) and the
retirement policy.

## Retirement policy
- The v1 source is preserved **read-only** under [`reference/v1/`](../reference/v1/) and remains
  recoverable from git history (it was deleted from the repo root and staged for removal at the
  start of the v2 build).
- It is kept until the **Phase-1 SAS adapter reaches parity** with v1's heuristics (verified by the
  v1 SAS golden-master, Phase S activity **S-9**). After that it may be deleted.
- Nothing in `reference/v1/` is imported by the `modeltracex` package or shipped.

## Element-by-element disposition (SDD §14)

| v1 element | v2 disposition | Lands in |
|---|---|---|
| `_normalize_tables`, `_norm_lines`, `_normalize_lineage_rows` | → Pydantic validators + validate/retry loop (`llm/structured.py`) | Phase 0 (P0-5) |
| `SAS_*_REGEX`, `heuristic_scan_tables` | → `adapters/sas.py` structural scanner; expanded for MERGE/PROC SQL/libname + `UsageObservation`s | Phase 1 (P1-3) |
| `draw_lineage_clustered` (Graphviz PNG swim-lanes) | → `lineage/render_graphviz.py` (SVG/PDF), role lanes | Phase 1 (P1-7) |
| `write_lineage_csv` | → `exporters/csv_compat.py` (legacy 5-col compatibility) | Phase 1 (P1-9) |
| `write_model_review_txt` | **Retired** — superseded by the DOCX projection (Part A) | Phase 1 (P1-9) |
| `launch_ui` (Gradio), CLI loop, `range(1,6)` 5-model cap | **Retired** — replaced by FastAPI + React; cap removed (FR-3.1) | Phases 1–2 |
| `llm_analyze_single_model`, `llm_synthesize_lineage`, hard-coded `OpenAI()` | → provider abstraction (`llm/`) + orchestrator (`analysis/`) + prompt fragments | Phases 0–1 |

## What carries forward conceptually
- The **SAS regex heuristics** and **Graphviz swim-lane** idea (now role-based, SVG/PDF).
- The **defensive-normalizer instinct** — but expressed declaratively as Pydantic coercion + a
  bounded retry loop instead of hand-written coercion functions.
