"""Phase 4 P4-T4 — retention scrub tests.

In ``security_mode=local`` with ``retain_source=False`` (the default), source
snippets the heuristic adapter captured for DQ inference are stripped from the
state before persistence. Cloud mode is unchanged. ``retain_source=True`` opts
out of scrubbing. Tests build the state by hand so they are independent of any
adapter's evidence-detection heuristics.
"""

from __future__ import annotations

from modeltracex.security import scrub_for_retention
from modeltracex.state import (
    Calculation,
    ColumnEdge,
    DQDimension,
    DQRule,
    ModelDoc,
    Provenance,
    RunMeta,
    RunState,
    SecurityMode,
    TransformationType,
    UsageKind,
    UsageObservation,
)
from modeltracex.store.db import RunStore


def _state(mode: SecurityMode = SecurityMode.LOCAL) -> RunState:
    """Hand-built state with every evidence-bearing field populated."""
    return RunState(
        run=RunMeta(
            run_id="ret_test",
            timestamp="2026-01-01T00:00:00+00:00",
            tool_version="2.0.0-dev",
            llm_provider="fake",
            llm_model="fake-1",
            security_mode=mode,
        ),
        models=[
            ModelDoc(
                model_id="m_1",
                label="m",
                language="SAS",  # type: ignore[arg-type]
                source_files=["m.sas"],
                calculations=[
                    Calculation(
                        target="mart.scores.total",
                        expression="sum(amount_net)",
                        source=Provenance.EXTRACTED,
                    )
                ],
            )
        ],
        column_edges=[
            ColumnEdge(
                edge_id="ce_1",
                source_element="work.staging.amount_net",
                target_element="mart.scores.total",
                model_id="m_1",
                transformation_type=TransformationType.AGGREGATE,
                expression="sum(amount_net)",
                source=Provenance.EXTRACTED,
            )
        ],
        usage_observations=[
            UsageObservation(
                element="raw.events.amount",
                usage_kind=UsageKind.DENOMINATOR,
                evidence="total = amount / 2;",
                model_id="m_1",
                source=Provenance.HEURISTIC,
            )
        ],
        dq_rules=[
            DQRule(
                rule_id="r_1",
                element="raw.events.amount",
                dimension=DQDimension.VALIDITY,
                rule_statement="non-zero divisor",
                code_evidence="total = amount / 2;",
            )
        ],
    )


def test_local_no_retain_clears_evidence_and_calc_expressions() -> None:
    state = _state()
    scrub_for_retention(state, retain_source=False)

    assert all(u.evidence == "" for u in state.usage_observations)
    assert all(r.code_evidence == "" for r in state.dq_rules)
    assert state.models[0].calculations[0].expression == ""
    assert state.column_edges[0].expression is None  # R4 home cleared too
    assert any("retention scrub" in i.message for i in state.issues)


def test_local_with_retain_source_keeps_evidence() -> None:
    state = _state()
    scrub_for_retention(state, retain_source=True)
    assert state.usage_observations[0].evidence == "total = amount / 2;"
    assert state.dq_rules[0].code_evidence == "total = amount / 2;"
    assert state.column_edges[0].expression == "sum(amount_net)"
    assert all("retention scrub" not in i.message for i in state.issues)


def test_cloud_mode_never_scrubs_even_if_retain_false() -> None:
    state = _state(mode=SecurityMode.CLOUD)
    scrub_for_retention(state, retain_source=False)
    assert state.usage_observations[0].evidence  # untouched
    assert state.column_edges[0].expression == "sum(amount_net)"


def test_persisted_state_in_local_mode_contains_no_source_snippets(tmp_path) -> None:
    state = _state()
    scrub_for_retention(state, retain_source=False)
    store = RunStore(str(tmp_path / "runs.db"))
    store.save(state)
    reloaded = store.load(state.run.run_id)
    assert reloaded is not None
    blob = reloaded.model_dump_json()
    # Neither the heuristic evidence nor the calc/edge expression survives.
    assert "amount / 2" not in blob
    assert "sum(amount_net)" not in blob
