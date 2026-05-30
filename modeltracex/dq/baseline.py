"""Baseline DQ rules — one rule per column per dimension (Phase 4D refined Part C).

The deterministic, usage-driven inference in ``engine.py`` only emits rules
when an adapter observes a specific Part C trigger (denominator, GROUP BY,
date-parse, …). For files that don't exercise those patterns — e.g. synthetic
generators or models that compute everything inline without filters — the DQ
register comes out empty even though the *output columns* of the model clearly
deserve quality expectations.

This module adds **baseline rules per column**:

- ``Completeness · "Non-null"`` for every column.
- ``Uniqueness · "Unique identifier"`` for ``_id`` / ``_key`` / ``^id$`` /
  ``^key$`` shaped names (heuristic).
- ``Validity · "Valid date; within plausible range"`` for ``_dt`` / ``_date`` /
  ``^date_`` shaped names.

Rules emitted here share the same ``rule_id`` scheme (``element + dimension +
statement``) and the same ``_emit`` dedup path as observation-driven rules, so
the same column from N models collapses to one rule with ``model_ids = [m1, …,
mN]`` for free. Population of ``model_ids`` from ``Table.produced_by ∪
consumed_by`` is the caller's responsibility — see ``infer_rules``.
"""

from __future__ import annotations

import re

from modeltracex import ids
from modeltracex.state import (
    Confidence,
    DQDimension,
    DQRule,
    Provenance,
    RuleStatus,
    Severity,
    Table,
)

_ID_RX = re.compile(r"(?:^|_)(id|key|sk|pk|uuid)(?:$|_)", re.IGNORECASE)
_DATE_RX = re.compile(r"(?:^|_)(date|dt|datetime|timestamp|ts|asof)(?:$|_)", re.IGNORECASE)


def _looks_like_id(col_name: str) -> bool:
    return bool(_ID_RX.search(col_name))


def _looks_like_date(col_name: str) -> bool:
    return bool(_DATE_RX.search(col_name))


def _emit_baseline(
    rules: dict[str, DQRule],
    element: str,
    dimension: DQDimension,
    severity: Severity,
    statement: str,
    confidence: Confidence,
    model_ids: list[str],
) -> None:
    """Dedup-aware emit that mirrors ``engine._emit`` but merges ``model_ids``."""
    rid = ids.rule_id(element, dimension.value, statement)
    existing = rules.get(rid)
    if existing is not None:
        for mid in model_ids:
            if mid and mid not in existing.model_ids:
                existing.model_ids.append(mid)
        return
    rules[rid] = DQRule(
        rule_id=rid,
        element=element,
        dimension=dimension,
        rule_statement=statement,
        rationale="baseline data-element expectation",
        code_evidence="",
        severity=severity,
        source=Provenance.HEURISTIC,
        confidence=confidence,
        status=RuleStatus.PROPOSED,
        model_ids=[mid for mid in model_ids if mid],
    )


def baseline_rules_for_tables(
    tables: list[Table],
    *,
    include_roles: tuple[str, ...] = ("Source", "Intermediate", "Output"),
) -> dict[str, DQRule]:
    """Emit baseline rules per column for every table whose role is in scope.

    Returns a dict keyed by ``rule_id`` so callers can merge with the
    observation-driven map from ``engine._emit`` and let dedup happen at
    rule-id level. Caller passes the per-table model attribution; we read it
    off ``Table.produced_by ∪ consumed_by`` (every model that *touches* the
    column, not just the one that authored the regex hit).
    """
    rules: dict[str, DQRule] = {}
    for table in tables:
        if table.role.value not in include_roles:
            continue
        touching_models = list(dict.fromkeys([*table.produced_by, *table.consumed_by]))
        for column in table.columns:
            element = f"{table.name}.{column.name}"
            # Completeness — every column gets a non-null expectation.
            _emit_baseline(
                rules,
                element,
                DQDimension.COMPLETENESS,
                Severity.MEDIUM,
                "Non-null",
                Confidence.MEDIUM,
                touching_models,
            )
            # Uniqueness — id-shaped names are presumed keys (escalate severity).
            if _looks_like_id(column.name):
                _emit_baseline(
                    rules,
                    element,
                    DQDimension.UNIQUENESS,
                    Severity.HIGH,
                    "Unique identifier",
                    Confidence.HIGH,
                    touching_models,
                )
            # Validity — date-shaped names get a date-range expectation.
            if _looks_like_date(column.name):
                _emit_baseline(
                    rules,
                    element,
                    DQDimension.VALIDITY,
                    Severity.MEDIUM,
                    "Valid date; within plausible range",
                    Confidence.MEDIUM,
                    touching_models,
                )
    return rules


def merge_model_attribution(rules: list[DQRule], tables: list[Table]) -> list[DQRule]:
    """Add models that touch a rule's element-table to the rule's ``model_ids``.

    Observation-driven rules currently carry only the *authoring* model
    (the one whose adapter saw the regex hit). For DQ-tab cross-model
    visibility (P4D-5 + refined Part C), we extend each rule's ``model_ids``
    with every model that produces or consumes the element's owning table.
    Returns the input list (mutated in place) for convenient chaining.
    """
    table_models: dict[str, list[str]] = {
        t.name: list(dict.fromkeys([*t.produced_by, *t.consumed_by])) for t in tables
    }
    for rule in rules:
        # `element` is shaped `table.column`; strip the last segment to find the table.
        if "." not in rule.element:
            continue
        table_name = rule.element.rsplit(".", 1)[0]
        for mid in table_models.get(table_name, ()):
            if mid and mid not in rule.model_ids:
                rule.model_ids.append(mid)
    return rules


__all__ = ["baseline_rules_for_tables", "merge_model_attribution"]
