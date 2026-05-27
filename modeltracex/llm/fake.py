"""FakeProvider — canned, fixture-keyed JSON for offline CI / local-mode testing.

A first-class test fixture (SDD §15): deterministic, free, no network. It also
exercises the exact code path a local/sensitive deployment uses, so the provider
conformance suite (P0-T4) runs it in CI while real providers are skipped.

Response resolution is flexible so one class covers every test shape:

* ``str`` — always return it (constant).
* ``Callable[[system, user], str]`` — computed per call.
* ``Sequence[str]`` — a script consumed in order (advances each call, so a
  retry sees the *next* item: use this to model "fails then recovers").
* ``Mapping[str, str]`` — routed by the first key that is a substring of the
  user prompt (e.g. keyed on a model label), falling back to ``default``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import TYPE_CHECKING

from pydantic import BaseModel

from modeltracex.llm.provider import LLMResult, Usage

if TYPE_CHECKING:
    from modeltracex.config import Settings

Responses = str | Mapping[str, str] | Sequence[str] | Callable[[str, str], str]


class FakeProvider:
    name = "fake"

    def __init__(
        self,
        model: str = "fake-1",
        *,
        responses: Responses | None = None,
        default: str | None = None,
        usage: Usage | None = None,
    ) -> None:
        self.model = model
        self._responses = responses
        self._default = default
        self._usage = usage or Usage(tokens_in=10, tokens_out=20, est_cost=0.0)
        # A list/tuple is treated as a consumable script.
        self._queue: list[str] | None = (
            list(responses)
            if isinstance(responses, Sequence) and not isinstance(responses, str)
            else None
        )

    def complete_json(self, system: str, user: str, schema: type[BaseModel]) -> LLMResult:
        return LLMResult(raw=self._resolve(system, user), usage=self._usage)

    def _resolve(self, system: str, user: str) -> str:
        r = self._responses
        if r is None:
            return self._default if self._default is not None else "{}"
        if isinstance(r, str):
            return r
        if callable(r):
            return r(system, user)
        if self._queue is not None:
            if self._queue:
                return self._queue.pop(0)
            if self._default is not None:
                return self._default
            raise IndexError("FakeProvider response script is exhausted")
        if isinstance(r, Mapping):
            for key, value in r.items():
                if key in user:
                    return value
            if self._default is not None:
                return self._default
            raise KeyError(f"no FakeProvider response matched the prompt; keys={list(r)}")
        return self._default if self._default is not None else "{}"


def build(cfg: Settings) -> FakeProvider:
    """Factory used by ``build_provider``. A bare instance returns ``{}`` — tests
    that need specific output construct ``FakeProvider(responses=...)`` directly."""
    return FakeProvider(model=getattr(cfg, "model", "fake-1"))


__all__ = ["FakeProvider", "build"]
