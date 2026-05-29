"""Authority boundary (SDD §13.2 / decision Q5).

Who may apply a mutation without an explicit confirmation is policy, **not** the
LLM's call. Auto-apply covers reversible, in-state, low-blast-radius
reclassifications (all captured as undoable overrides); confirmation is required
for anything structurally destructive, cost-bearing, or compliance-affecting —
including *bulk* accept/reject.
"""

from __future__ import annotations

# Reversible, in-state, low-blast-radius — applied on a single confirm of the action.
AUTO_APPLY = frozenset(
    {
        "set_table_role",
        "set_language_hint",
        "set_lineage_detail",
        "reanalyze_scope",
        "set_detail_level",
    }
)

# Structurally destructive, cost-bearing, or compliance-affecting — always gated.
CONFIRM_REQUIRED = frozenset({"merge_models", "split_model", "set_provider", "set_security_mode"})


def _is_bulk(args: dict) -> bool:
    return bool(args.get("bulk")) or len(args.get("rule_ids", [])) > 1


def requires_confirmation(op: str, args: dict) -> bool:
    """Decide confirmation purely from the op (+ bulkiness), per the Q5 policy."""
    if op in CONFIRM_REQUIRED:
        return True
    if op in ("accept_rule", "reject_rule"):
        return _is_bulk(args)  # single accept/reject is auto; bulk is gated
    # Auto-apply ops need no confirmation; anything unknown defaults to the safe side.
    return op not in AUTO_APPLY


__all__ = ["AUTO_APPLY", "CONFIRM_REQUIRED", "requires_confirmation"]
