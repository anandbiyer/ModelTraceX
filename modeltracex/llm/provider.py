"""LLM-provider abstraction + factory + construction-time egress guard (SDD §6.1/§14.3).

``LLMProvider`` is a structural Protocol — analysis code depends on it, never on a
concrete provider name (NFR-1, NFR-10). ``build_provider`` is the only place a
provider is constructed; it enforces the **egress guard** (NFR-2, SDD §14.3)
*before* importing or constructing anything, so a misconfigured local-mode run
can never reach an external API.

Phase 0 (P0-4) ships ``fake`` and ``anthropic``. ``local``/``openai``/``azure``
arrive in later phases; asking for one now raises a clear error.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pydantic import BaseModel

from modeltracex.state import SecurityMode

if TYPE_CHECKING:
    from collections.abc import Callable

    from modeltracex.config import Settings


class Usage(BaseModel):
    tokens_in: int = 0
    tokens_out: int = 0
    est_cost: float = 0.0


class LLMResult(BaseModel):
    raw: str
    usage: Usage = Usage()


@runtime_checkable
class LLMProvider(Protocol):
    """The structural contract every provider implements."""

    name: str
    model: str

    def complete_json(self, system: str, user: str, schema: type[BaseModel]) -> LLMResult: ...


class SecurityError(RuntimeError):
    """Raised when a configuration would breach the data-handling boundary (NFR-2)."""


# Providers that make no external network calls — always allowed in local mode.
_NON_EGRESS = frozenset({"local", "fake"})

# name -> (module, builder-attr). The builder is ``build(cfg) -> LLMProvider``.
_PROVIDERS: dict[str, tuple[str, str]] = {
    "fake": ("modeltracex.llm.fake", "build"),
    "anthropic": ("modeltracex.llm.anthropic", "build"),
    "local": ("modeltracex.llm.local", "build"),
}


def _load_factory(provider: str) -> Callable[[Settings], LLMProvider]:
    if provider not in _PROVIDERS:
        raise NotImplementedError(
            f"provider {provider!r} is not available yet "
            f"(implemented: {sorted(_PROVIDERS)}; openai/azure/local land in later phases)"
        )
    module_path, attr = _PROVIDERS[provider]
    import importlib

    module = importlib.import_module(module_path)
    return getattr(module, attr)


def build_provider(cfg: Settings) -> LLMProvider:
    """Construct the configured provider, enforcing the egress guard first (§14.3)."""
    if cfg.security_mode is SecurityMode.LOCAL and cfg.provider not in _NON_EGRESS:
        raise SecurityError(
            f"security_mode=local forbids the external provider {cfg.provider!r}; "
            f"use a local or fake provider"
        )
    return _load_factory(cfg.provider)(cfg)


__all__ = [
    "Usage",
    "LLMResult",
    "LLMProvider",
    "SecurityError",
    "build_provider",
]
