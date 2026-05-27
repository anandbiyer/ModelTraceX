"""Ingestion subpackage — paste/file/zip/docx/pdf -> SourceArtifacts -> models (FR-2)."""

from __future__ import annotations

from modeltracex.ingestion.archive import unzip_project
from modeltracex.ingestion.detect import assemble_models, detect_language
from modeltracex.ingestion.readers import SourceArtifact, read_paste, read_path

__all__ = [
    "SourceArtifact",
    "read_path",
    "read_paste",
    "unzip_project",
    "assemble_models",
    "detect_language",
]
