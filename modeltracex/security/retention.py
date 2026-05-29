"""Retention scrub (SDD §12, Phase 4 P4-5).

In ``security_mode=local`` with ``retain_source=False`` (the default), the source
snippets the heuristic adapter captured for DQ inference must NOT survive into
``state_json`` or the DOCX Appendix — they are the inputs the customer doesn't
want leaving the box. Cloud mode and ``retain_source=True`` are unchanged.

The scrub is structural (clear evidence strings on UsageObservations and DQRules;
clear the calculation expressions which carry literal code), never destructive of
*identity*: ids, table/column names, roles, and edges are all preserved so the
projections still render. A single ``Issue`` is appended so the reviewer can see
that scrubbing occurred — the audit trail is the policy, not the convention.
"""

from __future__ import annotations

from modeltracex.state import Issue, RunState, SecurityMode


def scrub_for_retention(state: RunState, *, retain_source: bool) -> RunState:
    """Mutate-and-return: strip source-bearing fields if local mode + not retaining.

    No-op in cloud mode (state remains as-is). No-op in local mode when
    ``retain_source=True`` (the operator opted into keeping snippets).
    """
    if state.run.security_mode is not SecurityMode.LOCAL or retain_source:
        return state

    scrubbed_observations = 0
    for usage in state.usage_observations:
        if usage.evidence:
            usage.evidence = ""
            scrubbed_observations += 1

    scrubbed_rules = 0
    for rule in state.dq_rules:
        if rule.code_evidence:
            rule.code_evidence = ""
            scrubbed_rules += 1

    scrubbed_calcs = 0
    for model in state.models:
        for calc in model.calculations:
            if calc.expression:
                calc.expression = ""
                scrubbed_calcs += 1

    # R4: ColumnEdge.expression is the authoritative home of calc text in lineage —
    # scrub that too, or the snippet survives via the lineage projection.
    scrubbed_edges = 0
    for edge in state.column_edges:
        if edge.expression:
            edge.expression = None
            scrubbed_edges += 1

    if scrubbed_observations or scrubbed_rules or scrubbed_calcs or scrubbed_edges:
        state.issues.append(
            Issue(
                model_id=None,
                severity="info",
                message=(
                    f"retention scrub: cleared source snippets in local mode "
                    f"(usages={scrubbed_observations}, rules={scrubbed_rules}, "
                    f"calcs={scrubbed_calcs}, edges={scrubbed_edges}); "
                    f"set retain_source=true to keep them"
                ),
            )
        )
    return state


__all__ = ["scrub_for_retention"]
