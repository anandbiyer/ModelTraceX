"""Phase 4D-P2 lineage polish — `Column.control_status` derivation.

Asserts the five-state heuristic in ``_derive_control_status``:

1. Accepted DQ rule → Controlled
2. Rejected DQ rule → Dissented (precedence over Controlled)
3. No DQ acceptance but the column participates in a column edge → Sourced
4. Output-role column with no lineage edge → Not Sourced
5. Everything else → Not Controlled

Tests build a state by hand so they don't depend on adapter heuristics or
the LLM.
"""

from __future__ import annotations

from modeltracex.analysis.orchestrator import _derive_control_status
from modeltracex.state import (
    Column,
    ColumnControlStatus,
    ColumnEdge,
    DQDimension,
    DQRule,
    Provenance,
    RuleStatus,
    RunMeta,
    RunState,
    Severity,
    Table,
    TableRole,
    TransformationType,
)


def _state(
    *,
    tables: list[Table],
    column_edges: list[ColumnEdge] | None = None,
    dq_rules: list[DQRule] | None = None,
) -> RunState:
    return RunState(
        run=RunMeta(
            run_id="r",
            timestamp="2026-01-01T00:00:00+00:00",
            tool_version="v",
            llm_provider="fake",
            llm_model="fake",
        ),
        tables=tables,
        column_edges=column_edges or [],
        dq_rules=dq_rules or [],
    )


def _tbl(
    name: str, role: TableRole, cols: list[str], *, produced_by: list[str] | None = None
) -> Table:
    return Table(
        table_id=f"t_{name}",
        name=name,
        role=role,
        produced_by=produced_by or [],
        columns=[Column(name=c, source=Provenance.HEURISTIC) for c in cols],
        source=Provenance.HEURISTIC,
    )


def _rule(element: str, status: RuleStatus) -> DQRule:
    return DQRule(
        rule_id=f"r_{element}_{status.value}",
        element=element,
        dimension=DQDimension.COMPLETENESS,
        rule_statement="Non-null",
        severity=Severity.MEDIUM,
        status=status,
    )


def _edge(source: str, target: str) -> ColumnEdge:
    return ColumnEdge(
        edge_id=f"e_{source}_{target}",
        source_element=source,
        target_element=target,
        model_id="m",
        transformation_type=TransformationType.DERIVE,
        source=Provenance.EXTRACTED,
    )


def _status(state: RunState, element: str) -> ColumnControlStatus | None:
    table_name, col_name = element.rsplit(".", 1)
    for t in state.tables:
        if t.name == table_name:
            for c in t.columns:
                if c.name == col_name:
                    return c.control_status
    return None


def test_accepted_dq_rule_marks_column_controlled() -> None:
    state = _state(
        tables=[_tbl("raw.customer", TableRole.SOURCE, ["cust_id"])],
        dq_rules=[_rule("raw.customer.cust_id", RuleStatus.ACCEPTED)],
    )
    _derive_control_status(state)
    assert _status(state, "raw.customer.cust_id") is ColumnControlStatus.CONTROLLED


def test_rejected_rule_takes_precedence_over_accepted() -> None:
    state = _state(
        tables=[_tbl("raw.t", TableRole.SOURCE, ["x"])],
        dq_rules=[
            _rule("raw.t.x", RuleStatus.ACCEPTED),
            _rule("raw.t.x", RuleStatus.REJECTED),
        ],
    )
    _derive_control_status(state)
    assert _status(state, "raw.t.x") is ColumnControlStatus.DISSENTED


def test_proposed_only_rule_does_not_promote_to_controlled() -> None:
    state = _state(
        tables=[_tbl("raw.t", TableRole.SOURCE, ["x"])],
        dq_rules=[_rule("raw.t.x", RuleStatus.PROPOSED)],
    )
    _derive_control_status(state)
    # No lineage edge either, source role → Not Controlled.
    assert _status(state, "raw.t.x") is ColumnControlStatus.NOT_CONTROLLED


def test_column_edge_participation_marks_sourced() -> None:
    state = _state(
        tables=[
            _tbl("raw.t", TableRole.SOURCE, ["amount"]),
            _tbl("mart.s", TableRole.OUTPUT, ["total"]),
        ],
        column_edges=[_edge("raw.t.amount", "mart.s.total")],
    )
    _derive_control_status(state)
    assert _status(state, "raw.t.amount") is ColumnControlStatus.SOURCED
    assert _status(state, "mart.s.total") is ColumnControlStatus.SOURCED


def test_output_column_without_lineage_is_not_sourced() -> None:
    state = _state(tables=[_tbl("mart.s", TableRole.OUTPUT, ["orphan"])])
    _derive_control_status(state)
    assert _status(state, "mart.s.orphan") is ColumnControlStatus.NOT_SOURCED


def test_default_fallback_for_isolated_source_column() -> None:
    state = _state(tables=[_tbl("raw.t", TableRole.SOURCE, ["lonely"])])
    _derive_control_status(state)
    assert _status(state, "raw.t.lonely") is ColumnControlStatus.NOT_CONTROLLED


def test_controlled_wins_over_sourced() -> None:
    """A column with both an accepted rule AND lineage edges is Controlled."""
    state = _state(
        tables=[
            _tbl("raw.t", TableRole.SOURCE, ["x"]),
            _tbl("mart.s", TableRole.OUTPUT, ["y"]),
        ],
        column_edges=[_edge("raw.t.x", "mart.s.y")],
        dq_rules=[_rule("raw.t.x", RuleStatus.ACCEPTED)],
    )
    _derive_control_status(state)
    assert _status(state, "raw.t.x") is ColumnControlStatus.CONTROLLED
    assert _status(state, "mart.s.y") is ColumnControlStatus.SOURCED
