"""Apply a human override to a live ``RunState`` (NFR-5, R9/D1, SDD §9.3).

Accept / reject / edit on **tables, columns, and edges** (and DQ rules). An edit
both writes the new value and flips ``review_status`` to ``Accepted`` (curating a
fact accepts it); an explicit accept/reject sets ``review_status`` directly. Every
change is captured as an :class:`~modeltracex.state.Override`, so it is reversible
and survives a re-run by id (the orchestrator re-applies the override log).

Targets are addressed by stable id; a **column** has no id of its own, so it is
addressed as ``<table_id>#<column_name>``.
"""

from __future__ import annotations

from enum import Enum

from modeltracex.state import Override, ReviewStatus, RunState

COLUMN_SEP = "#"


class OverrideError(KeyError):
    """Target id or field could not be resolved (mapped to HTTP 404/422)."""


def _entity_index(state: RunState) -> dict[str, object]:
    index: dict[str, object] = {}
    for table in state.tables:
        index[table.table_id] = table
    for edge in state.table_edges:
        index[edge.edge_id] = edge
    for cedge in state.column_edges:
        index[cedge.edge_id] = cedge
    for rule in state.dq_rules:
        index[rule.rule_id] = rule
    for model in state.models:
        index[model.model_id] = model
    return index


def resolve_target(state: RunState, target: str) -> object | None:
    if COLUMN_SEP in target:
        table_id, _, col_name = target.partition(COLUMN_SEP)
        table = next((t for t in state.tables if t.table_id == table_id), None)
        if table is None:
            return None
        return next((c for c in table.columns if c.name == col_name), None)
    return _entity_index(state).get(target)


def _coerce(current: object, value: object) -> object:
    """Coerce a JSON scalar into the field's enum type when the field holds one."""
    if isinstance(current, Enum) and not isinstance(value, Enum):
        return type(current)(value)
    return value


def apply_override(state: RunState, override: Override) -> object:
    """Mutate ``state`` in place; return the affected entity. Raises ``OverrideError``."""
    target = resolve_target(state, override.target)
    if target is None:
        raise OverrideError(f"override target {override.target!r} not found")
    if not hasattr(target, override.field):
        raise OverrideError(f"field {override.field!r} not valid for target {override.target!r}")
    setattr(target, override.field, _coerce(getattr(target, override.field), override.new))
    # An edit curates the fact, so it counts as acceptance (R9/D1). An explicit
    # review_status change (accept/reject) is honoured as-is.
    if override.field != "review_status" and hasattr(target, "review_status"):
        target.review_status = ReviewStatus.ACCEPTED
    return target


def pending_review(state: RunState) -> int:
    return sum(
        1
        for e in (*state.table_edges, *state.column_edges)
        if e.review_status is ReviewStatus.PROPOSED
    )


__all__ = ["OverrideError", "resolve_target", "apply_override", "pending_review", "COLUMN_SEP"]
