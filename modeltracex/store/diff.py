"""``diff_runs(a, b)`` — per-entity set comparison over stable IDs (SDD §9.3, NFR-4).

Because every entity carries a deterministic content-addressed id (§9.2), two runs
are diffable as keyed sets: an entity present in both with identical serialized
content is *unchanged*; differing content is *changed*; ids only in one side are
*added*/*removed*. An unchanged re-run therefore produces an empty diff (the
property the run-compare UI and the override-stability tests rely on). Run
metadata (run_id/timestamp) is intentionally excluded — it is not an entity.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from pydantic import BaseModel

from modeltracex.state import RunState


@dataclass
class EntityDelta:
    kind: str
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (self.added or self.removed or self.changed)


@dataclass
class RunDiff:
    run_a: str
    run_b: str
    deltas: list[EntityDelta] = field(default_factory=list)

    def is_empty(self) -> bool:
        return all(d.is_empty() for d in self.deltas)

    def delta(self, kind: str) -> EntityDelta:
        return next(d for d in self.deltas if d.kind == kind)


def _index(items: Iterable[BaseModel], id_attr: str) -> dict[str, str]:
    """id -> canonical JSON, for keyed comparison."""
    return {getattr(it, id_attr): it.model_dump_json() for it in items}


# (kind, RunState attribute, stable-id attribute)
_KINDS: list[tuple[str, str, str]] = [
    ("model", "models", "model_id"),
    ("table", "tables", "table_id"),
    ("table_edge", "table_edges", "edge_id"),
    ("column_edge", "column_edges", "edge_id"),
    ("dq_rule", "dq_rules", "rule_id"),
]


def diff_runs(a: RunState, b: RunState) -> RunDiff:
    deltas: list[EntityDelta] = []
    for kind, attr, id_attr in _KINDS:
        ia = _index(getattr(a, attr), id_attr)
        ib = _index(getattr(b, attr), id_attr)
        added = sorted(ib.keys() - ia.keys())
        removed = sorted(ia.keys() - ib.keys())
        changed = sorted(k for k in ia.keys() & ib.keys() if ia[k] != ib[k])
        deltas.append(EntityDelta(kind=kind, added=added, removed=removed, changed=changed))
    return RunDiff(run_a=a.run.run_id, run_b=b.run.run_id, deltas=deltas)


__all__ = ["EntityDelta", "RunDiff", "diff_runs"]
