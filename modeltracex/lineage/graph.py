"""Lineage graph — a networkx **view** over RunState (SDD §8.1).

``RunState.tables + table_edges`` *is* the graph; this wraps it in a
``networkx.DiGraph`` for traversal/queries (reachability, source→output paths) but
never as storage — the Pydantic state stays canonical. Cross-model stitching is
already done upstream by canonical ``table_id`` (the orchestrator), so a table
written by one model and read by another is a single node here.
"""

from __future__ import annotations

import networkx as nx

from modeltracex.state import RunState, Table, TableEdge, TableRole


class LineageGraph:
    def __init__(self, state: RunState) -> None:
        self.state = state
        self._by_id: dict[str, Table] = {t.table_id: t for t in state.tables}
        g: nx.DiGraph = nx.DiGraph()
        for table in state.tables:
            g.add_node(table.table_id, name=table.name, role=table.role.value)
        for edge in state.table_edges:
            g.add_edge(
                edge.source_table_id,
                edge.target_table_id,
                edge_id=edge.edge_id,
                transformation_type=edge.transformation_type.value,
                model_id=edge.model_id,
            )
        self.nx = g

    def tables_by_role(self) -> dict[TableRole, list[Table]]:
        grouped: dict[TableRole, list[Table]] = {r: [] for r in TableRole}
        for table in self.state.tables:
            grouped[table.role].append(table)
        return grouped

    @property
    def table_edges(self) -> list[TableEdge]:
        return self.state.table_edges

    def name_of(self, table_id: str) -> str:
        table = self._by_id.get(table_id)
        return table.name if table else table_id

    def source_to_output_paths(self) -> list[list[str]]:
        """Every simple path from a Source table to an Output table (table_ids)."""
        sources = [t.table_id for t in self.state.tables if t.role is TableRole.SOURCE]
        sinks = [t.table_id for t in self.state.tables if t.role is TableRole.OUTPUT]
        paths: list[list[str]] = []
        for s in sources:
            for t in sinks:
                if s in self.nx and t in self.nx:
                    paths.extend(nx.all_simple_paths(self.nx, s, t))
        return paths


__all__ = ["LineageGraph"]
