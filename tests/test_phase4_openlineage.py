"""Phase 4 P4-T2 (EXIT) — OpenLineage exporter validation.

Asserts each emitted RunEvent has the structural shape OL catalogs require
(eventTime/eventType/producer/run.runId/job.namespace/job.name + inputs/outputs)
and that the columnLineage facet appears on the output dataset with the expected
``inputFields`` references. Loading into Marquez is the manual acceptance gate;
the unit gate validates against the structural contract in-process so CI stays
offline.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from modeltracex.analysis.orchestrator import ModelInput, analyze_run
from modeltracex.lineage.openlineage import NAMESPACE, OpenLineageExporter
from modeltracex.llm.fake import FakeProvider
from modeltracex.state import Language, RunState

_REQUIRED_TOP_LEVEL = {
    "eventTime",
    "eventType",
    "producer",
    "schemaURL",
    "run",
    "job",
    "inputs",
    "outputs",
}


def _state() -> RunState:
    src = json.dumps(
        {
            "purpose": "build staging",
            "input_tables": [{"name": "raw.events", "columns": ["amount", "cust_id"]}],
            "output_tables": [{"name": "work.staging", "columns": ["amount_net", "cust_id"]}],
            "calculations": [{"target": "work.staging.amount_net", "expression": "amount - tax"}],
            "lineage_rows": ["raw.events.amount -> work.staging.amount_net"],
        }
    )
    score = json.dumps(
        {
            "purpose": "score",
            "input_tables": [{"name": "work.staging", "columns": ["amount_net"]}],
            "output_tables": [{"name": "mart.scores", "columns": ["total"]}],
            "calculations": [{"target": "mart.scores.total", "expression": "sum(amount_net)"}],
            "lineage_rows": ["work.staging.amount_net -> mart.scores.total"],
        }
    )
    provider = FakeProvider(responses={"build": src, "score": score}, default="{}")
    inputs = [
        ModelInput(
            label="build",
            language=Language.SAS,
            source_files=["build.sas"],
            code="data work.staging;",
        ),
        ModelInput(
            label="score",
            language=Language.SAS,
            source_files=["score.sas"],
            code="data mart.scores;",
        ),
    ]
    return analyze_run(provider, inputs, run_id="ol_test")


def test_each_event_has_required_top_level_fields() -> None:
    state = _state()
    events = OpenLineageExporter().events(state)
    assert len(events) == len(state.models)
    for ev in events:
        missing = _REQUIRED_TOP_LEVEL - set(ev.keys())
        assert not missing, f"missing OL fields: {missing}"
        assert ev["eventType"] == "COMPLETE"
        assert ev["producer"].startswith("https://")
        assert ev["run"]["runId"] == "ol_test"
        assert ev["job"]["namespace"] == NAMESPACE
        # job.name = model_id, which is deterministic — non-empty.
        assert ev["job"]["name"]


def test_columnlineage_facet_resolves_input_field() -> None:
    state = _state()
    events = OpenLineageExporter().events(state)
    score_ev = next(e for e in events if any(o["name"] == "mart.scores" for o in e["outputs"]))
    out = next(o for o in score_ev["outputs"] if o["name"] == "mart.scores")
    facet = out["facets"]["columnLineage"]
    assert "fields" in facet
    total = facet["fields"]["total"]
    # Input field references the upstream staging column, not a free-form string.
    assert any(
        inp["name"] == "work.staging" and inp["field"] == "amount_net"
        for inp in total["inputFields"]
    )


def test_export_writes_one_event_per_line(tmp_path: Path) -> None:
    state = _state()
    [path] = OpenLineageExporter().export(state, str(tmp_path))
    lines = Path(path).read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == len(state.models)
    for line in lines:
        ev = json.loads(line)  # each line parses as JSON
        assert ev["run"]["runId"] == "ol_test"


def test_optional_schema_validation_against_jsonschema_if_available() -> None:
    """If ``jsonschema`` is installed (modeltracex[security]), validate the event shape."""
    jsonschema = pytest.importorskip("jsonschema")
    minimal_schema = {
        "type": "object",
        "required": sorted(_REQUIRED_TOP_LEVEL),
        "properties": {
            "eventTime": {"type": "string"},
            "eventType": {
                "type": "string",
                "enum": ["START", "COMPLETE", "FAIL", "ABORT", "RUNNING", "OTHER"],
            },
            "producer": {"type": "string", "format": "uri"},
            "schemaURL": {"type": "string", "format": "uri"},
            "run": {
                "type": "object",
                "required": ["runId"],
                "properties": {"runId": {"type": "string"}},
            },
            "job": {
                "type": "object",
                "required": ["namespace", "name"],
                "properties": {"namespace": {"type": "string"}, "name": {"type": "string"}},
            },
            "inputs": {"type": "array"},
            "outputs": {"type": "array"},
        },
    }
    for ev in OpenLineageExporter().events(_state()):
        jsonschema.validate(ev, minimal_schema)
