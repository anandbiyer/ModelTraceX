"""DQ engine — deterministic Part C subset (SDD §10, Spec Part C).

Phase 1 ships only the **heuristic mapper**: each ``UsageObservation`` from an
adapter maps through the Part C table to one (or two) ``DQRule``s, deterministic,
``source=H``, ``confidence=High``, ``status=Proposed``, carrying the triggering
code snippet as evidence (FR-6.3). The LLM proposer (E/I, review-required) is
deferred to Phase 3 (P3-8).

Rules are deduped by stable ``rule_id`` (element + dimension + statement), so the
same signal observed in multiple chunks/models yields one rule.
"""

from __future__ import annotations

from modeltracex import ids
from modeltracex.dq.rules_table import PART_C
from modeltracex.state import (
    Confidence,
    DQDimension,
    DQRule,
    Provenance,
    RuleStatus,
    Severity,
    UsageObservation,
)


def _emit(
    rules: dict[str, DQRule],
    element: str,
    dimension: DQDimension,
    severity: Severity,
    statement: str,
    usage_kind: str,
    evidence: str,
) -> None:
    rid = ids.rule_id(element, dimension.value, statement)
    if rid in rules:
        return
    rules[rid] = DQRule(
        rule_id=rid,
        element=element,
        dimension=dimension,
        rule_statement=statement,
        rationale=f"element used as {usage_kind}",
        code_evidence=evidence,
        severity=severity,
        source=Provenance.HEURISTIC,
        confidence=Confidence.HIGH,
        status=RuleStatus.PROPOSED,
    )


def infer_rules(usages: list[UsageObservation]) -> list[DQRule]:
    """Map usage observations to deduped, evidence-backed DQ rules (Part C)."""
    rules: dict[str, DQRule] = {}
    for u in usages:
        rule = PART_C.get(u.usage_kind)
        if rule is None:
            continue
        _emit(
            rules,
            u.element,
            rule.dimension,
            rule.severity,
            rule.statement,
            u.usage_kind.value,
            u.evidence,
        )
        if rule.also_dimension is not None:
            _emit(
                rules,
                u.element,
                rule.also_dimension,
                rule.severity,
                rule.statement,
                u.usage_kind.value,
                u.evidence,
            )
    return list(rules.values())


__all__ = ["infer_rules"]
