"""Canonical Part C DQ inference table (Spec Part C, SDD §4.1/§10).

The single in-package source of truth mapping a ``UsageKind`` to its DQ
dimension, default severity, and rule statement. The synthetic corpus ships a
mirror at ``tests/fixtures/part_c_dq_table.json``; a test asserts the two stay in
sync so the coverage gate (S-13) and the engine never drift apart.
"""

from __future__ import annotations

from dataclasses import dataclass

from modeltracex.state import DQDimension, Severity, UsageKind


@dataclass(frozen=True)
class PartCRule:
    usage_kind: UsageKind
    dimension: DQDimension
    severity: Severity
    statement: str
    also_dimension: DQDimension | None = None


PART_C: dict[UsageKind, PartCRule] = {
    UsageKind.DENOMINATOR: PartCRule(
        UsageKind.DENOMINATOR,
        DQDimension.VALIDITY,
        Severity.HIGH,
        "Must be non-null and non-zero",
    ),
    UsageKind.JOIN_KEY: PartCRule(
        UsageKind.JOIN_KEY,
        DQDimension.UNIQUENESS,
        Severity.HIGH,
        "Uniqueness on key; referential integrity to joined table",
        also_dimension=DQDimension.CONSISTENCY,
    ),
    UsageKind.DATE_PARSE: PartCRule(
        UsageKind.DATE_PARSE,
        DQDimension.VALIDITY,
        Severity.MEDIUM,
        "Valid date; within plausible range",
    ),
    UsageKind.RANGE_FILTER: PartCRule(
        UsageKind.RANGE_FILTER,
        DQDimension.VALIDITY,
        Severity.MEDIUM,
        "Value within expected domain/range",
    ),
    UsageKind.AGGREGATED: PartCRule(
        UsageKind.AGGREGATED,
        DQDimension.COMPLETENESS,
        Severity.MEDIUM,
        "Completeness on the aggregation grain (no missing rows)",
    ),
    UsageKind.TYPE_CAST: PartCRule(
        UsageKind.TYPE_CAST,
        DQDimension.ACCURACY,
        Severity.MEDIUM,
        "Format/type conformance",
    ),
    UsageKind.EQUALITY_SET: PartCRule(
        UsageKind.EQUALITY_SET,
        DQDimension.VALIDITY,
        Severity.MEDIUM,
        "Domain/code-value validity (allowed values)",
    ),
    UsageKind.OUTPUT_MEASURE: PartCRule(
        UsageKind.OUTPUT_MEASURE,
        DQDimension.COMPLETENESS,
        Severity.MEDIUM,
        "Non-null; not all-zero/all-null",
    ),
    UsageKind.TIME_WINDOW: PartCRule(
        UsageKind.TIME_WINDOW,
        DQDimension.TIMELINESS,
        Severity.LOW,
        "Timeliness / freshness expectation",
    ),
    UsageKind.CROSS_SYSTEM_JOIN: PartCRule(
        UsageKind.CROSS_SYSTEM_JOIN,
        DQDimension.CONSISTENCY,
        Severity.MEDIUM,
        "Cross-system consistency",
    ),
}


__all__ = ["PartCRule", "PART_C"]
