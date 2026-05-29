"""FastAPI surface for the interactive reviewer (Deliverable 10, SDD §13.1).

One run is created, ingested, (optionally) edited, analyzed, then browsed. The
orchestrator runs in a background thread and streams per-model progress over a
single SSE channel (FR-8.3); every projection (state, lineage, exports) reads from
the resulting canonical ``RunState``. Human accept/reject/edit posts overrides that
mutate the live state, flip ``review_status`` (NFR-5, R9/D1), and persist to the
run store so they survive a re-run by id.

The provider is injected via the ``get_provider`` dependency so tests bind a
``FakeProvider`` and CI never touches the network.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import threading
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from modeltracex.analysis.rerun import INVALIDATION, IncrementalRun, triggers_llm
from modeltracex.api import estimate as estimate_mod
from modeltracex.api import lineage_json
from modeltracex.api.overrides import OverrideError, apply_override, pending_review
from modeltracex.api.registry import (
    ANALYZING,
    DONE,
    FAILED,
    CandidateModel,
    RunRegistry,
    RunSession,
)
from modeltracex.chat import ChatAgent
from modeltracex.config import Settings, get_settings
from modeltracex.ingestion import SourceArtifact, read_paste, read_path, unzip_project
from modeltracex.llm.provider import LLMProvider, build_provider
from modeltracex.security import default_redactor, scrub_for_retention
from modeltracex.state import Language, Override, SecurityMode

# --------------------------------------------------------------------------- #
# Request / response bodies
# --------------------------------------------------------------------------- #


class MergeOp(BaseModel):
    """Merge candidate models (by 0-based index) into one logical model (FR-2.4)."""

    op: Literal["merge"] = "merge"
    indices: list[int]
    label: str | None = None


class LanguageOp(BaseModel):
    """Override a candidate's detected language (decision D5, FR-2.3)."""

    op: Literal["set_language"] = "set_language"
    index: int
    language: Language


PatchOp = Annotated[MergeOp | LanguageOp, Field(discriminator="op")]


class PatchModelsRequest(BaseModel):
    operations: list[PatchOp] = []


class OverrideRequest(BaseModel):
    target: str
    field: str
    new: object | None = None
    old: object | None = None
    by: str = "user"


class ChatRequest(BaseModel):
    message: str


class SecurityModeRequest(BaseModel):
    """Per-run override of security_mode (decision D6)."""

    security_mode: SecurityMode


class ChatMutationBody(BaseModel):
    op: str
    args: dict = Field(default_factory=dict)


class ChatApplyRequest(BaseModel):
    mutations: list[ChatMutationBody]


# --------------------------------------------------------------------------- #
# Dependencies (overridable in tests)
# --------------------------------------------------------------------------- #


def get_provider() -> LLMProvider:
    return build_provider(get_settings())


# --------------------------------------------------------------------------- #
# Ingestion helpers
# --------------------------------------------------------------------------- #


def _artifacts_from_upload(filename: str, data: bytes) -> list[SourceArtifact]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".zip":
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / filename
            p.write_bytes(data)
            return unzip_project(p)
    if suffix in (".docx", ".pdf"):
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / filename
            p.write_bytes(data)
            art = read_path(p)
            art.filename = filename  # restore the user-facing name
            return [art]
    return [SourceArtifact(filename=filename, content=data.decode("utf-8", errors="replace"))]


def _candidate_view(session: RunSession) -> dict[str, object]:
    models = [
        {
            "index": i,
            "label": c.label,
            "language": c.language.value,
            "language_overridden": c.language_overridden,
            "files": [{"filename": f.filename, "evidence": c.evidence} for f in c.files],
        }
        for i, c in enumerate(session.candidates)
    ]
    return {
        "run_id": session.run_id,
        "status": session.status,
        "files": sum(len(c.files) for c in session.candidates),
        "models": models,
    }


# --------------------------------------------------------------------------- #
# App factory
# --------------------------------------------------------------------------- #


def create_app(settings: Settings | None = None, registry: RunRegistry | None = None) -> FastAPI:
    app = FastAPI(title="ModelTraceX", version="2.0.0-dev")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    cfg = settings or get_settings()
    reg = registry or RunRegistry()
    app.state.settings = cfg
    app.state.registry = reg

    def _session_or_404(run_id: str) -> RunSession:
        session = reg.get(run_id)
        if session is None:
            raise HTTPException(status_code=404, detail=f"no run {run_id!r}")
        return session

    # -- lifecycle ------------------------------------------------------- #
    @app.get("/config")
    def config() -> dict[str, object]:
        """Public-safe runtime config the FE needs (D6, NFR-2 ceiling on Cloud)."""
        return {
            "security_mode": cfg.security_mode.value,
            "allowed_security_modes": [m.value for m in cfg.allowed_security_modes],
            "retain_source": cfg.retain_source,
            "detail_level": cfg.detail_level.value,
            "provider": cfg.provider,
            "model": cfg.model,
        }

    @app.post("/runs")
    def create_run() -> dict[str, str]:
        session = reg.create()
        return {"run_id": session.run_id, "status": session.status}

    @app.get("/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, object]:
        session = _session_or_404(run_id)
        return {
            "run_id": session.run_id,
            "status": session.status,
            "models": len(session.candidates),
            "error": session.error,
        }

    @app.post("/runs/{run_id}/ingest")
    async def ingest(
        run_id: str,
        files: Annotated[list[UploadFile], File()] = [],  # noqa: B006
        paste: Annotated[str | None, Form()] = None,
        paste_filename: Annotated[str, Form()] = "pasted.txt",
    ) -> dict[str, object]:
        session = _session_or_404(run_id)
        artifacts: list[SourceArtifact] = []
        for upload in files:
            data = await upload.read()
            artifacts.extend(_artifacts_from_upload(upload.filename or "upload.txt", data))
        if paste:
            artifacts.append(read_paste(paste, paste_filename))
        if not artifacts:
            raise HTTPException(status_code=422, detail="no files or paste content supplied")
        session.add_artifacts(artifacts)
        return _candidate_view(session)

    @app.patch("/runs/{run_id}/models")
    def patch_models(run_id: str, body: PatchModelsRequest) -> dict[str, object]:
        session = _session_or_404(run_id)
        for op in body.operations:
            if isinstance(op, LanguageOp):
                if not 0 <= op.index < len(session.candidates):
                    raise HTTPException(status_code=422, detail=f"bad index {op.index}")
                cand = session.candidates[op.index]
                cand.language = op.language
                cand.language_overridden = True
            else:  # MergeOp
                _merge_candidates(session, op)
        return _candidate_view(session)

    @app.post("/runs/{run_id}/estimate")
    def estimate(run_id: str) -> dict[str, object]:
        session = _session_or_404(run_id)
        return estimate_mod.estimate_models([(c.label, c.code) for c in session.candidates])

    @app.patch("/runs/{run_id}/security")
    def patch_security(run_id: str, body: SecurityModeRequest) -> dict[str, object]:
        """Set the per-run security mode (D6); bounded by ``allowed_security_modes``."""
        session = _session_or_404(run_id)
        if body.security_mode not in cfg.allowed_security_modes:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"security_mode={body.security_mode.value!r} not in allowed "
                    f"{[m.value for m in cfg.allowed_security_modes]}"
                ),
            )
        session.security_mode = body.security_mode
        return {"run_id": run_id, "security_mode": body.security_mode.value}

    @app.post("/runs/{run_id}/analyze")
    def analyze(
        run_id: str, provider: Annotated[LLMProvider, Depends(get_provider)]
    ) -> dict[str, str]:
        session = _session_or_404(run_id)
        if not session.candidates:
            raise HTTPException(status_code=422, detail="nothing ingested to analyze")
        if session.status == ANALYZING:
            raise HTTPException(status_code=409, detail="run already analyzing")
        # If the run has a security_mode override, rebuild the provider through the
        # egress guard with that mode — keeps NFR-2 enforced regardless of UI input.
        effective_cfg = cfg
        effective_provider = provider
        if session.security_mode is not None and session.security_mode is not cfg.security_mode:
            effective_cfg = cfg.model_copy(update={"security_mode": session.security_mode})
            effective_provider = build_provider(effective_cfg)
        session.status = ANALYZING
        session.error = None
        thread = threading.Thread(
            target=_run_analysis,
            args=(session, effective_provider, effective_cfg),
            daemon=True,
        )
        session._thread = thread
        thread.start()
        return {"run_id": run_id, "status": ANALYZING}

    @app.get("/runs/{run_id}/events")
    async def events(run_id: str) -> EventSourceResponse:
        session = _session_or_404(run_id)
        return EventSourceResponse(_event_stream(session))

    @app.get("/runs/{run_id}/state")
    def state(run_id: str) -> JSONResponse:
        session = _session_or_404(run_id)
        if session.state is None:
            raise HTTPException(status_code=409, detail="run not analyzed yet")
        return JSONResponse(content=json.loads(session.state.model_dump_json()))

    @app.get("/runs/{run_id}/lineage")
    def lineage(
        run_id: str,
        level: str = "table",
        table: str | None = Query(default=None),
    ) -> dict[str, object]:
        session = _analyzed_or_409(_session_or_404(run_id))
        assert session.state is not None
        if level == "column" and table is not None:
            sub = lineage_json.column_subgraph(session.state, table)
            if sub is None:
                raise HTTPException(status_code=404, detail=f"no table {table!r}")
            return sub
        return lineage_json.table_graph(session.state)

    @app.post("/runs/{run_id}/overrides")
    def overrides(run_id: str, body: OverrideRequest) -> dict[str, object]:
        session = _analyzed_or_409(_session_or_404(run_id))
        assert session.state is not None
        override = Override(
            target=body.target,
            field=body.field,
            old=body.old,
            new=body.new,
            by=body.by,
            timestamp=datetime.now(tz=UTC).isoformat(),
        )
        try:
            entity = apply_override(session.state, override)
        except OverrideError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        session.store.log_override(run_id, override)
        session.state.overrides.append(override)
        session.store.save(session.state)
        entity_view = (
            json.loads(entity.model_dump_json()) if isinstance(entity, BaseModel) else str(entity)
        )
        return {
            "ok": True,
            "target": body.target,
            "entity": entity_view,
            "pending_review": pending_review(session.state),
        }

    @app.get("/runs/{run_id}/exports/{kind}")
    def export(run_id: str, kind: str) -> FileResponse:
        session = _analyzed_or_409(_session_or_404(run_id))
        assert session.state is not None
        path = _export_file(session, kind)
        return FileResponse(path, filename=Path(path).name)

    # -- chat-to-state (SDD §13.2/§13.3) --------------------------------- #
    @app.post("/runs/{run_id}/chat")
    def chat(
        run_id: str,
        body: ChatRequest,
        provider: Annotated[LLMProvider, Depends(get_provider)],
    ) -> dict[str, object]:
        session = _analyzed_or_409(_session_or_404(run_id))
        plan = ChatAgent(provider).plan(body.message, session.state)
        return {
            "rationale": plan.rationale,
            "mutations": [
                {
                    "op": m.op,
                    "args": m.args,
                    "requires_confirmation": m.requires_confirmation,
                    "triggers_llm": triggers_llm(m.op),
                    "invalidates": sorted(s.value for s in INVALIDATION.get(m.op, frozenset())),
                }
                for m in plan.mutations
            ],
        }

    @app.post("/runs/{run_id}/chat/apply")
    def chat_apply(run_id: str, body: ChatApplyRequest) -> dict[str, object]:
        session = _analyzed_or_409(_session_or_404(run_id))
        if session.engine is None:
            raise HTTPException(status_code=409, detail="run has no incremental engine")
        if not body.mutations:
            raise HTTPException(status_code=422, detail="no mutations to apply")
        reanalyzed: list[str] = []
        llm_used = False
        for m in body.mutations:
            try:
                outcome = session.engine.apply(m.op, m.args)
            except (ValueError, KeyError) as exc:
                raise HTTPException(status_code=422, detail=f"cannot apply {m.op}: {exc}") from exc
            reanalyzed += outcome.reanalyzed
            llm_used = llm_used or outcome.llm_used
            session.state = outcome.state
        # Re-apply logged entity overrides on top of the re-assembled state (§9.3).
        assert session.state is not None
        for ov in session.store.overrides_for(run_id):
            with contextlib.suppress(OverrideError):
                apply_override(session.state, ov)
        session.store.save(session.state)
        return {
            "ok": True,
            "reanalyzed": reanalyzed,
            "llm_used": llm_used,
            "counts": {
                "tables": len(session.state.tables),
                "table_edges": len(session.state.table_edges),
                "dq_rules": len(session.state.dq_rules),
                "pending_review": pending_review(session.state),
            },
        }

    return app


def _analyzed_or_409(session: RunSession) -> RunSession:
    if session.state is None:
        raise HTTPException(status_code=409, detail="run not analyzed yet")
    return session


def _merge_candidates(session: RunSession, op: MergeOp) -> None:
    idx = sorted({i for i in op.indices if 0 <= i < len(session.candidates)})
    if len(idx) < 2:
        raise HTTPException(status_code=422, detail="merge needs >=2 valid indices")
    chosen = [session.candidates[i] for i in idx]
    merged = CandidateModel(
        label=op.label or chosen[0].label,
        language=chosen[0].language,
        files=[f for c in chosen for f in c.files],
        evidence=chosen[0].evidence,
        language_overridden=chosen[0].language_overridden,
    )
    remaining = [c for i, c in enumerate(session.candidates) if i not in set(idx)]
    remaining.insert(idx[0], merged)
    session.candidates = remaining


# --------------------------------------------------------------------------- #
# Background analysis + SSE
# --------------------------------------------------------------------------- #


def _run_analysis(session: RunSession, provider: LLMProvider, cfg: Settings) -> None:
    session.events.put(
        {"type": "run_started", "run_id": session.run_id, "total": len(session.candidates)}
    )
    try:
        # The interactive run is driven by the incremental engine so a later chat
        # mutation re-runs only the minimal set (§13.3); the initial pass is a full run.
        # The redactor masks PII before any provider call (NFR-2).
        engine = IncrementalRun(
            provider,
            session.inputs(),
            run_id=session.run_id,
            detail_level=cfg.detail_level,
            tool_version=cfg.tool_version,
            redactor=default_redactor(),
        )
        run_state = engine.full(on_progress=session.events.put)
        run_state.run.security_mode = cfg.security_mode
        scrub_for_retention(run_state, retain_source=cfg.retain_source)
        session.engine = engine
        # Re-apply any human overrides logged in earlier passes (survives re-run, §9.3).
        for ov in session.store.overrides_for(session.run_id):
            with contextlib.suppress(OverrideError):
                apply_override(run_state, ov)
        session.state = run_state
        session.store.save(run_state)
        session.status = DONE
        session.events.put(
            {
                "type": "run_completed",
                "run_id": session.run_id,
                "status": "done",
                "counts": {
                    "models": len(run_state.models),
                    "tables": len(run_state.tables),
                    "table_edges": len(run_state.table_edges),
                    "column_edges": len(run_state.column_edges),
                    "dq_rules": len(run_state.dq_rules),
                    "pending_review": pending_review(run_state),
                },
            }
        )
    except Exception as exc:  # noqa: BLE001 - report failure to the stream, don't crash the thread
        session.status = FAILED
        session.error = str(exc)
        session.events.put(
            {"type": "run_failed", "run_id": session.run_id, "status": "failed", "error": str(exc)}
        )


async def _event_stream(session: RunSession) -> AsyncIterator[dict[str, str]]:
    import queue as _queue

    terminal = {"run_completed", "run_failed"}
    while True:
        try:
            event = session.events.get_nowait()
        except _queue.Empty:
            if session.status != ANALYZING and session.events.empty():
                break
            await asyncio.sleep(0.02)
            continue
        yield {"event": str(event.get("type", "message")), "data": json.dumps(event)}
        if event.get("type") in terminal:
            break


# --------------------------------------------------------------------------- #
# Exports
# --------------------------------------------------------------------------- #


def _export_file(session: RunSession, kind: str) -> str:
    from modeltracex.exporters.csv_compat import CsvCompatExporter
    from modeltracex.exporters.docx_report import DocxExporter
    from modeltracex.exporters.xlsx_workbook import XlsxExporter
    from modeltracex.lineage.drawio import DrawioExporter
    from modeltracex.lineage.graph import LineageGraph
    from modeltracex.lineage.openlineage import OpenLineageExporter
    from modeltracex.lineage.render_graphviz import GraphvizRenderer
    from modeltracex.lineage.render_mermaid import MermaidRenderer

    assert session.state is not None
    out_dir = Path(TemporaryDirectory(prefix=f"mtx_{session.run_id}_").name)
    out_dir.mkdir(parents=True, exist_ok=True)

    if kind == "docx":
        return DocxExporter().export(session.state, str(out_dir))[0]
    if kind == "xlsx":
        return XlsxExporter().export(session.state, str(out_dir))[0]
    if kind == "csv":
        return CsvCompatExporter().export(session.state, str(out_dir))[0]
    if kind == "mermaid":
        return MermaidRenderer().render(LineageGraph(session.state), str(out_dir / "lineage"))
    if kind == "openlineage":
        return OpenLineageExporter().export(session.state, str(out_dir))[0]
    if kind == "drawio":
        return DrawioExporter().export(session.state, str(out_dir))[0]
    if kind in ("svg", "pdf"):
        renderer = GraphvizRenderer()
        renderer.fmt = kind
        return renderer.render(LineageGraph(session.state), str(out_dir / "lineage"))
    raise HTTPException(status_code=404, detail=f"unknown export kind {kind!r}")


__all__ = ["create_app", "get_provider"]
