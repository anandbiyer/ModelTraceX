"""MermaidRenderer — portable, version-controllable `.mmd` (SDD §8.2, FR-7.1).

Pure string template (no binary), so it always works in CI. Role swim-lanes
(Source / Intermediate / Output) become Mermaid subgraphs; table edges carry their
transformation type as the edge label.
"""

from __future__ import annotations

from pathlib import Path

from modeltracex.lineage.graph import LineageGraph
from modeltracex.state import TableRole

_LANES = [
    (TableRole.SOURCE, "sources", "Sources"),
    (TableRole.INTERMEDIATE, "intermediate", "Intermediate"),
    (TableRole.OUTPUT, "outputs", "Outputs"),
]


class MermaidRenderer:
    fmt = "mermaid"

    def to_text(self, graph: LineageGraph) -> str:
        by_role = graph.tables_by_role()
        lines = ["flowchart LR"]
        for role, sg_id, title in _LANES:
            tables = by_role[role]
            if not tables:
                continue
            lines.append(f"  subgraph {sg_id}[{title}]")
            for t in tables:
                lines.append(f'    {t.table_id}["{t.name}"]')
            lines.append("  end")
        for e in graph.table_edges:
            label = e.transformation_type.value
            lines.append(f"  {e.source_table_id} -->|{label}| {e.target_table_id}")
        return "\n".join(lines) + "\n"

    def render(self, graph: LineageGraph, out_path: str, level: str = "table") -> str:
        path = out_path if out_path.endswith(".mmd") else f"{out_path}.mmd"
        Path(path).write_text(self.to_text(graph), encoding="utf-8")
        return path


__all__ = ["MermaidRenderer"]
