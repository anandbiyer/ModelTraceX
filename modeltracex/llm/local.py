"""``LocalProvider`` — OpenAI-compatible local LLM (SDD §3.4/§6.1, Phase 4 P4-3).

Talks plain HTTP to an OpenAI-compatible **/v1/chat/completions** endpoint —
typically Ollama or vLLM serving a local Qwen2.5-Coder model. The egress guard
(SDD §14.3) treats ``local`` as non-egress because we **refuse to bind to a
non-loopback URL**: any base_url whose host is not ``localhost``/``127.0.0.1``/
``[::1]`` is rejected at construction time. That keeps NFR-2 ("verifiably no
external call") provable from the configuration alone, not by trust.

The ``httpx`` dependency is optional (``modeltracex[local]``) and lazy-imported,
so the offline gate that uses ``FakeProvider`` doesn't need it installed.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from pydantic import BaseModel

from modeltracex.llm.provider import LLMResult, SecurityError, Usage

if TYPE_CHECKING:
    from modeltracex.config import Settings

_JSON_ONLY = "\n\nReturn ONLY a single JSON object matching the schema. No prose, no code fences."
_LOOPBACK = frozenset({"localhost", "127.0.0.1", "::1", "[::1]"})


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[-1] if "\n" in t else t
        if t.endswith("```"):
            t = t[: -len("```")]
    return t.strip()


def _require_loopback(base_url: str) -> None:
    """A local provider that talks anywhere but loopback is a misconfiguration (NFR-2)."""
    host = urlparse(base_url).hostname or ""
    if host not in _LOOPBACK:
        raise SecurityError(
            f"LocalProvider base_url {base_url!r} is not loopback "
            f"(host={host!r}); refusing to construct"
        )


class LocalProvider:
    """OpenAI-compatible local provider. Pricing is 0 (the local model is free)."""

    name = "local"

    def __init__(self, model: str, base_url: str, timeout: float = 120.0) -> None:
        _require_loopback(base_url)
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client: object | None = None

    def _get_client(self) -> object:
        if self._client is None:
            try:
                import httpx
            except ImportError as exc:  # pragma: no cover - only when [local] is missing
                raise RuntimeError(
                    "the 'httpx' library is required for the local provider; "
                    "install with: pip install 'modeltracex[local]'"
                ) from exc
            self._client = httpx.Client(base_url=self.base_url, timeout=self._timeout)
        return self._client

    def complete_json(self, system: str, user: str, schema: type[BaseModel]) -> LLMResult:
        client = self._get_client()
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system + _JSON_ONLY},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
            "stream": False,
        }
        resp = client.post("/chat/completions", json=body)  # type: ignore[attr-defined]
        resp.raise_for_status()
        data = resp.json()
        choice = data["choices"][0]["message"]["content"]
        usage_d = data.get("usage") or {}
        usage = Usage(
            tokens_in=int(usage_d.get("prompt_tokens", 0)),
            tokens_out=int(usage_d.get("completion_tokens", 0)),
            est_cost=0.0,
        )
        return LLMResult(
            raw=_strip_fences(choice if isinstance(choice, str) else json.dumps(choice)),
            usage=usage,
        )


def build(cfg: Settings) -> LocalProvider:
    return LocalProvider(model=cfg.local_model, base_url=cfg.local_base_url)


__all__ = ["LocalProvider", "build"]
