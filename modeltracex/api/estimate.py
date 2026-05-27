"""Pre-flight token/cost estimate (decision D4, NFR-6) — *no LLM call*.

The Upload tab shows "~38k tokens · ~$0.12" before the user spends anything
(SDD §13.4.1). The figure is derived purely from the adapter scans + source size,
so it is deterministic and free. Prices are per-1k-token planning defaults
(Claude Sonnet-tier) and intentionally coarse — this bounds spend, it is not a bill.
"""

from __future__ import annotations

from modeltracex.analysis.chunking import estimate_tokens

# Per-model fixed prompt overhead (system + schema instruction + adapter fragment).
_PROMPT_OVERHEAD_TOKENS = 450
# Rough output:input ratio for a structured extraction.
_OUTPUT_RATIO = 0.35
# Planning prices ($ per 1k tokens).
_IN_PRICE_PER_1K = 0.003
_OUT_PRICE_PER_1K = 0.015


def estimate_models(inputs: list[tuple[str, str]]) -> dict[str, object]:
    """``inputs``: list of (label, code). Returns token + cost projection."""
    per_model: list[dict[str, object]] = []
    total_in = 0
    total_out = 0
    for label, code in inputs:
        tin = estimate_tokens(code) + _PROMPT_OVERHEAD_TOKENS
        tout = int(tin * _OUTPUT_RATIO)
        total_in += tin
        total_out += tout
        per_model.append({"label": label, "tokens_in": tin, "tokens_out": tout})
    total = total_in + total_out
    cost = (total_in / 1000) * _IN_PRICE_PER_1K + (total_out / 1000) * _OUT_PRICE_PER_1K
    return {
        "models": len(inputs),
        "tokens_in": total_in,
        "tokens_out": total_out,
        "tokens": total,
        "est_cost": round(cost, 4),
        "per_model": per_model,
    }


__all__ = ["estimate_models"]
