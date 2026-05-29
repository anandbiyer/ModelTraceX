"""DQ LLM proposer (SDD §10, P3-8) — the E/I, review-required path.

The Phase-1 engine maps adapter usages to deterministic ``H`` rules. This adds an
LLM proposal pass that can surface rules the heuristics miss — notably *relational*
rules across elements (R6, ``related_elements``). Proposals are merged with the
heuristic set **by ``(element, dimension)``**: a proposal that duplicates a
heuristic rule only enriches its ``related_elements`` (the deterministic ``H`` rule
wins on source/severity); a genuinely new ``(element, dimension)`` is added as an
``I`` rule with ``status=Proposed`` (review-required, never auto-trusted, R5).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from modeltracex import ids
from modeltracex.llm.provider import LLMProvider
from modeltracex.llm.structured import SchemaValidationError, structured_call
from modeltracex.state import (
    Confidence,
    DQDimension,
    DQRule,
    Provenance,
    RuleStatus,
    Severity,
    UsageObservation,
)


class DQProposal(BaseModel):
    element: str
    dimension: DQDimension
    rule_statement: str
    severity: Severity = Severity.MEDIUM
    rationale: str = ""
    related_elements: list[str] = Field(default_factory=list)  # R6: relational rules


class DQProposalSet(BaseModel):
    proposals: list[DQProposal] = Field(default_factory=list)


_SYSTEM = (
    "You are a data-quality reviewer. Given a model's elements and how they are used, "
    "propose data-quality rules the static heuristics may have missed — especially "
    "RELATIONAL rules that span more than one element (list them in related_elements). "
    "Return a DQProposalSet JSON: proposals[{element, dimension, rule_statement, severity, "
    "rationale, related_elements}]. Use the six dimensions exactly: Completeness, Validity, "
    "Uniqueness, Consistency, Accuracy, Timeliness."
)


def _user(usages: list[UsageObservation]) -> str:
    lines = [f"- {u.element}: used as {u.usage_kind.value} ({u.evidence})" for u in usages]
    return "ELEMENT USAGES:\n" + ("\n".join(lines) or "(none)")


def propose_rules(provider: LLMProvider, usages: list[UsageObservation]) -> list[DQProposal]:
    """Ask the provider for additional DQ rules; degrade to none on validation failure."""
    try:
        result = structured_call(provider, _SYSTEM, _user(usages), DQProposalSet)
    except SchemaValidationError:
        return []
    return result.value.proposals


def merge_proposals(heuristic: list[DQRule], proposals: list[DQProposal]) -> list[DQRule]:
    """Merge LLM proposals into the heuristic set, deduped by (element, dimension)."""
    by_key: dict[tuple[str, DQDimension], DQRule] = {(r.element, r.dimension): r for r in heuristic}
    merged = list(heuristic)
    for p in proposals:
        key = (p.element, p.dimension)
        existing = by_key.get(key)
        if existing is not None:
            for related in p.related_elements:
                if related not in existing.related_elements:
                    existing.related_elements.append(related)
            continue
        rule = DQRule(
            rule_id=ids.rule_id(p.element, p.dimension.value, p.rule_statement),
            element=p.element,
            related_elements=list(p.related_elements),
            dimension=p.dimension,
            rule_statement=p.rule_statement,
            rationale=p.rationale,
            severity=p.severity,
            source=Provenance.INFERRED,  # E/I path; never H (R5)
            confidence=Confidence.MEDIUM,
            status=RuleStatus.PROPOSED,  # review-required
        )
        merged.append(rule)
        by_key[key] = rule
    return merged


def infer_rules_with_proposals(
    provider: LLMProvider, usages: list[UsageObservation], heuristic: list[DQRule]
) -> list[DQRule]:
    """Heuristic rules + merged LLM proposals (the full §10 path)."""
    return merge_proposals(heuristic, propose_rules(provider, usages))


__all__ = [
    "DQProposal",
    "DQProposalSet",
    "propose_rules",
    "merge_proposals",
    "infer_rules_with_proposals",
]
