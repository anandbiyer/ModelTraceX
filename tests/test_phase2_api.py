"""Phase 2 backend tests (P2-T1..T4): REST surface, SSE, column lineage, overrides.

Entirely offline: the ``get_provider`` dependency is overridden with a
``FakeProvider`` returning canned per-model JSON, so the orchestrator, the SSE
channel, and the projections all run with no network (SDD §15).
"""

from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient

from modeltracex.api import create_app, get_provider
from modeltracex.llm.fake import FakeProvider

# A two-model SAS project that stitches: m1 writes work.staging, m2 reads it.
_M1 = json.dumps(
    {
        "purpose": "Build the staging table from raw customer events.",
        "executive_summary": "Computes net amount per customer.",
        "input_tables": [
            {"name": "raw.customer_events", "columns": ["cust_id", "gross_amount", "tax_amount"]}
        ],
        "output_tables": [{"name": "work.staging", "columns": ["cust_id", "amount_net"]}],
        "calculations": [
            {"target": "work.staging.amount_net", "expression": "gross_amount - tax_amount"}
        ],
        "lineage_rows": [
            {
                "source_element": "raw.customer_events.gross_amount",
                "target_element": "work.staging.amount_net",
                "transformation_type": "derive",
            }
        ],
    }
)
_M2 = json.dumps(
    {
        "purpose": "Score customers from the staging table.",
        "executive_summary": "Aggregates net amounts into a score.",
        "input_tables": [{"name": "work.staging", "columns": ["cust_id", "amount_net"]}],
        "output_tables": [{"name": "mart.customer_scores", "columns": ["cust_id", "total_net"]}],
        "calculations": [
            {"target": "mart.customer_scores.total_net", "expression": "sum(amount_net)"}
        ],
        "lineage_rows": [
            {
                "source_element": "work.staging.amount_net",
                "target_element": "mart.customer_scores.total_net",
                "transformation_type": "aggregate",
            }
        ],
    }
)


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_provider] = lambda: FakeProvider(
        responses={"m1_build_staging": _M1, "m2_score": _M2}
    )
    return TestClient(app)


def _ingest_two(client: TestClient) -> str:
    run_id = client.post("/runs").json()["run_id"]
    resp = client.post(
        f"/runs/{run_id}/ingest",
        files=[
            (
                "files",
                (
                    "m1_build_staging.sas",
                    b"data work.staging; set raw.customer_events; run;",
                    "text/plain",
                ),
            ),
            (
                "files",
                (
                    "m2_score.sas",
                    b"data mart.customer_scores; set work.staging; run;",
                    "text/plain",
                ),
            ),
        ],
    )
    assert resp.status_code == 200, resp.text
    return run_id


def _analyze_and_wait(client: TestClient, run_id: str, timeout: float = 10.0) -> None:
    resp = client.post(f"/runs/{run_id}/analyze")
    assert resp.status_code == 200, resp.text
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = client.get(f"/runs/{run_id}").json()["status"]
        if status == "done":
            return
        assert status != "failed", client.get(f"/runs/{run_id}").json()
        time.sleep(0.02)
    raise AssertionError("analysis did not complete in time")


def _table_id(state: dict, name: str) -> str:
    return next(t["table_id"] for t in state["tables"] if t["name"] == name)


# --------------------------------------------------------------------------- #
# P2-T1 — REST routes: happy path + validation
# --------------------------------------------------------------------------- #


def test_create_ingest_lists_models(client: TestClient) -> None:
    run_id = _ingest_two(client)
    view = client.get(f"/runs/{run_id}").json()
    assert view["status"] == "ingested"
    models = client.post(
        f"/runs/{run_id}/ingest",
        data={"paste": "df = pd.read_csv('x'); df.to_csv('y')", "paste_filename": "extra.py"},
    ).json()
    assert models["files"] == 3
    langs = {m["language"] for m in models["models"]}
    assert "SAS" in langs and "Python" in langs


def test_ingest_requires_content(client: TestClient) -> None:
    run_id = client.post("/runs").json()["run_id"]
    assert client.post(f"/runs/{run_id}/ingest").status_code == 422


def test_estimate_has_no_llm_cost_but_returns_figure(client: TestClient) -> None:
    run_id = _ingest_two(client)
    est = client.post(f"/runs/{run_id}/estimate").json()
    assert est["models"] == 2
    assert est["tokens"] > 0
    assert est["est_cost"] >= 0.0
    assert len(est["per_model"]) == 2


def test_patch_language_override(client: TestClient) -> None:
    run_id = _ingest_two(client)
    resp = client.patch(
        f"/runs/{run_id}/models",
        json={"operations": [{"op": "set_language", "index": 0, "language": "Python"}]},
    )
    assert resp.status_code == 200
    m0 = resp.json()["models"][0]
    assert m0["language"] == "Python" and m0["language_overridden"] is True


def test_patch_merge_models(client: TestClient) -> None:
    run_id = _ingest_two(client)
    resp = client.patch(
        f"/runs/{run_id}/models",
        json={"operations": [{"op": "merge", "indices": [0, 1], "label": "combined"}]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["models"]) == 1
    assert body["models"][0]["label"] == "combined"
    assert len(body["models"][0]["files"]) == 2


def test_analyze_requires_ingest(client: TestClient) -> None:
    run_id = client.post("/runs").json()["run_id"]
    assert client.post(f"/runs/{run_id}/analyze").status_code == 422


def test_state_before_analyze_is_409(client: TestClient) -> None:
    run_id = _ingest_two(client)
    assert client.get(f"/runs/{run_id}/state").status_code == 409
    assert client.get(f"/runs/{run_id}/lineage").status_code == 409


def test_unknown_run_is_404(client: TestClient) -> None:
    assert client.get("/runs/nope").status_code == 404
    assert client.post("/runs/nope/estimate").status_code == 404


def test_full_run_state_and_export(client: TestClient) -> None:
    run_id = _ingest_two(client)
    _analyze_and_wait(client, run_id)
    state = client.get(f"/runs/{run_id}/state").json()
    assert len(state["models"]) == 2
    names = {t["name"] for t in state["tables"]}
    assert {"raw.customer_events", "work.staging", "mart.customer_scores"} <= names
    # work.staging is written by m1 and read by m2 -> Intermediate (cross-model stitch).
    staging = next(t for t in state["tables"] if t["name"] == "work.staging")
    assert staging["role"] == "Intermediate"
    # CSV export downloads.
    exp = client.get(f"/runs/{run_id}/exports/csv")
    assert exp.status_code == 200
    assert client.get(f"/runs/{run_id}/exports/bogus").status_code == 404


# --------------------------------------------------------------------------- #
# P2-T2 — SSE: per-model progress, partial results before completion
# --------------------------------------------------------------------------- #


def test_sse_streams_per_model_progress(client: TestClient) -> None:
    run_id = _ingest_two(client)
    client.post(f"/runs/{run_id}/analyze")
    events: list[dict] = []
    with client.stream("GET", f"/runs/{run_id}/events") as resp:
        for line in resp.iter_lines():
            if line.startswith("data:"):
                events.append(json.loads(line[len("data:") :].strip()))
                if events[-1].get("type") == "run_completed":
                    break

    model_events = [e for e in events if e.get("type") == "model"]
    assert model_events, events
    # progress is incremental: a 'started' event is seen with completed < total
    assert any(e["status"] == "started" and e["completed"] < e["total"] for e in model_events)
    completed = next(e for e in events if e.get("type") == "run_completed")
    assert completed["counts"]["models"] == 2


# --------------------------------------------------------------------------- #
# P2-T3 — column lineage: R4 expression home, lazy expand, no orphans
# --------------------------------------------------------------------------- #


def test_table_graph_and_pending_review(client: TestClient) -> None:
    run_id = _ingest_two(client)
    _analyze_and_wait(client, run_id)
    graph = client.get(f"/runs/{run_id}/lineage").json()
    assert graph["level"] == "table"
    assert graph["counts"]["tables"] == 3
    # every proposed edge (table- and column-level) is counted as pending review
    assert (
        graph["counts"]["pending_review"]
        == graph["counts"]["table_edges"] + graph["counts"]["column_edges"]
    )
    assert {n["data"]["role"] for n in graph["nodes"]} == {"Source", "Intermediate", "Output"}


def test_column_subgraph_expression_home_and_no_orphans(client: TestClient) -> None:
    run_id = _ingest_two(client)
    _analyze_and_wait(client, run_id)
    state = client.get(f"/runs/{run_id}/state").json()
    mart_id = _table_id(state, "mart.customer_scores")
    staging_id = _table_id(state, "work.staging")

    sub = client.get(f"/runs/{run_id}/lineage", params={"level": "column", "table": mart_id}).json()
    assert sub["level"] == "column"
    assert any(c["data"]["name"] == "total_net" for c in sub["columns"])

    edge = next(e for e in sub["column_edges"] if e["target"] == "mart.customer_scores.total_net")
    # R4: the expression's authoritative home is the column edge
    assert edge["data"]["expression"] == "sum(amount_net)"
    # collapsed neighbour resolves to its table id -> no orphan edge
    assert edge["source_table_id"] == staging_id
    assert edge["target_table_id"] == mart_id


def test_column_subgraph_unknown_table_404(client: TestClient) -> None:
    run_id = _ingest_two(client)
    _analyze_and_wait(client, run_id)
    resp = client.get(f"/runs/{run_id}/lineage", params={"level": "column", "table": "missing"})
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# P2-T4 — overrides: accept/reject/edit flips review_status, survives re-run
# --------------------------------------------------------------------------- #


def test_accept_edge_flips_review_status_and_counter(client: TestClient) -> None:
    run_id = _ingest_two(client)
    _analyze_and_wait(client, run_id)
    state = client.get(f"/runs/{run_id}/state").json()
    edge_id = state["table_edges"][0]["edge_id"]
    before = client.get(f"/runs/{run_id}/lineage").json()["counts"]["pending_review"]

    resp = client.post(
        f"/runs/{run_id}/overrides",
        json={"target": edge_id, "field": "review_status", "new": "Accepted"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["entity"]["review_status"] == "Accepted"
    assert body["pending_review"] == before - 1


def test_edit_table_role_flips_to_accepted(client: TestClient) -> None:
    run_id = _ingest_two(client)
    _analyze_and_wait(client, run_id)
    state = client.get(f"/runs/{run_id}/state").json()
    tid = _table_id(state, "work.staging")
    resp = client.post(
        f"/runs/{run_id}/overrides",
        json={"target": tid, "field": "role", "new": "Output"},
    )
    assert resp.status_code == 200
    entity = resp.json()["entity"]
    assert entity["role"] == "Output"
    # an edit curates the fact -> accepted (R9/D1)
    assert entity["review_status"] == "Accepted"


def test_override_unknown_target_404(client: TestClient) -> None:
    run_id = _ingest_two(client)
    _analyze_and_wait(client, run_id)
    resp = client.post(
        f"/runs/{run_id}/overrides",
        json={"target": "no_such_id", "field": "review_status", "new": "Accepted"},
    )
    assert resp.status_code == 404


def test_override_survives_rerun_by_id(client: TestClient) -> None:
    run_id = _ingest_two(client)
    _analyze_and_wait(client, run_id)
    state = client.get(f"/runs/{run_id}/state").json()
    edge_id = state["table_edges"][0]["edge_id"]
    client.post(
        f"/runs/{run_id}/overrides",
        json={"target": edge_id, "field": "review_status", "new": "Accepted"},
    )
    # re-run the analysis; the override must re-apply by stable id (SDD §9.3)
    _analyze_and_wait(client, run_id)
    state2 = client.get(f"/runs/{run_id}/state").json()
    edge = next(e for e in state2["table_edges"] if e["edge_id"] == edge_id)
    assert edge["review_status"] == "Accepted"
