"""Exporter contract (SDD §11.1, FR-4.3).

Every exporter is a pure projection of ``RunState`` → file(s); the document, the
workbook, the diagrams all render from one validated object (FR-4.2). The
"Not identified from code" rule (Part A) is shared here so empty sections render
explicitly rather than being omitted.
"""

from __future__ import annotations

import re
from typing import Protocol, runtime_checkable

from modeltracex.state import RunState

NOT_IDENTIFIED = "Not identified from code"


@runtime_checkable
class Exporter(Protocol):
    fmt: str

    def export(self, state: RunState, out_dir: str) -> list[str]: ...


def safe_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_") or "model"


__all__ = ["NOT_IDENTIFIED", "Exporter", "safe_filename"]
