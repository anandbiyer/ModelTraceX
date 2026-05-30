"""DQ engine — deterministic Part C subset (SDD §10, Spec Part C).

Phase 1 ships only the **heuristic mapper**: each ``UsageObservation`` from an
adapter maps through the Part C table to one (or two) ``DQRule``s, deterministic,
``source=H``, ``confidence=High``, ``status=Proposed``, carrying the triggering
code snippet as evidence (FR-6.3). The LLM proposer (E/I, review-required) is
deferred to Phase 3 (P3-8).

Rules are deduped by stable ``rule_id`` (element + dimension + statement), so the
same signal observed in multiple chunks/models yields one rule.

Phase 4D refined-Part-C extension: if the caller passes the run's ``tables``,
the engine ALSO emits **baseline rules per column** (Completeness for every
column; Uniqueness for id-shaped names; Validity for date-shaped names). These
share the same dedup path so an observation-driven rule and the baseline rule
for the same ``(element, dimension)`` collapse to one. After dedup, every rule's
``model_ids`` is augmented with all models that produce or consume the rule's
table — surfacing cross-model attribution required by the per-model DQ filter.
"""

from __future__ import annotations

from modeltracex import ids
from modeltracex.dq.baseline import baseline_rules_for_tables, merge_model_attribution
from modeltracex.dq.rules_table import PART_C
from modeltracex.state import (
    Confidence,
    DQDimension,
    DQRule,
    Provenance,
    RuleStatus,
    Severity,
    Table,
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
    model_id: str,
) -> None:
    rid = ids.rule_id(element, dimension.value, statement)
    existing = rules.get(rid)
    if existing is not None:
        # Same rule triggered by another model — track that model in `model_ids`
        # so the UI's per-model filter (Phase 4D) sees both.
        if model_id and model_id not in existing.model_ids:
            existing.model_ids.append(model_id)
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
        model_ids=[model_id] if model_id else [],
    )


def infer_rules(
    usages: list[UsageObservation],
    *,
    tables: list[Table] | None = None,
) -> list[DQRule]:
    """Map usage observations + (optional) per-column baseline to deduped DQ rules.

    When ``tables`` is supplied, the refined-Part-C extension fires:

    1. Baseline rules are emitted via ``baseline_rules_for_tables`` (one per
       column per applicable dimension).
    2. Observation-driven rules are merged in via the same ``_emit`` dedup,
       so a column with both a baseline ``Completeness`` rule and an
       observation-driven ``Completeness`` rule (from e.g. an output_measure
       observation) collapses to one rule.
    3. Every rule's ``model_ids`` is augmented from ``produced_by ∪ consumed_by``
       of its element's owning table so cross-model attribution is complete.
    """
    rules: dict[str, DQRule] = baseline_rules_for_tables(tables) if tables is not None else {}
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
            u.model_id,
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
                u.model_id,
            )
    out = list(rules.values())
    if tables is not None:
        merge_model_attribution(out, tables)
    return out


__all__ = ["infer_rules"]
