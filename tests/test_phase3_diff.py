"""Phase 3 diff tests (P3-T4): empty diff on unchanged re-run; precise deltas;
override survives a re-run by id (SDD §9.3, NFR-4)."""

from __future__ import annotations

import json

from modeltracex import ids
from modeltracex.analysis.orchestrator import ModelInput, analyze_run
from modeltracex.llm.fake import FakeProvider
from modeltracex.state import Language, Override, TableRole
from modeltracex.store.db import apply_overrides
from modeltracex.store.diff import diff_runs

_A = json.dumps(
    {
        "input_tables": [{"name": "raw.events", "columns": ["id", "amt"]}],
        "output_tables": [{"name": "work.staging", "columns": ["id", "net"]}],
        "lineage_rows": [
            {"source_element": "raw.events.amt", "target_element": "work.staging.net"}
        ],
    }
)
_B = json.dumps(
    {
        "input_tables": [{"name": "work.staging", "columns": ["id", "net"]}],
        "output_tables": [{"name": "mart.scores", "columns": ["id", "score"]}],
        "lineage_rows": [
            {"source_element": "work.staging.net", "target_element": "mart.scores.score"}
        ],
    }
)


def _provider() -> FakeProvider:
    return FakeProvider(responses={"alpha": _A, "beta": _B})


def _inputs() -> list[ModelInput]:
    return [
        ModelInput(
            label="alpha", language=Language.SAS, source_files=["alpha.sas"], code="data x;"
        ),
        ModelInput(label="beta", language=Language.SAS, source_files=["beta.sas"], code="data y;"),
    ]


def test_unchanged_rerun_is_empty_diff() -> None:
    a = analyze_run(_provider(), _inputs(), run_id="A")
    b = analyze_run(_provider(), _inputs(), run_id="B")
    d = diff_runs(a, b)
    assert d.is_empty(), [(x.kind, x.added, x.removed, x.changed) for x in d.deltas]


def test_precise_deltas_when_a_model_is_removed() -> None:
    a = analyze_run(_provider(), _inputs(), run_id="A")
    b = analyze_run(_provider(), _inputs()[:1], run_id="B")  # drop beta
    d = diff_runs(a, b)
    model_delta = d.delta("model")
    assert model_delta.removed == [ids.model_id("beta", ["beta.sas"])]
    # beta's output table (mart.scores) disappears too.
    assert any("mart.scores" for _ in d.delta("table").removed)
    assert d.delta("table").removed  # at least the dropped model's exclusive table


def test_role_change_shows_changed_table() -> None:
    a = analyze_run(_provider(), _inputs(), run_id="A")
    b = a.model_copy(deep=True)
    b.run.run_id = "B"
    staging = next(t for t in b.tables if t.name == "work.staging")
    staging.role = TableRole.OUTPUT
    d = diff_runs(a, b)
    assert d.delta("table").changed == [staging.table_id]
    assert d.delta("model").is_empty()


def test_override_survives_rerun_by_id() -> None:
    a = analyze_run(_provider(), _inputs(), run_id="A")
    edge_id = a.table_edges[0].edge_id
    override = Override(
        target=edge_id, field="review_status", old="Proposed", new="Accepted", timestamp="t"
    )
    # Re-run, then re-apply the logged override by id.
    b = analyze_run(_provider(), _inputs(), run_id="B")
    b2 = apply_overrides(b, [override])
    edge = next(e for e in b2.table_edges if e.edge_id == edge_id)
    assert edge.review_status.value == "Accepted"
