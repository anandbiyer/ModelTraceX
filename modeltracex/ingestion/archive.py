"""Archive ingestion (FR-2.1) — unzip a project into ``SourceArtifact``s.

Text members are decoded directly; binary members (``.docx``/``.pdf``) are routed
through the readers via a temp file so a zipped project ingests the same as a
loose one. Directory entries and dotfiles are skipped.
"""

from __future__ import annotations

import os
import tempfile
import zipfile
from pathlib import Path

from modeltracex.ingestion.readers import SourceArtifact, read_path

_BINARY_SUFFIXES = {".docx", ".pdf"}


def unzip_project(path: str | os.PathLike[str]) -> list[SourceArtifact]:
    artifacts: list[SourceArtifact] = []
    with zipfile.ZipFile(path) as zf:
        for name in sorted(zf.namelist()):
            if name.endswith("/") or os.path.basename(name).startswith("."):
                continue
            data = zf.read(name)
            suffix = Path(name).suffix.lower()
            if suffix in _BINARY_SUFFIXES:
                with tempfile.TemporaryDirectory() as td:
                    tmp = Path(td) / Path(name).name
                    tmp.write_bytes(data)
                    art = read_path(tmp)
                    art.filename = name
                    artifacts.append(art)
            else:
                artifacts.append(
                    SourceArtifact(filename=name, content=data.decode("utf-8", errors="replace"))
                )
    return artifacts


__all__ = ["unzip_project"]
