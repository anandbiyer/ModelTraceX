"""Phase 3 DQ proposer tests (P3-T6): LLM proposals merge with heuristic by
(element, dimension); relational rules populate related_elements (R6)."""

from __future__ import annotations

import json

from modeltracex.dq.engine import infer_rules
from modeltracex.dq.proposer import infer_rules_with_proposals, propose_rules
from modeltracex.llm.fake import FakeProvider
from modeltracex.state import (
    Confidence,
    DQDimension,
    Provenance,
    RuleStatus,
    UsageKind,
    UsageObservation,
)


def _usages() -> list[UsageObservation]:
    return [
        UsageObservation(
            element="mart.scores.score",
            usage_kind=UsageKind.OUTPUT_MEASURE,
            evidence="score = ...",
            model_id="m",
            source=Provenance.HEURISTIC,
        ),
        UsageObservation(
            element="raw.cust.cust_id",
            usage_kind=UsageKind.JOIN_KEY,
            evidence="merge by cust_id",
            model_id="m",
            source=Provenance.HEURISTIC,
        ),
    ]


# A proposal that (1) duplicates a heuristic (element, dimension) to enrich it with a
# relational sibling, and (2) adds a genuinely new (element, dimension).
_PROPOSALS = json.dumps(
    {
        "proposals": [
            {
                "element": "raw.cust.cust_id",
                "dimension": "Consistency",
                "rule_statement": "cust_id must reconcile across systems",
                "severity": "High",
                "related_elements": ["raw.txn.cust_id"],
            },
            {
                "element": "mart.scores.score",
                "dimension": "Accuracy",
                "rule_statement": "score must be within model output bounds",
                "severity": "Medium",
                "related_elements": [],
            },
        ]
    }
)


def test_proposer_returns_typed_proposals() -> None:
    proposals = propose_rules(FakeProvider(responses=_PROPOSALS), _usages())
    assert {p.dimension for p in proposals} == {DQDimension.CONSISTENCY, DQDimension.ACCURACY}


def test_merge_dedupes_by_element_dimension_and_enriches_related() -> None:
    heuristic = infer_rules(_usages())
    # join_key heuristic already yields a (cust_id, Consistency) rule.
    before = {(r.element, r.dimension) for r in heuristic}
    assert ("raw.cust.cust_id", DQDimension.CONSISTENCY) in before

    merged = infer_rules_with_proposals(FakeProvider(responses=_PROPOSALS), _usages(), heuristic)

    # No duplicate (element, dimension) pairs.
    keys = [(r.element, r.dimension) for r in merged]
    assert len(keys) == len(set(keys))

    # The duplicate proposal enriched the heuristic rule's related_elements (R6),
    # keeping its heuristic source.
    consistency = next(
        r
        for r in merged
        if r.element == "raw.cust.cust_id" and r.dimension is DQDimension.CONSISTENCY
    )
    assert "raw.txn.cust_id" in consistency.related_elements
    assert consistency.source is Provenance.HEURISTIC

    # The genuinely new (element, dimension) was added as an I rule, review-required.
    accuracy = next(
        r
        for r in merged
        if r.element == "mart.scores.score" and r.dimension is DQDimension.ACCURACY
    )
    assert accuracy.source is Provenance.INFERRED
    assert accuracy.confidence is Confidence.MEDIUM
    assert accuracy.status is RuleStatus.PROPOSED


def test_proposer_degrades_to_none_on_invalid_llm() -> None:
    heuristic = infer_rules(_usages())
    merged = infer_rules_with_proposals(
        FakeProvider(responses="not json at all"), _usages(), heuristic
    )
    assert merged == heuristic  # robust: proposer failure leaves the heuristic set intact
