"""``ChatAgent`` — NL → typed ``StateMutationPlan`` (SDD §13.2, FR-9.2).

The agent maps a natural-language request to a validated plan via the shared
structured-call retry loop (§6.3), then **stamps ``requires_confirmation`` from the
authority policy** (overwriting whatever the model said). The LLM proposes; policy
disposes. A short summary of the current run is passed as context so the agent can
target real model/table ids.
"""

from __future__ import annotations

from modeltracex.chat import authority
from modeltracex.chat.schema import StateMutationPlan
from modeltracex.llm.provider import LLMProvider
from modeltracex.llm.structured import structured_call
from modeltracex.state import RunState

_SYSTEM = (
    "You translate a reviewer's natural-language request into a StateMutationPlan: "
    "a rationale plus a list of typed mutations over the analysis state. Allowed ops: "
    "set_table_role(table_id, role), set_language_hint(model_id, language), "
    "set_lineage_detail(detail, model_ids?), reanalyze_scope(model_ids), "
    "accept_rule(rule_id|rule_ids), reject_rule(rule_id|rule_ids), "
    "merge_models(model_ids, label?), split_model(model_id), set_detail_level(detail), "
    "set_provider(provider). Use ONLY ids present in the run context. Do not invent ids. "
    "Return ONLY the JSON object; do not set requires_confirmation (the system sets it)."
)


def _context(state: RunState | None) -> str:
    if state is None:
        return "No run context available."
    models = "; ".join(f"{m.label}={m.model_id}" for m in state.models) or "(none)"
    tables = "; ".join(f"{t.name}={t.table_id}" for t in state.tables) or "(none)"
    return f"Models: {models}\nTables: {tables}"


class ChatAgent:
    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    def plan(self, message: str, state: RunState | None = None) -> StateMutationPlan:
        user = f"REQUEST:\n{message}\n\nRUN CONTEXT:\n{_context(state)}"
        result = structured_call(self.provider, _SYSTEM, user, StateMutationPlan)
        plan = result.value
        for mutation in plan.mutations:
            mutation.requires_confirmation = authority.requires_confirmation(
                mutation.op, mutation.args
            )
        return plan


__all__ = ["ChatAgent"]
