"""Orchestrator — assemble a ``RunState`` from a project (SDD §7).

Per model: run the deterministic adapter ``scan`` (heuristic facts + Part C usage
signals), token-aware ``chunk`` the source on the adapter's split points, run the
LLM ``structured_call`` per chunk, and ``merge`` the chunks idempotently. Then,
across models: stitch tables by canonical ``table_id``, infer DQ rules from the
heuristic usages, and project source systems.

Concurrency is bounded by a ``Semaphore`` with a token-bucket rate limiter in
front of the provider (FR-3.2). The public entry point ``analyze_run`` is
synchronous (drives the async core via ``asyncio.run``) so callers and Phase-0
tests need no event loop. Partial-failure is isolated (NFR-7): a model whose
extraction never validates is kept heuristic-only and marked ``Failed``/``Partial``
with an ``Issue``; the batch completes.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from modeltracex import ids
from modeltracex.adapters.base import ADAPTERS, StructuralScan
from modeltracex.analysis.chunking import chunk_code, estimate_tokens
from modeltracex.analysis.merge import merge_extractions
from modeltracex.config import DetailLevel
from modeltracex.dq.engine import infer_rules
from modeltracex.llm.prompts import build_system_prompt, build_user_prompt
from modeltracex.llm.provider import LLMProvider, Usage
from modeltracex.llm.schema import ModelExtraction
from modeltracex.llm.structured import SchemaValidationError, structured_call
from modeltracex.state import (
    Calculation,
    Column,
    ColumnEdge,
    Confidence,
    Issue,
    Language,
    ModelDoc,
    ModelStatus,
    ModelTelemetry,
    Provenance,
    RunMeta,
    RunState,
    SourceSystem,
    Table,
    TableEdge,
    TableRole,
    TransformationType,
)

_MAX_CHUNK_TOKENS = 6000


@dataclass
class ModelInput:
    label: str
    language: Language
    source_files: list[str] = field(default_factory=list)
    code: str = ""
    libnames: dict[str, str] = field(default_factory=dict)


@dataclass
class _ModelResult:
    mi: ModelInput
    model_ref: str
    scan: StructuralScan
    extraction: ModelExtraction | None
    usage: Usage
    status: ModelStatus
    issues: list[Issue]


# --------------------------------------------------------------------------- #
# Rate limiting (token bucket; starts full so a small batch never sleeps)
# --------------------------------------------------------------------------- #
class _TokenBucket:
    def __init__(self, requests_per_minute: int, tokens_per_minute: int) -> None:
        self._req_cap = float(requests_per_minute)
        self._tok_cap = float(tokens_per_minute)
        self._req = self._req_cap
        self._tok = self._tok_cap
        self._rate_req = requests_per_minute / 60.0
        self._rate_tok = tokens_per_minute / 60.0
        self._ts = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, requests: int, tokens: int) -> None:
        async with self._lock:
            while True:
                now = time.monotonic()
                elapsed = now - self._ts
                self._ts = now
                self._req = min(self._req_cap, self._req + elapsed * self._rate_req)
                self._tok = min(self._tok_cap, self._tok + elapsed * self._rate_tok)
                if self._req >= requests and self._tok >= tokens:
                    self._req -= requests
                    self._tok -= tokens
                    return
                await asyncio.sleep(0.01)


def _new_run_id() -> str:
    return f"run_{int(datetime.now(tz=UTC).timestamp())}_{uuid.uuid4().hex[:8]}"


def _add(a: Usage, b: Usage) -> Usage:
    return Usage(
        tokens_in=a.tokens_in + b.tokens_in,
        tokens_out=a.tokens_out + b.tokens_out,
        est_cost=a.est_cost + b.est_cost,
    )


# --------------------------------------------------------------------------- #
# Per-model analysis (runs in a worker thread; provider calls are synchronous)
# --------------------------------------------------------------------------- #
def _analyze_model_sync(
    provider: LLMProvider, mi: ModelInput, detail_level: DetailLevel, max_chunk_tokens: int
) -> _ModelResult:
    model_ref = ids.model_id(mi.label, mi.source_files)
    adapter = ADAPTERS.get(mi.language)
    scan = adapter.scan(mi.code, model_ref) if adapter and mi.code.strip() else StructuralScan()
    fragment = adapter.prompt_fragment() if adapter else ""
    system = build_system_prompt(fragment, detail_level)

    chunks = chunk_code(mi.code, scan.split_points, max_chunk_tokens) if mi.code.strip() else [""]
    parts: list[ModelExtraction] = []
    usage = Usage()
    issues: list[Issue] = []
    failures = 0
    for chunk in chunks:
        user = build_user_prompt(mi.label, mi.language.value, scan.libnames, chunk)
        try:
            result = structured_call(provider, system, user, ModelExtraction)
        except SchemaValidationError as exc:
            failures += 1
            issues.append(
                Issue(
                    model_id=model_ref,
                    severity="error",
                    message=f"chunk extraction failed schema validation after retries: {exc}",
                )
            )
            continue
        parts.append(result.value)
        usage = _add(usage, result.usage)

    if not parts:
        status = ModelStatus.FAILED
        extraction = None
    else:
        extraction = merge_extractions(parts)
        status = ModelStatus.PARTIAL if failures else ModelStatus.ANALYZED
    return _ModelResult(mi, model_ref, scan, extraction, usage, status, issues)


async def _analyze_async(
    provider: LLMProvider,
    inputs: list[ModelInput],
    detail_level: DetailLevel,
    max_concurrency: int,
    requests_per_minute: int,
    tokens_per_minute: int,
    max_chunk_tokens: int,
) -> list[_ModelResult]:
    sem = asyncio.Semaphore(max_concurrency)
    limiter = _TokenBucket(requests_per_minute, tokens_per_minute)

    async def run(mi: ModelInput) -> _ModelResult:
        async with sem:
            await limiter.acquire(1, estimate_tokens(mi.code))
            return await asyncio.to_thread(
                _analyze_model_sync, provider, mi, detail_level, max_chunk_tokens
            )

    return list(await asyncio.gather(*(run(mi) for mi in inputs)))


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def analyze_run(
    provider: LLMProvider,
    inputs: list[ModelInput],
    *,
    tool_version: str = "2.0.0-dev",
    run_id: str | None = None,
    detail_level: DetailLevel = DetailLevel.TABLE,
    max_concurrency: int = 8,
    requests_per_minute: int = 6000,
    tokens_per_minute: int = 100_000_000,
    max_chunk_tokens: int = _MAX_CHUNK_TOKENS,
) -> RunState:
    results = asyncio.run(
        _analyze_async(
            provider,
            inputs,
            detail_level,
            max_concurrency,
            requests_per_minute,
            tokens_per_minute,
            max_chunk_tokens,
        )
    )

    run = RunMeta(
        run_id=run_id or _new_run_id(),
        timestamp=datetime.now(tz=UTC).isoformat(),
        tool_version=tool_version,
        llm_provider=getattr(provider, "name", "unknown"),
        llm_model=getattr(provider, "model", "unknown"),
    )
    state = RunState(run=run)

    for r in results:
        ext = r.extraction
        state.run.tokens += r.usage.tokens_in + r.usage.tokens_out
        state.run.est_cost += r.usage.est_cost
        state.issues.extend(r.issues)
        state.models.append(
            ModelDoc(
                model_id=r.model_ref,
                label=r.mi.label,
                language=r.mi.language,
                source_files=r.mi.source_files,
                purpose=ext.purpose if ext else "",
                executive_summary=ext.executive_summary if ext else "",
                assumptions=ext.assumptions if ext else [],
                methodology_steps=ext.methodology_steps if ext else [],
                limitations=ext.limitations if ext else [],
                calculations=[
                    Calculation(
                        target=c.target, expression=c.expression, source=Provenance.EXTRACTED
                    )
                    for c in (ext.calculations if ext else [])
                ],
                status=r.status,
                confidence=Confidence.HIGH if r.status is ModelStatus.ANALYZED else Confidence.LOW,
                telemetry=ModelTelemetry(
                    tokens_in=r.usage.tokens_in,
                    tokens_out=r.usage.tokens_out,
                    est_cost=r.usage.est_cost,
                ),
            )
        )

    _assemble_lineage(state, results)
    state.usage_observations = [u for r in results for u in r.scan.usages]
    state.dq_rules = infer_rules(state.usage_observations)
    _derive_source_systems(state)
    return state


def _refs(result: _ModelResult, *, output: bool) -> list[tuple[str, list[str], Provenance]]:
    libs = result.scan.libnames
    refs: list[tuple[str, list[str], Provenance]] = []
    seen: set[str] = set()
    ext_tables = (
        (result.extraction.output_tables if output else result.extraction.input_tables)
        if result.extraction
        else []
    )
    for t in ext_tables:
        canon = ids.canonical_table_name(t.name, libs)
        seen.add(canon)
        refs.append((t.name, list(t.columns), Provenance.EXTRACTED))
    for name in result.scan.outputs if output else result.scan.inputs:
        if ids.canonical_table_name(name, libs) not in seen:
            refs.append((name, [], Provenance.HEURISTIC))
    return refs


def _assemble_lineage(state: RunState, results: list[_ModelResult]) -> None:
    produced: set[str] = set()
    consumed: set[str] = set()
    for r in results:
        libs = r.scan.libnames
        produced.update(ids.canonical_table_name(n, libs) for n, _, _ in _refs(r, output=True))
        consumed.update(ids.canonical_table_name(n, libs) for n, _, _ in _refs(r, output=False))

    def role_for(canon: str) -> TableRole:
        is_out, is_in = canon in produced, canon in consumed
        if is_out and is_in:
            return TableRole.INTERMEDIATE
        return TableRole.OUTPUT if is_out else TableRole.SOURCE

    tables: dict[str, Table] = {}

    def upsert(
        name: str,
        cols: list[str],
        prov: Provenance,
        model_ref: str,
        libs: dict[str, str],
        *,
        output: bool,
    ) -> str:
        canon = ids.canonical_table_name(name, libs)
        tid = ids.table_id(name, libs)
        table = tables.get(tid)
        if table is None:
            table = Table(
                table_id=tid,
                name=canon,
                role=role_for(canon),
                source_system=canon.split(".", 1)[0] if "." in canon else None,
                source=prov,
            )
            tables[tid] = table
        known = {c.name for c in table.columns}
        for col in cols:
            if col not in known:
                table.columns.append(Column(name=col, source=prov))
                known.add(col)
        if output and model_ref not in table.produced_by:
            table.produced_by.append(model_ref)
        if not output and model_ref not in table.consumed_by:
            table.consumed_by.append(model_ref)
        return tid

    edge_ids: set[str] = set()
    col_edge_ids: set[str] = set()
    for r in results:
        libs = r.scan.libnames
        in_ids = [
            upsert(n, c, p, r.model_ref, libs, output=False) for n, c, p in _refs(r, output=False)
        ]
        out_ids = [
            upsert(n, c, p, r.model_ref, libs, output=True) for n, c, p in _refs(r, output=True)
        ]

        # Column-level edges — authoritative home of expressions (R4), from lineage rows.
        for row in r.extraction.lineage_rows if r.extraction else []:
            ttype = row.transformation_type or TransformationType.DERIVE
            ceid = ids.column_edge_id(
                row.source_element, row.target_element, r.model_ref, ttype.value
            )
            if ceid not in col_edge_ids:
                col_edge_ids.add(ceid)
                state.column_edges.append(
                    ColumnEdge(
                        edge_id=ceid,
                        source_element=row.source_element,
                        target_element=row.target_element,
                        model_id=r.model_ref,
                        transformation_type=ttype,
                        source=Provenance.EXTRACTED,
                    )
                )

        lineage_pairs = _table_edges_from_lineage(r, libs)
        edge_prov = Provenance.EXTRACTED if lineage_pairs else Provenance.HEURISTIC
        pairs = lineage_pairs or [(s, t) for s in in_ids for t in out_ids]
        for src, tgt in pairs:
            if src == tgt:
                continue
            eid = ids.table_edge_id(src, tgt, r.model_ref, TransformationType.DERIVE.value)
            if eid not in edge_ids:
                edge_ids.add(eid)
                state.table_edges.append(
                    TableEdge(
                        edge_id=eid,
                        source_table_id=src,
                        target_table_id=tgt,
                        model_id=r.model_ref,
                        transformation_type=TransformationType.DERIVE,
                        source=edge_prov,
                    )
                )

    state.tables = list(tables.values())


def _table_edges_from_lineage(result: _ModelResult, libs: dict[str, str]) -> list[tuple[str, str]]:
    if not result.extraction:
        return []
    pairs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in result.extraction.lineage_rows:
        src_tbl, tgt_tbl = _table_of(row.source_element), _table_of(row.target_element)
        if not src_tbl or not tgt_tbl:
            continue
        src, tgt = ids.table_id(src_tbl, libs), ids.table_id(tgt_tbl, libs)
        if (src, tgt) not in seen:
            seen.add((src, tgt))
            pairs.append((src, tgt))
    return pairs


def _table_of(element: str) -> str | None:
    parts = element.rsplit(".", 1)
    return parts[0] if len(parts) == 2 and "." in parts[0] else None


def _derive_source_systems(state: RunState) -> None:
    systems: dict[str, list[str]] = {}
    for table in state.tables:
        if table.source_system:
            systems.setdefault(table.source_system, []).append(table.table_id)
    state.source_systems = [
        SourceSystem(name=name, tables=sorted(tids)) for name, tids in sorted(systems.items())
    ]


__all__ = ["ModelInput", "analyze_run"]
