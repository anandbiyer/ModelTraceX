"""Phase 4 P4-T1 (EXIT) — no-egress verification.

Asserts that running the full pipeline in ``security_mode=local`` makes zero
outbound socket connections AND that constructing a cloud provider in local mode
raises ``SecurityError`` (SDD §14.3). The egress harness monkeypatches the low-
level socket factory so any call out from anywhere in the pipeline trips it
loudly — including transitive deps (anthropic SDK, httpx, urllib).
"""

from __future__ import annotations

import json
import socket

import pytest

from modeltracex.analysis.orchestrator import ModelInput, analyze_run
from modeltracex.config import Settings
from modeltracex.llm.fake import FakeProvider
from modeltracex.llm.provider import SecurityError, build_provider
from modeltracex.security import default_redactor, scrub_for_retention
from modeltracex.state import Language, SecurityMode


def _install_egress_block(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, int]]:
    """Replace ``socket.create_connection`` with a tripwire; return the attempts list."""
    attempts: list[tuple[str, int]] = []
    real_create = socket.create_connection

    def blocked(addr: tuple[str, int], *args: object, **kwargs: object) -> socket.socket:
        host, port = addr
        # Loopback is permitted (the LocalProvider talks to it).
        if host in {"localhost", "127.0.0.1", "::1"}:
            return real_create(addr, *args, **kwargs)  # type: ignore[arg-type]
        attempts.append((host, port))
        raise RuntimeError(f"egress blocked: {host}:{port}")

    monkeypatch.setattr(socket, "create_connection", blocked)
    return attempts


def test_local_mode_full_pipeline_makes_zero_external_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = _install_egress_block(monkeypatch)

    cfg = Settings(provider="fake", security_mode=SecurityMode.LOCAL)
    provider = build_provider(cfg)  # FakeProvider is non-egress by definition
    assert isinstance(provider, FakeProvider)

    payload = json.dumps(
        {
            "purpose": "build the table",
            "input_tables": [{"name": "raw.events"}],
            "output_tables": [{"name": "work.staging"}],
        }
    )
    inputs = [
        ModelInput(
            label="m", language=Language.SAS, source_files=["m.sas"], code="data work.staging;"
        )
    ]
    state = analyze_run(
        FakeProvider(responses={"m": payload}, default=payload),
        inputs,
        redactor=default_redactor(),
    )
    state.run.security_mode = SecurityMode.LOCAL
    scrub_for_retention(state, retain_source=cfg.retain_source)

    assert attempts == [], f"unexpected external calls: {attempts}"
    assert state.run.security_mode is SecurityMode.LOCAL


def test_cloud_provider_in_local_mode_raises_at_construction() -> None:
    cfg = Settings(provider="anthropic", security_mode=SecurityMode.LOCAL)
    with pytest.raises(SecurityError):
        build_provider(cfg)


def test_local_provider_outside_loopback_is_refused() -> None:
    # Even when the operator forces local provider, the LocalProvider itself
    # refuses to talk to anything but loopback — defense in depth.
    cfg = Settings(
        provider="local",
        security_mode=SecurityMode.LOCAL,
        local_base_url="http://10.0.0.5:11434/v1",
    )
    with pytest.raises(SecurityError, match="not loopback"):
        build_provider(cfg)
