"""``StateMutationPlan`` — the typed output of the Chat agent (SDD §13.2).

Chat is **not** a free-form chatbot: the agent is constrained (via the structured
call) to emit a list of allowed, typed operations over ``RunState``. The schema is
deliberately small and tolerant on ``args`` (a free dict) so the validate→retry
loop (§6.3) recovers easily; the **authority policy** — not the LLM — stamps
``requires_confirmation`` (see ``chat/authority.py``).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

MutationOp = Literal[
    "set_table_role",
    "set_language_hint",
    "set_lineage_detail",
    "reanalyze_scope",
    "accept_rule",
    "reject_rule",
    "merge_models",
    "split_model",
    "set_detail_level",
    "set_provider",
]


class StateMutation(BaseModel):
    op: MutationOp
    args: dict = Field(default_factory=dict)
    # Set by the authority policy after the agent returns, never trusted from the LLM.
    requires_confirmation: bool = False


class StateMutationPlan(BaseModel):
    rationale: str = ""
    mutations: list[StateMutation] = Field(default_factory=list)


__all__ = ["MutationOp", "StateMutation", "StateMutationPlan"]
