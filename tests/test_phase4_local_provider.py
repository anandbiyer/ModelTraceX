"""Phase 4 P4-T6 — LocalProvider conformance against a mocked OpenAI-compatible endpoint.

Drives the provider conformance contract (``complete_json`` returns an
``LLMResult`` with usage) without a real Ollama/vLLM running. ``httpx.MockTransport``
intercepts the POST and shapes the response.

Also covers two NFR-2 invariants:
- Non-loopback ``local_base_url`` raises ``SecurityError`` at construction.
- ``security_mode=local`` + non-local provider raises ``SecurityError`` via the
  egress guard (already tested in Phase 0 P0-T3; here re-asserted for the local
  flip-side: local provider + local mode is allowed).
"""

from __future__ import annotations

import json

import httpx
import pytest

from modeltracex.config import Settings
from modeltracex.llm.local import LocalProvider
from modeltracex.llm.provider import SecurityError, build_provider
from modeltracex.llm.schema import ModelExtraction
from modeltracex.state import SecurityMode


def _mock_transport(payload: dict[str, object]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        body = json.loads(request.content)
        assert body["model"] == "qwen2.5-coder:32b"
        assert body["response_format"] == {"type": "json_object"}
        return httpx.Response(200, json=payload)

    return httpx.MockTransport(handler)


def test_local_provider_returns_llmresult_with_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODELTRACEX_PROVIDER", "local")
    monkeypatch.setenv("MODELTRACEX_SECURITY_MODE", "local")
    provider = LocalProvider(model="qwen2.5-coder:32b", base_url="http://localhost:11434/v1")
    provider._client = httpx.Client(  # noqa: SLF001 - intentional injection of the mock
        base_url=provider.base_url,
        transport=_mock_transport(
            {
                "choices": [{"message": {"content": json.dumps({"purpose": "X"})}}],
                "usage": {"prompt_tokens": 17, "completion_tokens": 5},
            }
        ),
    )
    result = provider.complete_json("sys", "user", ModelExtraction)
    assert json.loads(result.raw)["purpose"] == "X"
    assert result.usage.tokens_in == 17
    assert result.usage.tokens_out == 5
    assert result.usage.est_cost == 0.0  # local model is free


def test_local_provider_rejects_non_loopback_base_url() -> None:
    with pytest.raises(SecurityError, match="not loopback"):
        LocalProvider(model="m", base_url="http://example.com/v1")


def test_egress_guard_allows_local_provider_in_local_mode() -> None:
    cfg = Settings(provider="local", security_mode=SecurityMode.LOCAL)
    # build_provider must not raise — local is non-egress.
    provider = build_provider(cfg)
    assert provider.name == "local"


def test_egress_guard_blocks_non_local_in_local_mode() -> None:
    cfg = Settings(provider="anthropic", security_mode=SecurityMode.LOCAL)
    with pytest.raises(SecurityError, match="local"):
        build_provider(cfg)
