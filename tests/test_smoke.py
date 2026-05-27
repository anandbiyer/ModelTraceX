"""Bootstrap smoke tests (Pre-Phase 0).

Prove the scaffold is importable and config loads with sane defaults — the
anchor the CI gate (CT-1) runs against until real tests arrive in Phase 0.
"""

from __future__ import annotations

import importlib

import pytest

import modeltracex
from modeltracex.config import DetailLevel, SecurityMode, Settings, get_settings

# Every package module should import cleanly (stubs included).
PACKAGE_MODULES = [
    "modeltracex.config",
    "modeltracex.state",
    "modeltracex.ids",
    "modeltracex.cli",
    "modeltracex.ingestion.readers",
    "modeltracex.ingestion.archive",
    "modeltracex.ingestion.detect",
    "modeltracex.adapters.base",
    "modeltracex.adapters.sas",
    "modeltracex.adapters.python",
    "modeltracex.llm.provider",
    "modeltracex.llm.anthropic",
    "modeltracex.llm.fake",
    "modeltracex.llm.prompts",
    "modeltracex.llm.schema",
    "modeltracex.llm.structured",
    "modeltracex.analysis.orchestrator",
    "modeltracex.analysis.chunking",
    "modeltracex.analysis.merge",
    "modeltracex.lineage.graph",
    "modeltracex.lineage.render_graphviz",
    "modeltracex.lineage.render_mermaid",
    "modeltracex.dq.rules_table",
    "modeltracex.dq.engine",
    "modeltracex.exporters.base",
    "modeltracex.exporters.docx_report",
    "modeltracex.exporters.xlsx_workbook",
    "modeltracex.exporters.csv_compat",
    "modeltracex.store.db",
    "modeltracex.store.diff",
]


def test_version_present() -> None:
    assert isinstance(modeltracex.__version__, str)
    assert modeltracex.__version__


@pytest.mark.parametrize("module_name", PACKAGE_MODULES)
def test_module_imports(module_name: str) -> None:
    assert importlib.import_module(module_name) is not None


def test_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    # Test genuine code defaults, isolated from ambient env (CI sets
    # MODELTRACEX_PROVIDER=fake / SECURITY_MODE=local for the offline gate).
    for var in ("MODELTRACEX_PROVIDER", "MODELTRACEX_MODEL", "MODELTRACEX_SECURITY_MODE"):
        monkeypatch.delenv(var, raising=False)
    cfg = Settings()
    assert cfg.provider == "anthropic"
    assert cfg.model == "claude-sonnet-4-6"
    assert cfg.security_mode is SecurityMode.CLOUD
    assert cfg.detail_level is DetailLevel.TABLE
    assert cfg.retain_source is False
    assert cfg.max_concurrency == 4
    assert cfg.output_formats == ["docx", "xlsx"]


def test_settings_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODELTRACEX_PROVIDER", "fake")
    monkeypatch.setenv("MODELTRACEX_SECURITY_MODE", "local")
    monkeypatch.setenv("MODELTRACEX_MAX_CONCURRENCY", "8")
    cfg = get_settings()
    assert cfg.provider == "fake"
    assert cfg.security_mode is SecurityMode.LOCAL
    assert cfg.max_concurrency == 8


def test_settings_excludes_secrets_from_default_dump() -> None:
    # Secrets exist as fields but must be omittable for safe logging (NFR-10).
    cfg = Settings(anthropic_api_key="sk-should-not-leak")  # noqa: S106 (test literal)
    safe = cfg.model_dump(exclude={"anthropic_api_key"})
    assert "anthropic_api_key" not in safe
