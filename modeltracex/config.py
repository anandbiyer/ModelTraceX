"""Application configuration (NFR-10).

Single, environment-driven ``Settings`` object. All settings are read from the
environment (prefix ``MODELTRACEX_``) or a ``.env`` file; provider secrets are
read here but never persisted to the run store.

Bootstrap deliverable PRE-4, refined in Phase 0 (P0-3): ``SecurityMode`` is now
the canonical enum from ``modeltracex.state`` (re-exported here for convenience);
``DetailLevel`` stays local since it is a config concern, not part of the
canonical state (SDD §4.1).
"""

from __future__ import annotations

from enum import Enum

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from modeltracex.state import SecurityMode


class DetailLevel(str, Enum):
    """Run-wide lineage granularity default (FR-5.1)."""

    TABLE = "table"
    COLUMN = "column"


class Settings(BaseSettings):
    """Runtime configuration for a ModelTraceX deployment.

    Authority note (SDD §12, D6): ``security_mode`` is the per-run default, but
    ``allowed_security_modes`` is the hard ceiling the UI cannot exceed; the
    construction-time egress guard (SDD §14.3, Phase 0 P0-4) enforces it.
    """

    model_config = SettingsConfigDict(
        env_prefix="MODELTRACEX_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # This is a settings object, not an LLM schema; allow a field named `model`.
        protected_namespaces=(),
    )

    # --- LLM provider selection (NFR-1) ---
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-6"
    local_base_url: str = "http://localhost:11434/v1"
    local_model: str = "qwen2.5-coder:32b"

    # --- Security & data handling (NFR-2) ---
    security_mode: SecurityMode = SecurityMode.CLOUD
    retain_source: bool = False
    allowed_security_modes: list[SecurityMode] = Field(
        default_factory=lambda: [SecurityMode.CLOUD, SecurityMode.LOCAL]
    )

    # --- Orchestration (FR-3.2) ---
    max_concurrency: int = 4
    requests_per_minute: int = 60
    tokens_per_minute: int = 120_000

    # --- Analysis defaults ---
    detail_level: DetailLevel = DetailLevel.TABLE
    output_formats: list[str] = Field(default_factory=lambda: ["docx", "xlsx"])

    # --- Provider secrets (NFR-10; never persisted) ---
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_endpoint: str | None = None

    # --- Store ---
    db_path: str = "modeltracex.db"
    tool_version: str = "2.0.0-dev"


def get_settings() -> Settings:
    """Load settings from the environment / ``.env``."""

    return Settings()
