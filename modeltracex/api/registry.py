"""In-process run registry — the API's session state (SDD §13.1).

A ``RunSession`` holds everything one browser run needs: the ingested artifacts
grouped into editable **candidate models** (the Upload-tab file→model table), the
analyzed ``RunState`` once available, a per-run ``RunStore`` (override log +
fidelity blob), and a thread-safe event queue the SSE channel drains (FR-8.3).

The registry is process-local and ephemeral by design — SQLite via ``RunStore`` is
the durable record; this just tracks live runs for the interactive session.
"""

from __future__ import annotations

import queue
import threading
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from modeltracex.analysis.orchestrator import ModelInput
from modeltracex.ingestion import SourceArtifact, detect_language
from modeltracex.state import Language, RunState, SecurityMode
from modeltracex.store.db import RunStore

if TYPE_CHECKING:
    from modeltracex.analysis.rerun import IncrementalRun

# Run lifecycle states surfaced to the UI.
CREATED = "created"
INGESTED = "ingested"
ANALYZING = "analyzing"
DONE = "done"
FAILED = "failed"


@dataclass
class CandidateModel:
    """One editable row of the Upload-tab file→model table.

    Defaults to one candidate per file; ``PATCH /models`` merges several into one
    (multi-file model) or overrides the detected language (decisions D5, FR-2.3/2.4).
    """

    label: str
    language: Language
    files: list[SourceArtifact] = field(default_factory=list)
    evidence: str = ""
    language_overridden: bool = False

    @property
    def code(self) -> str:
        return "\n\n".join(a.content for a in self.files)

    @property
    def filenames(self) -> list[str]:
        return [a.filename for a in self.files]

    def to_input(self) -> ModelInput:
        return ModelInput(
            label=self.label,
            language=self.language,
            source_files=self.filenames,
            code=self.code,
        )


@dataclass
class RunSession:
    run_id: str
    store: RunStore
    status: str = CREATED
    candidates: list[CandidateModel] = field(default_factory=list)
    state: RunState | None = None
    engine: IncrementalRun | None = None  # caches per-model results for targeted re-run
    error: str | None = None
    events: queue.Queue[dict[str, object]] = field(default_factory=queue.Queue)
    _thread: threading.Thread | None = None
    # Per-run security mode override (D6). None → fall back to Settings.security_mode.
    # The egress guard runs again at analyze-time, so an out-of-policy choice raises.
    security_mode: SecurityMode | None = None

    # -- ingestion -------------------------------------------------------- #
    def add_artifacts(self, artifacts: list[SourceArtifact]) -> None:
        """Append artifacts as one candidate per file (detected language)."""
        for art in artifacts:
            det = detect_language(art.filename, art.content)
            self.candidates.append(
                CandidateModel(
                    label=_stem(art.filename),
                    language=det.language,
                    files=[art],
                    evidence=det.evidence,
                )
            )
        if self.candidates:
            self.status = INGESTED

    def inputs(self) -> list[ModelInput]:
        return [c.to_input() for c in self.candidates]


def _stem(filename: str) -> str:
    from pathlib import Path

    return Path(filename).stem or filename


class RunRegistry:
    """Thread-safe map of ``run_id`` → ``RunSession``."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self._db_path = db_path
        self._runs: dict[str, RunSession] = {}
        self._lock = threading.Lock()

    def create(self) -> RunSession:
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        # One in-memory store per run keeps interactive sessions isolated and fast;
        # the headless CLI path persists to a shared on-disk db separately.
        session = RunSession(run_id=run_id, store=RunStore(self._db_path))
        with self._lock:
            self._runs[run_id] = session
        return session

    def get(self, run_id: str) -> RunSession | None:
        with self._lock:
            return self._runs.get(run_id)

    def list_summaries(self, limit: int = 50) -> list[dict[str, object]]:
        """Recent-runs feed for the Upload-tab history panel (P4D-8).

        Surfaces every persisted run that lives in the per-session ``RunStore``s
        plus the currently-active in-memory sessions that haven't yet finished.
        In-memory entries get a synthetic summary (zero counts) so the
        analyze-in-flight case still shows up. The persisted entries are
        deduped against the in-memory ones by run_id (the live row wins, so a
        re-render mid-analysis stays consistent with the SSE stream).
        """
        with self._lock:
            live = list(self._runs.values())
        seen: set[str] = set()
        summaries: list[dict[str, object]] = []
        for session in live:
            if session.state is None:
                summaries.append(
                    {
                        "run_id": session.run_id,
                        "timestamp": "",
                        "tool_version": "",
                        "provider": "",
                        "model": "",
                        "tokens": 0,
                        "est_cost": 0.0,
                        "security_mode": "",
                        "status": session.status,
                        "counts": {
                            "models": len(session.candidates),
                            "tables": 0,
                            "table_edges": 0,
                            "column_edges": 0,
                            "dq_rules": 0,
                            "issues": 0,
                        },
                    }
                )
                seen.add(session.run_id)
                continue
            persisted = session.store.list_runs(limit=limit)
            for row in persisted:
                row_id = str(row["run_id"])
                if row_id in seen:
                    continue
                row["status"] = session.status if row_id == session.run_id else "done"
                summaries.append(row)
                seen.add(row_id)
        # Newest first; stable across re-render.
        summaries.sort(key=lambda r: str(r.get("timestamp") or ""), reverse=True)
        return summaries[:limit]


__all__ = [
    "CandidateModel",
    "RunSession",
    "RunRegistry",
    "CREATED",
    "INGESTED",
    "ANALYZING",
    "DONE",
    "FAILED",
]
