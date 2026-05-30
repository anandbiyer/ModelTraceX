"""Phase 4D refined-Part-C: baseline DQ rules + cross-model dedup.

Covers the user-requested behavior:

1. **Every column gets a Completeness rule** by default (the baseline).
2. **id/key-shaped column names also get a Uniqueness rule**.
3. **date-shaped column names also get a Validity rule**.
4. **The same `(element, dimension)` from N models collapses to ONE rule** with
   ``model_ids = [m1, …, mN]`` so the per-model UI filter (P4D-5) can drill in.
5. **Heuristic observation-driven rules merge** with baselines via the same
   dedup, never duplicate.
6. **Role filter respected**: source/intermediate/output coverage is exhaustive
   by default but caller-tunable.
"""

from __future__ import annotations

from modeltracex.dq.baseline import baseline_rules_for_tables
from modeltracex.dq.engine import infer_rules
from modeltracex.state import (
    Column,
    Confidence,
    DQDimension,
    Provenance,
    Table,
    TableRole,
    UsageKind,
    UsageObservation,
)


def _tbl(
    table_id: str,
    name: str,
    role: TableRole,
    cols: list[str],
    produced_by: list[str] | None = None,
    consumed_by: list[str] | None = None,
) -> Table:
    return Table(
        table_id=table_id,
        name=name,
        role=role,
        produced_by=produced_by or [],
        consumed_by=consumed_by or [],
        columns=[Column(name=c, source=Provenance.HEURISTIC) for c in cols],
        source=Provenance.HEURISTIC,
    )


def test_completeness_emitted_for_every_column() -> None:
    tables = [_tbl("t1", "raw.customer", TableRole.SOURCE, ["cust_id", "name", "balance"])]
    rules = baseline_rules_for_tables(tables)
    # 3 Completeness + 1 Uniqueness (for cust_id) = 4 baseline rules.
    by_dim = {(r.element, r.dimension) for r in rules.values()}
    assert ("raw.customer.cust_id", DQDimension.COMPLETENESS) in by_dim
    assert ("raw.customer.name", DQDimension.COMPLETENESS) in by_dim
    assert ("raw.customer.balance", DQDimension.COMPLETENESS) in by_dim


def test_uniqueness_for_id_shaped_columns() -> None:
    tables = [_tbl("t1", "raw.t", TableRole.SOURCE, ["cust_id", "balance", "ID", "row_key"])]
    rules = baseline_rules_for_tables(tables)
    uniq = {r.element for r in rules.values() if r.dimension is DQDimension.UNIQUENESS}
    assert uniq == {"raw.t.cust_id", "raw.t.ID", "raw.t.row_key"}, uniq


def test_validity_for_date_shaped_columns() -> None:
    tables = [_tbl("t1", "raw.t", TableRole.SOURCE, ["asof_date", "balance", "txn_dt", "ts"])]
    rules = baseline_rules_for_tables(tables)
    dates = {r.element for r in rules.values() if r.dimension is DQDimension.VALIDITY}
    assert dates == {"raw.t.asof_date", "raw.t.txn_dt", "raw.t.ts"}, dates


def test_shared_column_dedups_with_model_attribution() -> None:
    """Two tables, same column, both produced_by m1 and consumed_by m2.

    Refined Part C: the (element, dimension) collapses to ONE rule with
    model_ids=[m1, m2] — the cross-model visibility the user requested.
    """
    tables = [
        _tbl(
            "t1",
            "raw.customer",
            TableRole.SOURCE,
            ["cust_id"],
            produced_by=["m1"],
            consumed_by=["m2"],
        ),
        _tbl(
            "t2",
            "raw.customer",
            TableRole.SOURCE,
            ["cust_id"],
            produced_by=["m1"],
            consumed_by=["m2"],
        ),
    ]
    rules = baseline_rules_for_tables(tables)
    completeness = [r for r in rules.values() if r.dimension is DQDimension.COMPLETENESS]
    assert len(completeness) == 1
    assert set(completeness[0].model_ids) == {"m1", "m2"}


def test_observation_and_baseline_merge_via_engine() -> None:
    """An observation-driven rule for the same (element, dimension) as a
    baseline rule must collapse — not duplicate. The engine's `_emit` dedup
    keys on (element, dimension, statement). When the baseline statement
    "Non-null" and the observation's Part-C statement differ, they're
    different rules; if they match (e.g. OUTPUT_MEASURE's "Non-null; not
    all-zero/all-null"), they merge."""
    tables = [_tbl("t1", "mart.scores", TableRole.OUTPUT, ["score"], produced_by=["m1"])]
    observations = [
        UsageObservation(
            element="mart.scores.score",
            usage_kind=UsageKind.OUTPUT_MEASURE,
            evidence="score = ...; keep score",
            model_id="m1",
            source=Provenance.HEURISTIC,
            confidence=Confidence.HIGH,
        )
    ]
    rules = infer_rules(observations, tables=tables)
    # Completeness rules for `mart.scores.score`: at most 2 (baseline + observation
    # if their statements differ). At minimum 1.
    completeness_for_score = [
        r
        for r in rules
        if r.dimension is DQDimension.COMPLETENESS and r.element == "mart.scores.score"
    ]
    assert completeness_for_score, "no Completeness rule emitted for the output column"
    # The observation's model_id should appear on at least one Completeness rule.
    assert any("m1" in r.model_ids for r in completeness_for_score)


def test_role_filter_excludes_source_tables() -> None:
    tables = [
        _tbl("s1", "raw.customer", TableRole.SOURCE, ["cust_id"]),
        _tbl("o1", "mart.scores", TableRole.OUTPUT, ["score"]),
    ]
    rules = baseline_rules_for_tables(tables, include_roles=("Output",))
    elements = {r.element for r in rules.values()}
    assert "raw.customer.cust_id" not in elements
    assert "mart.scores.score" in elements


def test_attribution_added_from_produced_consumed_after_dedup() -> None:
    """A rule should pick up model_ids from `produced_by ∪ consumed_by` of its
    element's owning table even when the rule was authored by only one model.

    The chained pack from the live UAT: `cust_id` lives in `raw_source.csv`,
    consumed_by every model in the chain. Without this attribution, the rule
    would only carry one model_id — the per-model filter would hide it for the
    other 9 models even though they touch it."""
    tables = [
        _tbl(
            "t1",
            "raw.events",
            TableRole.SOURCE,
            ["amount"],
            consumed_by=["m1", "m2", "m3"],
        )
    ]
    obs = [
        UsageObservation(
            element="raw.events.amount",
            usage_kind=UsageKind.DENOMINATOR,
            evidence="x / raw.events.amount",
            model_id="m1",  # only m1 authored the observation
            source=Provenance.HEURISTIC,
            confidence=Confidence.HIGH,
        )
    ]
    rules = infer_rules(obs, tables=tables)
    denom_rules = [
        r for r in rules if r.dimension is DQDimension.VALIDITY and "amount" in r.element
    ]
    assert denom_rules, "denominator rule not emitted"
    assert set(denom_rules[0].model_ids) >= {"m1", "m2", "m3"}, (
        f"expected cross-model attribution from consumed_by; got {denom_rules[0].model_ids}"
    )
