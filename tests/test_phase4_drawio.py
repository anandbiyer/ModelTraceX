"""Phase 4 P4-T5 — draw.io exporter structural round-trip.

The export is XML, so the unit gate parses the emitted document with stdlib
``xml.etree.ElementTree`` and asserts the structure draw.io / diagrams.net
requires (mxfile → diagram → mxGraphModel → root with vertex + edge cells)
plus identity preservation (vertex ids = ``table_id``, edge ids = ``edge_id``).
"""

from __future__ import annotations

import json
from pathlib import Path
from xml.etree import ElementTree as ET

from modeltracex.analysis.orchestrator import ModelInput, analyze_run
from modeltracex.lineage.drawio import DrawioExporter
from modeltracex.llm.fake import FakeProvider
from modeltracex.state import Language, RunState


def _state() -> RunState:
    payload = json.dumps(
        {
            "purpose": "p",
            "input_tables": [{"name": "raw.events"}],
            "output_tables": [{"name": "work.staging"}],
            "lineage_rows": ["raw.events.amount -> work.staging.amount_net"],
        }
    )
    return analyze_run(
        FakeProvider(responses={"m": payload}, default=payload),
        [
            ModelInput(
                label="m", language=Language.SAS, source_files=["m.sas"], code="data work.staging;"
            )
        ],
        run_id="drawio_test",
    )


def test_export_writes_parseable_mxfile(tmp_path: Path) -> None:
    state = _state()
    [path] = DrawioExporter().export(state, str(tmp_path))
    tree = ET.parse(path)
    root = tree.getroot()
    assert root.tag == "mxfile"
    model = root.find("./diagram/mxGraphModel/root")
    assert model is not None
    # 0 + 1 layer cells + 3 lanes + N table vertices + M edges
    cells = list(model.findall("./mxCell"))
    assert any(c.attrib.get("id") == "0" for c in cells)
    assert any(c.attrib.get("id") == "1" for c in cells)


def test_vertex_ids_match_table_ids_and_edge_ids_match_edge_ids() -> None:
    state = _state()
    xml = DrawioExporter().to_xml(state)
    root = ET.fromstring(xml)
    cells = list(root.find("./diagram/mxGraphModel/root").findall("./mxCell"))  # type: ignore[union-attr]

    vertex_ids = {c.attrib["id"] for c in cells if c.attrib.get("vertex") == "1"}
    edge_ids = {c.attrib["id"] for c in cells if c.attrib.get("edge") == "1"}
    for table in state.tables:
        assert table.table_id in vertex_ids, f"missing vertex for {table.name}"
    for edge in state.table_edges:
        assert edge.edge_id in edge_ids, f"missing edge {edge.edge_id}"


def test_three_role_lanes_present() -> None:
    state = _state()
    xml = DrawioExporter().to_xml(state)
    assert 'value="Source"' in xml
    assert 'value="Intermediate"' in xml
    assert 'value="Output"' in xml
