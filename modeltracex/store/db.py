"""``RunStore`` — SQLAlchemy + SQLite persistence (SDD §9.1, NFR-4).

Two complementary representations, per the SDD:

* ``runs.state_json`` — the full validated ``RunState`` serialized, the **fidelity**
  copy that ``load`` round-trips back into a ``RunState`` exactly.
* an ``entities`` index (run_id, kind, entity_id, data_json) — the **flattened,
  queryable** projection (e.g. "every table_id in this run"). Phase 2's diff/query
  work can specialize this into the per-type tables the SDD sketches; a single
  keyed index is enough for the Phase-0 foundation and keeps it lean.

Plus an ``overrides`` log: human accept/reject/edit actions keyed by entity id, so
they survive re-runs (``apply_overrides`` re-applies them by id; a target that has
disappeared becomes a stale-override ``Issue``, SDD §9.3).
"""

from __future__ import annotations

import json
from enum import Enum

from sqlalchemy import Float, Integer, String, Text, create_engine, delete, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy.pool import StaticPool

from modeltracex.state import Issue, Override, RunState


class Base(DeclarativeBase):
    pass


class RunRow(Base):
    __tablename__ = "runs"

    run_id: Mapped[str] = mapped_column(String, primary_key=True)
    timestamp: Mapped[str] = mapped_column(String)
    tool_version: Mapped[str] = mapped_column(String)
    provider: Mapped[str] = mapped_column(String)
    model: Mapped[str] = mapped_column(String)
    tokens: Mapped[int] = mapped_column(Integer)
    est_cost: Mapped[float] = mapped_column(Float)
    security_mode: Mapped[str] = mapped_column(String)
    state_json: Mapped[str] = mapped_column(Text)


class EntityRow(Base):
    __tablename__ = "entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String, index=True)
    kind: Mapped[str] = mapped_column(String, index=True)
    entity_id: Mapped[str] = mapped_column(String, index=True)
    data_json: Mapped[str] = mapped_column(Text)


class OverrideRow(Base):
    __tablename__ = "overrides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String, index=True)
    target: Mapped[str] = mapped_column(String, index=True)
    field: Mapped[str] = mapped_column(String)
    old: Mapped[str] = mapped_column(Text)  # json-encoded
    new: Mapped[str] = mapped_column(Text)  # json-encoded
    by: Mapped[str] = mapped_column(String)
    timestamp: Mapped[str] = mapped_column(String)


# (kind, attribute holding the stable id) for the flattened index. Entities without
# a stable id (issues, usage observations) index under an empty entity_id.
_FLATTENED: list[tuple[str, str, str | None]] = [
    ("model", "models", "model_id"),
    ("table", "tables", "table_id"),
    ("table_edge", "table_edges", "edge_id"),
    ("column_edge", "column_edges", "edge_id"),
    ("dq_rule", "dq_rules", "rule_id"),
    ("source_system", "source_systems", "name"),
    ("usage_observation", "usage_observations", None),
    ("issue", "issues", None),
]


class RunStore:
    def __init__(self, db: str = ":memory:") -> None:
        url = db if "://" in db else f"sqlite:///{db}"
        # The interactive API analyzes in a background thread, so the store is touched
        # from more than one thread. An in-memory SQLite db is per-connection, so we
        # pin a single shared connection (StaticPool) and disable the same-thread check;
        # otherwise a second thread would open a fresh, empty database (no tables).
        is_memory = ":memory:" in url or url in ("sqlite://", "sqlite:///:memory:")
        kwargs: dict[str, object] = {"connect_args": {"check_same_thread": False}}
        if is_memory:
            kwargs["poolclass"] = StaticPool
        self._engine = create_engine(url, **kwargs)
        Base.metadata.create_all(self._engine)

    def save(self, state: RunState) -> None:
        """Persist (or replace) a run: fidelity blob + flattened entity index."""
        run_id = state.run.run_id
        with Session(self._engine) as session, session.begin():
            session.execute(delete(RunRow).where(RunRow.run_id == run_id))
            session.execute(delete(EntityRow).where(EntityRow.run_id == run_id))
            session.add(
                RunRow(
                    run_id=run_id,
                    timestamp=state.run.timestamp,
                    tool_version=state.run.tool_version,
                    provider=state.run.llm_provider,
                    model=state.run.llm_model,
                    tokens=state.run.tokens,
                    est_cost=state.run.est_cost,
                    security_mode=state.run.security_mode.value,
                    state_json=state.model_dump_json(),
                )
            )
            for kind, attr, id_attr in _FLATTENED:
                for item in getattr(state, attr):
                    entity_id = getattr(item, id_attr) if id_attr else ""
                    session.add(
                        EntityRow(
                            run_id=run_id,
                            kind=kind,
                            entity_id=entity_id,
                            data_json=item.model_dump_json(),
                        )
                    )

    def load(self, run_id: str) -> RunState:
        with Session(self._engine) as session:
            row = session.get(RunRow, run_id)
            if row is None:
                raise KeyError(f"no run {run_id!r} in store")
            return RunState.model_validate_json(row.state_json)

    def entity_ids(self, run_id: str, kind: str) -> list[str]:
        """Flattened-table query: the stable ids of one entity kind in a run."""
        with Session(self._engine) as session:
            stmt = (
                select(EntityRow.entity_id)
                .where(EntityRow.run_id == run_id, EntityRow.kind == kind)
                .order_by(EntityRow.entity_id)
            )
            return list(session.execute(stmt).scalars().all())

    def list_runs(self, limit: int = 50) -> list[dict[str, object]]:
        """List persisted runs as small summary dicts (Phase 4D run history).

        Returns the most recently-saved runs first, capped at ``limit``. Counts
        are derived from the flattened ``entities`` index so we don't deserialize
        every blob. This is cheap enough to call on every Upload-tab mount and
        small enough to fit in a TanStack Query cache.
        """
        with Session(self._engine) as session:
            run_rows = list(
                session.execute(select(RunRow).order_by(RunRow.timestamp.desc()).limit(limit))
                .scalars()
                .all()
            )
            summaries: list[dict[str, object]] = []
            for r in run_rows:
                counts = {
                    "models": 0,
                    "tables": 0,
                    "table_edges": 0,
                    "column_edges": 0,
                    "dq_rules": 0,
                    "issues": 0,
                }
                for kind, _attr, _id_attr in _FLATTENED:
                    key = (
                        "models"
                        if kind == "model"
                        else "tables"
                        if kind == "table"
                        else "table_edges"
                        if kind == "table_edge"
                        else "column_edges"
                        if kind == "column_edge"
                        else "dq_rules"
                        if kind == "dq_rule"
                        else "issues"
                        if kind == "issue"
                        else None
                    )
                    if key is None:
                        continue
                    n = session.execute(
                        select(EntityRow.id).where(
                            EntityRow.run_id == r.run_id, EntityRow.kind == kind
                        )
                    ).all()
                    counts[key] = len(n)
                summaries.append(
                    {
                        "run_id": r.run_id,
                        "timestamp": r.timestamp,
                        "tool_version": r.tool_version,
                        "provider": r.provider,
                        "model": r.model,
                        "tokens": r.tokens,
                        "est_cost": r.est_cost,
                        "security_mode": r.security_mode,
                        "counts": counts,
                    }
                )
            return summaries

    def log_override(self, run_id: str, override: Override) -> None:
        with Session(self._engine) as session, session.begin():
            session.add(
                OverrideRow(
                    run_id=run_id,
                    target=override.target,
                    field=override.field,
                    old=json.dumps(override.old),
                    new=json.dumps(override.new),
                    by=override.by,
                    timestamp=override.timestamp,
                )
            )

    def overrides_for(self, run_id: str) -> list[Override]:
        with Session(self._engine) as session:
            stmt = select(OverrideRow).where(OverrideRow.run_id == run_id).order_by(OverrideRow.id)
            return [
                Override(
                    target=row.target,
                    field=row.field,
                    old=json.loads(row.old),
                    new=json.loads(row.new),
                    by=row.by,
                    timestamp=row.timestamp,
                )
                for row in session.execute(stmt).scalars().all()
            ]


def apply_overrides(state: RunState, overrides: list[Override]) -> RunState:
    """Return a copy of ``state`` with each override re-applied to its target by id.

    Targets that no longer exist are recorded as stale-override Issues (SDD §9.3).
    """
    new = state.model_copy(deep=True)
    index: dict[str, object] = {}
    for table in new.tables:
        index[table.table_id] = table
    for edge in new.table_edges:
        index[edge.edge_id] = edge
    for cedge in new.column_edges:
        index[cedge.edge_id] = cedge
    for rule in new.dq_rules:
        index[rule.rule_id] = rule
    for model in new.models:
        index[model.model_id] = model

    applied: list[Override] = []
    for override in overrides:
        target = index.get(override.target)
        if target is not None and hasattr(target, override.field):
            current = getattr(target, override.field)
            # Coerce a JSON scalar back into the field's enum type (e.g. "Accepted"
            # -> ReviewStatus.ACCEPTED) so the re-applied state stays well-typed.
            value = (
                type(current)(override.new)
                if isinstance(current, Enum) and not isinstance(override.new, Enum)
                else override.new
            )
            setattr(target, override.field, value)
            applied.append(override)
        else:
            new.issues.append(
                Issue(
                    severity="warning",
                    message=f"stale override: target {override.target!r} "
                    f"field {override.field!r} not found on re-apply",
                )
            )
    new.overrides = applied
    return new


__all__ = ["RunStore", "apply_overrides"]
