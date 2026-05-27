"""AnthropicProvider — cloud default (``claude-sonnet-4-6``), SDD §6.1.

The ``anthropic`` SDK is an optional dependency (``modeltracex[llm]``) and is
imported lazily inside the client accessor, so this module imports cleanly in the
offline CI gate where the SDK is absent and only the ``FakeProvider`` runs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

from modeltracex.llm.provider import LLMResult, Usage

if TYPE_CHECKING:
    from modeltracex.config import Settings

# USD per 1M tokens (input, output). Best-effort for telemetry (NFR-6, R2); 0.0 if unknown.
_PRICES: dict[str, tuple[float, float]] = {
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-opus-4-7": (15.0, 75.0),
}

_JSON_ONLY = "\n\nReturn ONLY a single JSON object matching the schema. No prose, no code fences."


def _estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    price_in, price_out = _PRICES.get(model, (0.0, 0.0))
    return (tokens_in * price_in + tokens_out * price_out) / 1_000_000


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[-1] if "\n" in t else t
        if t.endswith("```"):
            t = t[: -len("```")]
    return t.strip()


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, model: str, api_key: str | None = None, max_tokens: int = 4096) -> None:
        self.model = model
        self._api_key = api_key
        self._max_tokens = max_tokens
        self._client: object | None = None

    def _get_client(self) -> object:
        if self._client is None:
            try:
                import anthropic
            except ImportError as exc:  # pragma: no cover - exercised only without the extra
                raise RuntimeError(
                    "the 'anthropic' SDK is required for the anthropic provider; "
                    "install with: pip install 'modeltracex[llm]'"
                ) from exc
            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    def complete_json(self, system: str, user: str, schema: type[BaseModel]) -> LLMResult:
        client = self._get_client()
        resp = client.messages.create(  # type: ignore[attr-defined]
            model=self.model,
            max_tokens=self._max_tokens,
            system=system + _JSON_ONLY,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(
            block.text for block in resp.content if getattr(block, "type", None) == "text"
        )
        usage = Usage(
            tokens_in=resp.usage.input_tokens,
            tokens_out=resp.usage.output_tokens,
            est_cost=_estimate_cost(self.model, resp.usage.input_tokens, resp.usage.output_tokens),
        )
        return LLMResult(raw=_strip_fences(text), usage=usage)


def build(cfg: Settings) -> AnthropicProvider:
    return AnthropicProvider(model=cfg.model, api_key=cfg.anthropic_api_key)


__all__ = ["AnthropicProvider", "build"]
