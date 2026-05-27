# ModelTraceX v2

Multi-language (SAS · Python · R · VBA) **model-code reviewer** that extracts a governance-grade
**model document**, a **data-lineage workbook**, **DQ rules**, and **lineage diagrams** — all as pure
projections of a single validated canonical state (`RunState`).

> v2 is a ground-up rewrite of the v1 single-module `ModelTraceX.py` (kept read-only for reference under
> [`reference/v1/`](./reference/v1/), see [docs/MIGRATION_v1_to_v2.md](./docs/MIGRATION_v1_to_v2.md)).

## Documents

| Doc | Purpose |
|---|---|
| [`ModelTraceX_v2_SDD.md`](./ModelTraceX_v2_SDD.md) | Software Design Document (source of truth for architecture). |
| [`ModelTraceX_v2_Requirements.md`](./ModelTraceX_v2_Requirements.md) | FR/NFR requirements. |
| [`ModelTraceX_v2_Document_and_Lineage_Spec.md`](./ModelTraceX_v2_Document_and_Lineage_Spec.md) | DOCX/XLSX output + canonical-state spec. |
| [`ModelTraceX_v2_Implementation_Plan.md`](./ModelTraceX_v2_Implementation_Plan.md) | Phased build plan (what/how). |
| [`ModelTraceX_v2_Project_Plan.md`](./ModelTraceX_v2_Project_Plan.md) | Activity-wise status tracker (progress). |

## Repository layout

```
modeltracex/        # Python core package (SDD §20) — scaffold stubs, filled in per phase
frontend/           # React + Vite + TS UI scaffold (shared MVA dark design system) — wired in Phase 2
tests/              # pytest suite; synthetic-data corpus lands in Phase S under tests/fixtures/
docs/               # migration + design notes
reference/v1/       # read-only v1 source, for migration reference
.github/workflows/  # CI (lint → type-check → offline pytest → coverage)
```

## Development setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows (PowerShell: .venv\Scripts\Activate.ps1)
pip install -e ".[dev]"          # core + dev tools; add ,llm,api,export,... as phases need them
cp .env.example .env             # then fill in provider keys (cloud) or leave blank (local/fake)
```

## Checks

```bash
ruff check .          # lint
ruff format --check . # format
mypy modeltracex      # types
pytest                # tests (offline; FakeProvider — no external LLM calls)
```

## Build status

Tracked in [`ModelTraceX_v2_Project_Plan.md`](./ModelTraceX_v2_Project_Plan.md). Current: **Pre-Phase 0 (Bootstrap)**.
