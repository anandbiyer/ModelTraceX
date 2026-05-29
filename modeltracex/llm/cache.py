"""``CachingProvider`` — content-hash response cache (SDD §18 R4 control, P3-9).

Wraps any ``LLMProvider`` and memoizes ``complete_json`` by a content hash of
``(system, user)``. Identical chunks — repeated boilerplate across a large project,
or a retry of the same prompt — are served from cache, so token spend scales with
*distinct* content rather than raw model/chunk count. A cache hit makes **no
downstream call** and reports zero new usage, so the rate limiter and cost
telemetry see only real traffic.
"""

from __future__ import annotations

import hashlib

from pydantic import BaseModel

from modeltracex.llm.provider import LLMProvider, LLMResult, Usage


class CachingProvider:
    def __init__(self, inner: LLMProvider) -> None:
        self.inner = inner
        self.name = getattr(inner, "name", "cached")
        self.model = getattr(inner, "model", "")
        self._cache: dict[str, str] = {}
        self.hits = 0
        self.misses = 0

    @staticmethod
    def _key(system: str, user: str) -> str:
        return hashlib.sha1(f"{system}\x00{user}".encode()).hexdigest()

    def complete_json(self, system: str, user: str, schema: type[BaseModel]) -> LLMResult:
        key = self._key(system, user)
        cached = self._cache.get(key)
        if cached is not None:
            self.hits += 1
            # Cache hit: no real call, so report zero new tokens (no double-billing).
            return LLMResult(raw=cached, usage=Usage())
        self.misses += 1
        result = self.inner.complete_json(system, user, schema)
        self._cache[key] = result.raw
        return result


__all__ = ["CachingProvider"]
