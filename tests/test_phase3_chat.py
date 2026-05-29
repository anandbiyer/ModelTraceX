"""Phase 3 chat tests (P3-T1): NL → typed StateMutationPlan + authority gating.

The ChatAgent maps NL to a validated plan via the FakeProvider; the authority
policy — not the LLM — stamps requires_confirmation (auto vs confirm, SDD §13.2 Q5).
"""

from __future__ import annotations

import json

from modeltracex.chat import ChatAgent
from modeltracex.chat.authority import requires_confirmation
from modeltracex.llm.fake import FakeProvider

# --------------------------------------------------------------------------- #
# Authority policy (Q5)
# --------------------------------------------------------------------------- #


def test_auto_apply_ops_need_no_confirmation() -> None:
    for op in (
        "set_table_role",
        "set_language_hint",
        "set_lineage_detail",
        "reanalyze_scope",
        "set_detail_level",
    ):
        assert requires_confirmation(op, {}) is False


def test_confirm_required_ops_are_gated() -> None:
    for op in ("merge_models", "split_model", "set_provider", "set_security_mode"):
        assert requires_confirmation(op, {}) is True


def test_single_accept_is_auto_but_bulk_is_gated() -> None:
    assert requires_confirmation("accept_rule", {"rule_id": "r1"}) is False
    assert requires_confirmation("reject_rule", {"rule_ids": ["r1", "r2"]}) is True
    assert requires_confirmation("accept_rule", {"bulk": True}) is True


# --------------------------------------------------------------------------- #
# Agent: NL -> plan, with policy-stamped confirmation
# --------------------------------------------------------------------------- #


def test_agent_stamps_confirmation_regardless_of_llm() -> None:
    # The LLM (wrongly) marks a destructive merge as not requiring confirmation;
    # the agent must overwrite that from policy.
    plan_json = json.dumps(
        {
            "rationale": "Treat staging as intermediate and merge the two scoring models.",
            "mutations": [
                {
                    "op": "set_table_role",
                    "args": {"table_id": "t1", "role": "Intermediate"},
                    "requires_confirmation": True,
                },
                {
                    "op": "merge_models",
                    "args": {"model_ids": ["m1", "m2"]},
                    "requires_confirmation": False,
                },
            ],
        }
    )
    agent = ChatAgent(FakeProvider(responses=plan_json))
    plan = agent.plan("treat staging as intermediate and merge the scoring models")

    assert [m.op for m in plan.mutations] == ["set_table_role", "merge_models"]
    by_op = {m.op: m.requires_confirmation for m in plan.mutations}
    assert by_op["set_table_role"] is False  # auto-apply, despite LLM saying True
    assert by_op["merge_models"] is True  # confirm-required, despite LLM saying False


def test_agent_returns_typed_plan() -> None:
    plan_json = json.dumps(
        {
            "rationale": "Raise scoring to column level.",
            "mutations": [
                {"op": "set_lineage_detail", "args": {"detail": "column", "model_ids": ["m3"]}}
            ],
        }
    )
    plan = ChatAgent(FakeProvider(responses=plan_json)).plan("raise model 3 to column level")
    assert plan.rationale
    assert plan.mutations[0].op == "set_lineage_detail"
    assert plan.mutations[0].args["detail"] == "column"
    assert plan.mutations[0].requires_confirmation is False
