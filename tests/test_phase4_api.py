"""Phase 4 API surface — /config + per-run security_mode + new export kinds.

Covers P4-6 (per-run security UI surface) and the OpenLineage/draw.io export
routes wired into ``/runs/{id}/exports/{kind}``. The handler ceiling for cloud
mode comes from ``allowed_security_modes`` on Settings (NFR-2 / D6).
"""

from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient

from modeltracex.api import create_app, get_provider
from modeltracex.config import Settings
from modeltracex.llm.fake import FakeProvider
from modeltracex.state import SecurityMode

_M1 = json.dumps(
    {
        "purpose": "Build the staging table.",
        "input_tables": [{"name": "raw.customer_events", "columns": ["cust_id", "amount"]}],
        "output_tables": [{"name": "work.staging", "columns": ["cust_id", "amount_net"]}],
        "calculations": [{"target": "work.staging.amount_net", "expression": "amount - 0"}],
        "lineage_rows": [
            {
                "source_element": "raw.customer_events.amount",
                "target_element": "work.staging.amount_net",
                "transformation_type": "derive",
            }
        ],
    }
)


@pytest.fixture
def client() -> TestClient:
    # provider="fake" so the post-PATCH egress-guard rebuild stays non-egress.
    app = create_app(settings=Settings(provider="fake"))
    app.dependency_overrides[get_provider] = lambda: FakeProvider(responses={"m": _M1}, default=_M1)
    return TestClient(app)


@pytest.fixture
def local_only_client() -> TestClient:
    cfg = Settings(
        provider="fake",
        allowed_security_modes=[SecurityMode.LOCAL],
        security_mode=SecurityMode.LOCAL,
    )
    app = create_app(settings=cfg)
    app.dependency_overrides[get_provider] = lambda: FakeProvider(responses={"m": _M1}, default=_M1)
    return TestClient(app)


def _ingest_one(client: TestClient) -> str:
    run_id = client.post("/runs").json()["run_id"]
    resp = client.post(
        f"/runs/{run_id}/ingest",
        files=[
            ("files", ("m.sas", b"data work.staging; set raw.customer_events; run;", "text/plain"))
        ],
    )
    assert resp.status_code == 200
    return run_id


def _wait_done(client: TestClient, run_id: str) -> None:
    deadline = time.time() + 10.0
    while time.time() < deadline:
        st = client.get(f"/runs/{run_id}").json()["status"]
        if st == "done":
            return
        assert st != "failed"
        time.sleep(0.02)
    raise AssertionError("did not complete")


# --------------------------------------------------------------------------- #
# /config + per-run security_mode (D6)
# --------------------------------------------------------------------------- #


def test_config_endpoint_lists_allowed_modes(client: TestClient) -> None:
    cfg = client.get("/config").json()
    assert cfg["security_mode"] in ("cloud", "local")
    assert set(cfg["allowed_security_modes"]) <= {"cloud", "local"}
    assert isinstance(cfg["retain_source"], bool)


def test_patch_security_mode_within_allowed_set(client: TestClient) -> None:
    run_id = _ingest_one(client)
    resp = client.patch(f"/runs/{run_id}/security", json={"security_mode": "local"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["security_mode"] == "local"


def test_patch_security_mode_rejects_disallowed(local_only_client: TestClient) -> None:
    run_id = _ingest_one(local_only_client)
    resp = local_only_client.patch(f"/runs/{run_id}/security", json={"security_mode": "cloud"})
    assert resp.status_code == 422
    assert "allowed" in resp.json()["detail"]


def test_run_in_local_mode_persists_security_mode_on_runmeta(client: TestClient) -> None:
    run_id = _ingest_one(client)
    client.patch(f"/runs/{run_id}/security", json={"security_mode": "local"})
    client.post(f"/runs/{run_id}/analyze")
    _wait_done(client, run_id)
    state = client.get(f"/runs/{run_id}/state").json()
    assert state["run"]["security_mode"] == "local"


# --------------------------------------------------------------------------- #
# Phase 4 export kinds (OL + draw.io)
# --------------------------------------------------------------------------- #


def test_openlineage_export(client: TestClient) -> None:
    run_id = _ingest_one(client)
    client.post(f"/runs/{run_id}/analyze")
    _wait_done(client, run_id)
    resp = client.get(f"/runs/{run_id}/exports/openlineage")
    assert resp.status_code == 200
    lines = resp.content.decode("utf-8").strip().splitlines()
    assert lines and all(json.loads(line)["run"]["runId"] == run_id for line in lines)


def test_drawio_export(client: TestClient) -> None:
    run_id = _ingest_one(client)
    client.post(f"/runs/{run_id}/analyze")
    _wait_done(client, run_id)
    resp = client.get(f"/runs/{run_id}/exports/drawio")
    assert resp.status_code == 200
    assert b"<mxfile" in resp.content
    assert b"mxGraphModel" in resp.content
