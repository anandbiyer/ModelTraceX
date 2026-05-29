"""draw.io exporter (FR-7.3, SDD §8.2) — Phase 4 P4-2, editable XML.

Emits an mxGraph 2.0 ``<mxfile>`` document whose root ``<mxGraphModel>`` carries
one vertex per table and one edge per table-edge, parented under role swim-lane
groups (Source / Intermediate / Output). The format is the canonical input to
diagrams.net / draw.io desktop, so a reviewer can open the file, rearrange the
diagram, annotate, and re-export — the structural identity (vertex ids = our
``table_id``, edge ids = our ``edge_id``) is preserved across round-trips.

We hand-roll the XML rather than pull a templating engine: the document is small,
flat, and well-defined, and ``xml.etree.ElementTree`` ships with stdlib.
"""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

from modeltracex.state import RunState, TableRole

_LANE_X: dict[TableRole, int] = {
    TableRole.SOURCE: 40,
    TableRole.INTERMEDIATE: 360,
    TableRole.OUTPUT: 680,
}
_LANE_FILL: dict[TableRole, str] = {
    TableRole.SOURCE: "#1A2C44",
    TableRole.INTERMEDIATE: "#2A1F44",
    TableRole.OUTPUT: "#1A3A26",
}
_VERTEX_W = 220
_VERTEX_H = 60
_VERTEX_GAP = 20


def _style(fill: str) -> str:
    return (
        f"rounded=1;whiteSpace=wrap;html=1;fillColor={fill};"
        "strokeColor=#3B4760;fontColor=#E5E9F2;align=left;spacingLeft=8;"
    )


def _lane_style(fill: str) -> str:
    return (
        f"swimlane;startSize=24;fillColor={fill};strokeColor=#3B4760;"
        "fontColor=#E5E9F2;horizontal=0;"
    )


class DrawioExporter:
    fmt = "drawio"

    def to_xml(self, state: RunState) -> str:
        mxfile = ET.Element("mxfile", host="modeltracex")
        diagram = ET.SubElement(mxfile, "diagram", id="lineage", name="Lineage")
        model = ET.SubElement(
            diagram,
            "mxGraphModel",
            dx="1422",
            dy="757",
            grid="1",
            gridSize="10",
            guides="1",
            tooltips="1",
            connect="1",
            arrows="1",
            fold="1",
            page="1",
            pageScale="1",
            pageWidth="1100",
            pageHeight="850",
            math="0",
            shadow="0",
        )
        root = ET.SubElement(model, "root")
        # `parent` is an mxGraph attribute name but also ET.SubElement's positional
        # arg; pass it via `attrib=` so mypy and ET both stay happy.
        ET.SubElement(root, "mxCell", attrib={"id": "0"})
        ET.SubElement(root, "mxCell", attrib={"id": "1", "parent": "0"})

        # One swim-lane per role; vertices live inside.
        lanes: dict[TableRole, str] = {}
        for role in (TableRole.SOURCE, TableRole.INTERMEDIATE, TableRole.OUTPUT):
            lane_id = f"lane_{role.value.lower()}"
            lanes[role] = lane_id
            lane = ET.SubElement(
                root,
                "mxCell",
                attrib={
                    "id": lane_id,
                    "value": role.value,
                    "style": _lane_style(_LANE_FILL[role]),
                    "vertex": "1",
                    "parent": "1",
                },
            )
            ET.SubElement(
                lane,
                "mxGeometry",
                attrib={
                    "x": str(_LANE_X[role]),
                    "y": "40",
                    "width": str(_VERTEX_W + 40),
                    "height": "760",
                    "as": "geometry",
                },
            )

        # Tables → vertices, stacked vertically inside their role lane.
        y_by_role: dict[TableRole, int] = dict.fromkeys(_LANE_X, 40)
        for table in state.tables:
            lane_id = lanes.get(table.role, lanes[TableRole.SOURCE])
            cell = ET.SubElement(
                root,
                "mxCell",
                attrib={
                    "id": table.table_id,
                    "value": f"{table.name}\n({len(table.columns)} col)",
                    "style": _style(_LANE_FILL[table.role]),
                    "vertex": "1",
                    "parent": lane_id,
                },
            )
            y = y_by_role[table.role]
            ET.SubElement(
                cell,
                "mxGeometry",
                attrib={
                    "x": "20",
                    "y": str(y),
                    "width": str(_VERTEX_W),
                    "height": str(_VERTEX_H),
                    "as": "geometry",
                },
            )
            y_by_role[table.role] = y + _VERTEX_H + _VERTEX_GAP

        # Table edges.
        for edge in state.table_edges:
            cell = ET.SubElement(
                root,
                "mxCell",
                attrib={
                    "id": edge.edge_id,
                    "value": edge.transformation_type.value,
                    "style": (
                        "endArrow=block;html=1;rounded=0;strokeColor=#22D3EE;fontColor=#9BA6BD;"
                    ),
                    "edge": "1",
                    "parent": "1",
                    "source": edge.source_table_id,
                    "target": edge.target_table_id,
                },
            )
            ET.SubElement(cell, "mxGeometry", attrib={"relative": "1", "as": "geometry"})

        return ET.tostring(mxfile, encoding="unicode", xml_declaration=True)

    def export(self, state: RunState, out_dir: str) -> list[str]:
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        path = str(Path(out_dir) / "lineage.drawio")
        Path(path).write_text(self.to_xml(state), encoding="utf-8")
        return [path]


__all__ = ["DrawioExporter"]
