"""ReactFlow graph JSON — the Lineage-tab projection of ``RunState`` (FR-5.1, SDD §13.4.3).

Two views over the same canonical state:

* :func:`table_graph` — the always-loaded table-level swim-lane graph (one node per
  table, role = lane), with a ``pending_review`` count driving the "⚠ N edges
  pending review" footer (R9/D1).
* :func:`column_subgraph` — the **lazy** per-table expansion
  (``GET /lineage?level=column&table=<id>``): the table's columns plus every column
  edge touching them. Each column edge resolves *both* endpoints to a ``table_id``
  so a collapsed neighbour aggregates onto its table node — no orphaned edges
  (SDD §13.4.3b). The expression lives on the column edge (R4).
"""

from __future__ import annotations

from modeltracex import ids
from modeltracex.state import Provenanced, ReviewStatus, RunState, Table

_LANE_ORDER = {"Source": 0, "Intermediate": 1, "Output": 2}


def _prov(item: Provenanced) -> dict[str, str]:
    return {
        "provenance": item.source.value,
        "confidence": item.confidence.value,
        "review_status": item.review_status.value,
    }


def _pending_review(state: RunState) -> int:
    return sum(
        1
        for e in (*state.table_edges, *state.column_edges)
        if e.review_status is ReviewStatus.PROPOSED
    )


def table_graph(state: RunState) -> dict[str, object]:
    nodes = [
        {
            "id": t.table_id,
            "type": "table",
            "lane": t.role.value,
            "lane_index": _LANE_ORDER.get(t.role.value, 1),
            "data": {
                "name": t.name,
                "role": t.role.value,
                "source_system": t.source_system,
                "grain": t.grain,
                "column_count": len(t.columns),
                "produced_by": t.produced_by,
                "consumed_by": t.consumed_by,
                **_prov(t),
            },
        }
        for t in state.tables
    ]
    edges = [
        {
            "id": e.edge_id,
            "source": e.source_table_id,
            "target": e.target_table_id,
            "label": e.transformation_type.value,
            "data": {
                "transformation_type": e.transformation_type.value,
                "model_id": e.model_id,
                "notes": e.notes,
                **_prov(e),
            },
        }
        for e in state.table_edges
    ]
    return {
        "level": "table",
        "nodes": nodes,
        "edges": edges,
        "counts": {
            "tables": len(state.tables),
            "table_edges": len(state.table_edges),
            "column_edges": len(state.column_edges),
            "pending_review": _pending_review(state),
        },
    }


def _table_of(element: str) -> str | None:
    """The ``table`` part of a ``table.column`` element (handles dotted libnames)."""
    parts = element.rsplit(".", 1)
    return parts[0] if len(parts) == 2 else None


def _name_index(state: RunState) -> dict[str, str]:
    """Canonical table name → table_id, for resolving column-edge endpoints."""
    return {ids.canonical_table_name(t.name, {}): t.table_id for t in state.tables}


def column_subgraph(state: RunState, table_id: str) -> dict[str, object] | None:
    table: Table | None = next((t for t in state.tables if t.table_id == table_id), None)
    if table is None:
        return None

    name_to_id = _name_index(state)

    def tid_for(element: str | None) -> str | None:
        if element is None:
            return None
        return name_to_id.get(ids.canonical_table_name(element, {}))

    columns = [
        {
            "id": f"{table.name}.{c.name}",
            "table_id": table_id,
            "data": {"name": c.name, "role": c.role.value, "used_in": c.used_in, **_prov(c)},
        }
        for c in table.columns
    ]

    edges = []
    for ce in state.column_edges:
        src_tid = tid_for(_table_of(ce.source_element))
        tgt_tid = tid_for(_table_of(ce.target_element))
        if src_tid != table_id and tgt_tid != table_id:
            continue
        edges.append(
            {
                "id": ce.edge_id,
                "source": ce.source_element,
                "target": ce.target_element,
                "source_table_id": src_tid,
                "target_table_id": tgt_tid,
                "label": ce.transformation_type.value,
                "data": {
                    "transformation_type": ce.transformation_type.value,
                    "expression": ce.expression,
                    "join_keys": ce.join_keys,
                    "model_id": ce.model_id,
                    **_prov(ce),
                },
            }
        )

    return {
        "level": "column",
        "table_id": table_id,
        "table_name": table.name,
        "columns": columns,
        "column_edges": edges,
    }


__all__ = ["table_graph", "column_subgraph"]
