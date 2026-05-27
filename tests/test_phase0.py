"""Phase 0 — Foundation tests (P0-T1 .. P0-T6).

All offline (FakeProvider only); no network, no real provider. These map 1:1 to
the Phase-0 testing activities in the Implementation Plan §4.2 and gate the
Phase-0 exit criterion (a schema-valid RunState persisted to SQLite).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from modeltracex import ids
from modeltracex.config import Settings
from modeltracex.llm.fake import FakeProvider
from modeltracex.llm.provider import LLMProvider, LLMResult, SecurityError, build_provider
from modeltracex.llm.schema import ModelExtraction
from modeltracex.llm.structured import SchemaValidationError, structured_call
from modeltracex.state import (
    Language,
    Override,
    ReviewStatus,
    RunState,
    SecurityMode,
    TableRole,
)
from modeltracex.store.db import RunStore, apply_overrides

FIXTURES = Path(__file__).parent / "fixtures"
MALFORMED = FIXTURES / "fake_provider" / "malformed"
PARTIAL = FIXTURES / "fake_provider" / "partial_failure"

# Two canned ModelExtraction responses forming a cross-model stitch project.
_M1 = json.dumps(
    {
        "purpose": "Build staging from raw events.",
        "input_tables": [{"name": "raw.customer_events", "columns": ["cust_id", "gross_amount"]}],
        "output_tables": [{"name": "work.staging", "columns": ["cust_id", "amount_net"]}],
        "lineage_rows": ["raw.customer_events.gross_amount -> work.staging.amount_net"],
    }
)
_M2 = json.dumps(
    {
        "purpose": "Score customers from staging.",
        "input_tables": [{"name": "work.staging", "columns": ["cust_id", "amount_net"]}],
        "output_tables": [{"name": "mart.customer_scores", "columns": ["cust_id", "total_net"]}],
        "lineage_rows": ["work.staging.amount_net -> mart.customer_scores.total_net"],
    }
)


def _stitch_state() -> RunState:
    from modeltracex.analysis.orchestrator import ModelInput, analyze_run

    provider = FakeProvider(responses={"m1_build_staging": _M1, "m2_score": _M2})
    inputs = [
        ModelInput(label="m1_build_staging", language=Language.SAS, source_files=["m1.sas"]),
        ModelInput(label="m2_score", language=Language.SAS, source_files=["m2.sas"]),
    ]
    return analyze_run(provider, inputs, run_id="run_test_0001")


# --------------------------------------------------------------------------- #
# P0-T1 — Schema / coercion: the malformed-LLM set recovers via validators
# --------------------------------------------------------------------------- #
_CASES = json.loads((MALFORMED / "expected.json").read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("filename, case", sorted(_CASES.items()))
def test_malformed_llm_recovers_via_coercion(filename: str, case: dict) -> None:
    raw = (MALFORMED / filename).read_text(encoding="utf-8")
    provider = FakeProvider(responses=raw)
    result = structured_call(provider, "sys", "user", ModelExtraction)

    # Coercible defects must recover WITHOUT consuming a retry (SDD §6.3).
    if case.get("recovers_without_retry"):
        assert result.attempts == 1

    if "normalized_input_tables" in case:
        got = [(t.name, list(t.columns)) for t in result.value.input_tables]
        exp = [(d["name"], list(d.get("columns", []))) for d in case["normalized_input_tables"]]
        assert got == exp
    if "normalized_lineage_rows" in case:
        got_l = [(r.source_element, r.target_element) for r in result.value.lineage_rows]
        exp_l = [
            (d["source_element"], d["target_element"]) for d in case["normalized_lineage_rows"]
        ]
        assert got_l == exp_l


def test_coercion_recovers_after_one_retry() -> None:
    # First reply is unparseable, second is valid → recovers on attempt 2.
    provider = FakeProvider(responses=["not json at all", '{"purpose": "ok"}'])
    result = structured_call(provider, "sys", "user", ModelExtraction)
    assert result.attempts == 2
    assert result.value.purpose == "ok"


def test_non_coercible_response_raises_after_retries() -> None:
    # The partial-failure fixture: a bare scalar can never be a ModelExtraction.
    raw = (PARTIAL / "always_invalid.json").read_text(encoding="utf-8")
    provider = FakeProvider(responses=raw)
    with pytest.raises(SchemaValidationError):
        structured_call(provider, "sys", "user", ModelExtraction, retries=2)


# --------------------------------------------------------------------------- #
# P0-T2 — Stable-ID determinism + alias canonicalization
# --------------------------------------------------------------------------- #
def test_table_id_is_deterministic_and_case_insensitive() -> None:
    assert ids.table_id("work.staging") == ids.table_id("work.staging")
    assert ids.table_id("work.staging") == ids.table_id("  WORK.STAGING  ")
    assert ids.table_id("work.staging") != ids.table_id("work.other")


def test_libname_alias_canonicalizes_to_one_id() -> None:
    assert ids.canonical_table_name("stg.events", {"stg": "work"}) == "work.events"
    assert ids.table_id("stg.events", {"stg": "work"}) == ids.table_id("work.events")


def test_model_id_is_order_independent_over_files() -> None:
    assert ids.model_id("m", ["a.sas", "b.sas"]) == ids.model_id("m", ["b.sas", "a.sas"])
    assert ids.model_id("m", ["a.sas"]) != ids.model_id("n", ["a.sas"])


def test_edge_and_rule_ids_are_deterministic() -> None:
    assert ids.table_edge_id("t_a", "t_b", "m_1", "derive") == ids.table_edge_id(
        "t_a", "t_b", "m_1", "derive"
    )
    assert ids.column_edge_id("a.x", "b.y", "m_1", "derive").startswith("ce_")
    assert ids.rule_id("t.col", "Validity", "non-null").startswith("dq_")


# --------------------------------------------------------------------------- #
# P0-T3 — Egress guard
# --------------------------------------------------------------------------- #
def test_egress_guard_blocks_external_provider_in_local_mode() -> None:
    cfg = Settings(provider="anthropic", security_mode=SecurityMode.LOCAL)
    with pytest.raises(SecurityError):
        build_provider(cfg)


def test_egress_guard_allows_fake_in_local_mode() -> None:
    cfg = Settings(provider="fake", security_mode=SecurityMode.LOCAL)
    provider = build_provider(cfg)
    assert provider.name == "fake"


def test_build_provider_returns_configured_provider_in_cloud_mode() -> None:
    assert (
        build_provider(Settings(provider="fake", security_mode=SecurityMode.CLOUD)).name == "fake"
    )
    # anthropic constructs lazily (no SDK / key needed until first call).
    assert (
        build_provider(Settings(provider="anthropic", security_mode=SecurityMode.CLOUD)).name
        == "anthropic"
    )


# --------------------------------------------------------------------------- #
# P0-T4 — Provider conformance harness (only FakeProvider runs in CI)
# --------------------------------------------------------------------------- #
def _ci_providers() -> list[LLMProvider]:
    return [FakeProvider(responses='{"purpose": "ok"}')]


@pytest.mark.parametrize("provider", _ci_providers(), ids=lambda p: p.name)
def test_provider_conformance(provider: LLMProvider) -> None:
    assert isinstance(provider, LLMProvider)
    res = provider.complete_json("sys", "user", ModelExtraction)
    assert isinstance(res, LLMResult)
    assert res.raw
    assert res.usage.tokens_in >= 0 and res.usage.tokens_out >= 0
    # And it drives the structured loop to a validated model.
    out = structured_call(provider, "sys", "user", ModelExtraction)
    assert isinstance(out.value, ModelExtraction)


# --------------------------------------------------------------------------- #
# P0-T5 — Store round-trip + override logged and re-applied by id
# --------------------------------------------------------------------------- #
def test_store_round_trips_runstate(tmp_path: Path) -> None:
    state = _stitch_state()
    store = RunStore(str(tmp_path / "runs.db"))
    store.save(state)
    assert store.load(state.run.run_id) == state
    # Flattened index is queryable.
    table_ids = store.entity_ids(state.run.run_id, "table")
    assert sorted(t.table_id for t in state.tables) == table_ids


def test_override_logged_and_reapplied_by_id() -> None:
    state = _stitch_state()
    store = RunStore(":memory:")
    store.save(state)

    target = state.tables[0]
    override = Override(
        target=target.table_id,
        field="review_status",
        old=target.review_status.value,
        new=ReviewStatus.ACCEPTED.value,
        timestamp="2026-05-26T00:00:00Z",
    )
    store.log_override(state.run.run_id, override)

    logged = store.overrides_for(state.run.run_id)
    assert len(logged) == 1 and logged[0].target == target.table_id

    applied = apply_overrides(state, logged)
    changed = next(t for t in applied.tables if t.table_id == target.table_id)
    assert changed.review_status == ReviewStatus.ACCEPTED.value


def test_stale_override_becomes_an_issue() -> None:
    state = _stitch_state()
    before = len(state.issues)
    applied = apply_overrides(
        state,
        [Override(target="t_does_not_exist", field="role", new="Output", timestamp="t")],
    )
    assert len(applied.issues) == before + 1
    assert "stale override" in applied.issues[-1].message


# --------------------------------------------------------------------------- #
# P0-T6 [EXIT] — FakeProvider E2E → schema-valid RunState persisted to SQLite
# --------------------------------------------------------------------------- #
def test_exit_fakeprovider_e2e_persists_schema_valid_runstate(tmp_path: Path) -> None:
    state = _stitch_state()

    # Cross-model stitch: work.staging is produced by m1 and consumed by m2 → one
    # Intermediate node; the source→intermediate→output path is complete.
    roles = {t.name: t.role for t in state.tables}
    assert roles["raw.customer_events"] is TableRole.SOURCE
    assert roles["work.staging"] is TableRole.INTERMEDIATE
    assert roles["mart.customer_scores"] is TableRole.OUTPUT
    assert len(state.table_edges) == 2

    # Persist to a real on-disk SQLite file and reload byte-for-byte.
    db_file = tmp_path / "exit.db"
    store = RunStore(str(db_file))
    store.save(state)
    assert db_file.exists()

    reloaded = store.load(state.run.run_id)
    assert reloaded == state
    # Reloaded blob is itself a valid RunState (re-validates without error).
    RunState.model_validate(reloaded.model_dump())
