"""Token-aware chunking (SDD §7.3, FR-3.3).

Splits oversized source on adapter ``split_points`` (DATA/PROC or top-level defs),
greedily packing whole segments into chunks under a token budget so a step is
never cut mid-statement. Idempotence comes from the merge step (``merge.py``):
chunking + id-keyed merge reproduces the unchunked extraction.
"""

from __future__ import annotations

# ~4 chars/token is the usual rough English/code heuristic; good enough for budgeting.
_CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // _CHARS_PER_TOKEN)


def chunk_code(content: str, split_points: list[int], max_tokens: int) -> list[str]:
    """Return chunks (concatenating to ``content`` exactly) each ≲ ``max_tokens``."""
    if not content:
        return [content]
    if estimate_tokens(content) <= max_tokens or not split_points:
        return [content]

    bounds = [0, *sorted({p for p in split_points if 0 < p < len(content)}), len(content)]
    segments = [content[bounds[i] : bounds[i + 1]] for i in range(len(bounds) - 1)]

    chunks: list[str] = []
    current = ""
    for segment in segments:
        if current and estimate_tokens(current + segment) > max_tokens:
            chunks.append(current)
            current = segment
        else:
            current += segment
    if current:
        chunks.append(current)
    return chunks


__all__ = ["estimate_tokens", "chunk_code"]
