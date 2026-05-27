"""Source readers (FR-2.1) — turn a path/paste into a ``SourceArtifact``.

Plain text and ``.docx`` extract cleanly; ``.pdf`` extraction is treated as
**lossy** and always attaches a warning ``Issue`` (PDF text layout extraction is
unreliable), satisfying the lossy-extraction requirement. ``python-docx`` /
``pypdf`` are optional deps imported lazily, so this module imports without them.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from modeltracex.state import Issue


@dataclass
class SourceArtifact:
    filename: str
    content: str
    issues: list[Issue] = field(default_factory=list)


def read_paste(text: str, filename: str = "pasted.txt") -> SourceArtifact:
    return SourceArtifact(filename=filename, content=text)


def read_text(path: str | os.PathLike[str]) -> str:
    return Path(path).read_text(encoding="utf-8", errors="replace")


def docx_extract(path: str | os.PathLike[str]) -> str:
    from docx import Document  # lazy (optional 'export' dep)

    return "\n".join(p.text for p in Document(str(path)).paragraphs)


def pdf_extract(path: str | os.PathLike[str]) -> tuple[str, list[Issue]]:
    name = os.path.basename(str(path))
    issues = [
        Issue(
            severity="warning",
            message=f"PDF text extraction is lossy; verify {name} against the source",
        )
    ]
    try:
        from pypdf import PdfReader  # lazy (optional dep)

        reader = PdfReader(str(path))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception as exc:  # noqa: BLE001 - degrade to heuristic/empty + Issue
        return "", [*issues, Issue(severity="error", message=f"PDF extraction failed: {exc}")]
    return text, issues


def read_path(path: str | os.PathLike[str]) -> SourceArtifact:
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".docx":
        return SourceArtifact(filename=p.name, content=docx_extract(p))
    if suffix == ".pdf":
        text, issues = pdf_extract(p)
        return SourceArtifact(filename=p.name, content=text, issues=issues)
    return SourceArtifact(filename=p.name, content=read_text(p))


__all__ = ["SourceArtifact", "read_paste", "read_text", "docx_extract", "pdf_extract", "read_path"]
