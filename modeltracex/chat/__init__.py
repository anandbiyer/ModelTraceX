"""Chat-to-state subpackage (SDD §13.2/§13.3, Deliverable 16).

NL → typed ``StateMutationPlan`` (``agent``), gated by the ``authority`` policy and
applied via the incremental re-run engine (``analysis.rerun``) so only the minimal
downstream set re-executes.
"""

from __future__ import annotations

from modeltracex.chat.agent import ChatAgent
from modeltracex.chat.authority import requires_confirmation
from modeltracex.chat.schema import StateMutation, StateMutationPlan

__all__ = ["ChatAgent", "StateMutation", "StateMutationPlan", "requires_confirmation"]
