"""GraphvizRenderer — role swim-lanes to SVG/PDF (SDD §8.2; migrates v1 `draw_lineage_clustered`).

Builds a clustered ``graphviz.Digraph`` (Source / Intermediate / Output lanes,
left→right). ``render`` emits a rendered SVG/PDF when the Graphviz ``dot`` binary
is installed; when it is not, it degrades gracefully to writing the ``.gv`` DOT
source so the pipeline never hard-fails on a missing system dependency.
"""

from __future__ import annotations

from pathlib import Path

import graphviz

from modeltracex.lineage.graph import LineageGraph
from modeltracex.state import TableRole

_LANES = [
    (TableRole.SOURCE, "source", "Sources", "#22D3EE"),
    (TableRole.INTERMEDIATE, "intermediate", "Intermediate", "#A78BFA"),
    (TableRole.OUTPUT, "output", "Outputs", "#22C55E"),
]


class GraphvizRenderer:
    fmt = "svg"

    def _build(self, graph: LineageGraph) -> graphviz.Digraph:
        dot = graphviz.Digraph("lineage", graph_attr={"rankdir": "LR"})
        by_role = graph.tables_by_role()
        for role, cid, label, color in _LANES:
            tables = by_role[role]
            if not tables:
                continue
            with dot.subgraph(name=f"cluster_{cid}") as c:
                c.attr(label=label, color=color)
                for t in tables:
                    c.node(t.table_id, t.name)
        for e in graph.table_edges:
            dot.edge(e.source_table_id, e.target_table_id, label=e.transformation_type.value)
        return dot

    def to_dot(self, graph: LineageGraph) -> str:
        return self._build(graph).source

    def render(self, graph: LineageGraph, out_path: str, level: str = "table") -> str:
        dot = self._build(graph)
        try:
            return dot.render(out_path, format=self.fmt, cleanup=True)
        except graphviz.ExecutableNotFound:
            # No `dot` binary — write the portable DOT source instead.
            path = f"{out_path}.gv"
            Path(path).write_text(dot.source, encoding="utf-8")
            return path


__all__ = ["GraphvizRenderer"]
