#!/usr/bin/env python
"""Materialize the *derived* corpus artifacts (Phase S tooling).

The hand-curated text fixtures are committed directly under
``tests/fixtures/corpus/``. This script produces the artifacts that should not
be hand-edited as text — the binary ingestion variants (S-6): a ``.zip`` of the
multi-file project, an intentionally lossy ``.pdf``, and (if ``python-docx`` is
installed) a ``.docx``. It derives them from the committed text variants, so the
text fixtures remain the single source of truth.

Idempotent and re-runnable:

    python tests/tools/build_corpus.py

Stdlib-only for the zip and PDF so it runs in the offline CI gate without the
optional ``export`` dependency group; the ``.docx`` is skipped (not failed)
when ``python-docx`` is absent.
"""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
INGESTION = FIXTURES / "corpus" / "ingestion"

# Fixed timestamp so regenerated zips are byte-stable (no churn in diffs/CI).
_ZIP_EPOCH = (2026, 1, 1, 0, 0, 0)


def _build_zip(dest: Path, members: dict[str, bytes]) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in sorted(members):
            info = zipfile.ZipInfo(name, date_time=_ZIP_EPOCH)
            zf.writestr(info, members[name])


def _build_pdf(dest: Path, text: str) -> None:
    """Write a minimal, valid single-page PDF holding only the first code line.

    Carrying just a fragment makes the fixture *lossy* on purpose, so the
    Phase-1 pdf_extract path can assert the lossy-extraction Issue (FR-2.1).
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    fragment = next((ln for ln in text.splitlines() if ln.strip()), "")
    safe = fragment.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
    stream = b"BT /F1 10 Tf 72 720 Td (" + safe.encode("latin-1", "replace") + b") Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += str(i).encode() + b" 0 obj\n" + body + b"\nendobj\n"
    xref_pos = len(out)
    size = len(objects) + 1
    out += b"xref\n0 " + str(size).encode() + b"\n"
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        b"trailer\n<< /Size " + str(size).encode() + b" /Root 1 0 R >>\n"
        b"startxref\n" + str(xref_pos).encode() + b"\n%%EOF\n"
    )
    dest.write_bytes(bytes(out))


def _build_docx(dest: Path, text: str) -> bool:
    try:
        from docx import Document  # type: ignore[import-not-found]
    except ImportError:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    doc = Document()
    for line in text.splitlines():
        doc.add_paragraph(line)
    doc.save(str(dest))
    return True


def materialize() -> dict[str, str]:
    """(Re)build the binary ingestion variants. Returns a {artifact: status} map."""
    single = (INGESTION / "single" / "model.sas").read_text(encoding="utf-8")
    part1 = (INGESTION / "multi" / "part1.sas").read_bytes()
    part2 = (INGESTION / "multi" / "part2.sas").read_bytes()

    manifest: dict[str, str] = {}

    zip_path = INGESTION / "zip" / "model_project.zip"
    _build_zip(zip_path, {"part1.sas": part1, "part2.sas": part2})
    manifest[str(zip_path.relative_to(FIXTURES))] = "built"

    pdf_path = INGESTION / "pdf" / "model_lossy.pdf"
    _build_pdf(pdf_path, single)
    manifest[str(pdf_path.relative_to(FIXTURES))] = "built"

    docx_path = INGESTION / "docx" / "model.docx"
    built = _build_docx(docx_path, single)
    manifest[str(docx_path.relative_to(FIXTURES))] = (
        "built" if built else "skipped (python-docx not installed)"
    )

    return manifest


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()
    for artifact, status in materialize().items():
        print(f"  {status:<40} {artifact}")


if __name__ == "__main__":
    main()
