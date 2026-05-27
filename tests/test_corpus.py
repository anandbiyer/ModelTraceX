"""Corpus smoke test + Part C coverage assertion (Phase S, activity S-13).

These tests guard the *synthetic corpus itself* — they need no Pydantic schema
and no LLM, so they run in the offline CI gate (CT-1) from Phase S onward:

* **smoke** — every fixture source file is non-empty and every co-located
  ``expected.json`` is valid JSON with the documented enum values (SDD §4.1).
* **coverage** — the ``dq_coverage`` set collectively triggers *every*
  ``usage_kind`` and *every* ``DQDimension`` in ``part_c_dq_table.json``. If a
  Part C row ever loses its fixture, CI fails here (Implementation Plan §3.4).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
CORPUS = FIXTURES / "corpus"
DQ_COVERAGE = CORPUS / "dq_coverage"
INGESTION = CORPUS / "ingestion"
FAKE_PROVIDER = FIXTURES / "fake_provider"
TOOLS = Path(__file__).parent / "tools"


def _load_tool(name: str) -> ModuleType:
    """Import a tests/tools/*.py script by path (the dir is not a package)."""
    spec = importlib.util.spec_from_file_location(f"_corpus_tool_{name}", TOOLS / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    # Register before exec so dataclasses.asdict() can resolve cls.__module__.
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


PART_C: dict[str, Any] = json.loads((FIXTURES / "part_c_dq_table.json").read_text(encoding="utf-8"))

# Valid enum values, derived from the canonical Part C table so the test can
# never drift from it. The two coarse fallbacks (SDD §4.1) are added explicitly.
VALID_DIMENSIONS = set(PART_C["dimensions"])
VALID_SEVERITIES = set(PART_C["severities"])
VALID_USAGE_KINDS = {r["usage_kind"] for r in PART_C["rules"]} | {"filter", "output"}

# Source files we expect to parse in a later phase; presence + non-emptiness now.
SOURCE_SUFFIXES = {".sas", ".py", ".r", ".bas", ".vba", ".txt"}


def _expected_json_files() -> list[Path]:
    # `_generated/` is gitignored scale output, not curated — skip it.
    return sorted(p for p in FIXTURES.rglob("expected.json") if "_generated" not in p.parts)


def _source_files() -> list[Path]:
    return sorted(
        p
        for p in CORPUS.rglob("*")
        if p.is_file() and p.suffix.lower() in SOURCE_SUFFIXES and "_generated" not in p.parts
    )


# --------------------------------------------------------------------------- #
# Smoke: the corpus is well-formed
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "expected", _expected_json_files(), ids=lambda p: str(p.relative_to(FIXTURES))
)
def test_expected_json_is_valid(expected: Path) -> None:
    data = json.loads(expected.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"{expected} is not a JSON object"


@pytest.mark.parametrize("source", _source_files(), ids=lambda p: str(p.relative_to(CORPUS)))
def test_source_file_non_empty(source: Path) -> None:
    assert source.stat().st_size > 0, f"{source} is empty"


# --------------------------------------------------------------------------- #
# DQ-coverage fixtures: shape + enum validity + twin presence
# --------------------------------------------------------------------------- #
def _dq_dirs() -> list[Path]:
    return sorted(d for d in DQ_COVERAGE.glob("*") if d.is_dir())


@pytest.mark.parametrize("kind_dir", _dq_dirs(), ids=lambda p: p.name)
def test_dq_fixture_shape(kind_dir: Path) -> None:
    expected = kind_dir / "expected.json"
    assert expected.exists(), f"{kind_dir} has no expected.json"
    data = json.loads(expected.read_text(encoding="utf-8"))

    assert data["usage_kind"] in VALID_USAGE_KINDS, data["usage_kind"]
    # Directory name is the usage_kind it is curated for — keeps the set self-describing.
    assert data["usage_kind"] == kind_dir.name
    assert data["severity"] in VALID_SEVERITIES, data["severity"]
    assert data["dimensions"], "at least one dimension required"
    assert set(data["dimensions"]) <= VALID_DIMENSIONS, data["dimensions"]

    # Every declared twin file must exist and be non-empty.
    twins = data.get("twins", {})
    assert twins, "a dq_coverage fixture must declare SAS/Python twins"
    for fname in twins.values():
        twin = kind_dir / fname
        assert twin.exists() and twin.stat().st_size > 0, f"missing twin {twin}"


def test_dq_coverage_triggers_every_part_c_row() -> None:
    """The keystone gate: the dq_coverage set must cover all of Part C."""
    required_kinds = {r["usage_kind"] for r in PART_C["rules"]}
    required_dims = set(PART_C["dimensions"])

    covered_kinds: set[str] = set()
    covered_dims: set[str] = set()
    for kind_dir in _dq_dirs():
        data = json.loads((kind_dir / "expected.json").read_text(encoding="utf-8"))
        covered_kinds.add(data["usage_kind"])
        covered_dims.update(data["dimensions"])

    missing_kinds = required_kinds - covered_kinds
    missing_dims = required_dims - covered_dims
    assert not missing_kinds, f"usage_kinds with no dq_coverage fixture: {sorted(missing_kinds)}"
    assert not missing_dims, f"DQ dimensions with no dq_coverage fixture: {sorted(missing_dims)}"


# --------------------------------------------------------------------------- #
# Referenced-file integrity: every source file an expected.json names exists
# --------------------------------------------------------------------------- #
def _referenced_sources(data: Any, base: Path) -> list[Path]:
    refs: list[str] = []
    if isinstance(data, dict):
        if isinstance(data.get("source_file"), str):
            refs.append(data["source_file"])
        if isinstance(data.get("source_files"), list):
            refs += [s for s in data["source_files"] if isinstance(s, str)]
        if isinstance(data.get("twins"), dict):
            refs += [s for s in data["twins"].values() if isinstance(s, str)]
        if isinstance(data.get("fixtures"), dict):
            refs += list(data["fixtures"].keys())
        if isinstance(data.get("models"), list):
            for m in data["models"]:
                if isinstance(m, dict) and isinstance(m.get("source_file"), str):
                    refs.append(m["source_file"])
    return [base / r for r in refs]


@pytest.mark.parametrize(
    "expected",
    sorted(p for p in CORPUS.rglob("expected.json") if "_generated" not in p.parts),
    ids=lambda p: str(p.relative_to(CORPUS)),
)
def test_referenced_sources_exist(expected: Path) -> None:
    data = json.loads(expected.read_text(encoding="utf-8"))
    referenced = _referenced_sources(data, expected.parent)
    for src in referenced:
        assert src.exists() and src.stat().st_size > 0, f"{expected} references missing {src}"


# --------------------------------------------------------------------------- #
# FakeProvider fixtures parse (malformed set is deliberately *coercible*, not
# un-parseable; partial-failure's always_invalid.json is valid JSON of the
# wrong shape).
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "fixture",
    sorted(FAKE_PROVIDER.rglob("*.json")),
    ids=lambda p: str(p.relative_to(FAKE_PROVIDER)),
)
def test_fake_provider_json_parses(fixture: Path) -> None:
    json.loads(fixture.read_text(encoding="utf-8"))  # raises on malformed JSON


def test_partial_failure_declares_one_failed_one_analyzed() -> None:
    data = json.loads((FAKE_PROVIDER / "partial_failure" / "expected.json").read_text("utf-8"))
    statuses = {m["label"]: m["expected_status"] for m in data["models"]}
    assert "Failed" in statuses.values()
    assert "Analyzed" in statuses.values()
    assert data["batch_completes"] is True
    # The referenced canned responses must exist next to the manifest.
    base = FAKE_PROVIDER / "partial_failure"
    for m in data["models"]:
        assert (base / m["response_file"]).exists()


# --------------------------------------------------------------------------- #
# Ingestion-format set: text variants committed; binaries built on demand
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="session")
def materialized_binaries() -> dict[str, str]:
    """Run build_corpus once so the zip/pdf/(docx) ingestion variants exist."""
    return _load_tool("build_corpus").materialize()


def test_ingestion_text_variants_committed() -> None:
    expected = json.loads((INGESTION / "expected.json").read_text("utf-8"))
    for key in ("paste", "single"):
        rel = expected["variants"][key]["path"]
        f = INGESTION / rel
        assert f.exists() and f.stat().st_size > 0, f"missing committed variant {rel}"
    for rel in expected["variants"]["multi"]["paths"]:
        assert (INGESTION / rel).exists()


def test_ingestion_binaries_materialize(materialized_binaries: dict[str, str]) -> None:
    import zipfile

    zip_path = INGESTION / "zip" / "model_project.zip"
    pdf_path = INGESTION / "pdf" / "model_lossy.pdf"
    assert zipfile.is_zipfile(zip_path)
    assert set(zipfile.ZipFile(zip_path).namelist()) == {"part1.sas", "part2.sas"}
    assert pdf_path.read_bytes().startswith(b"%PDF"), "lossy pdf is not a valid PDF"
    # docx is optional (skipped without python-docx); only assert when built.
    docx_status = materialized_binaries.get("corpus/ingestion/docx/model.docx", "")
    if docx_status == "built":
        assert (INGESTION / "docx" / "model.docx").exists()


# --------------------------------------------------------------------------- #
# Generator (S-10/11/12): seeded, reproducible, covers Part C, emits responses
# --------------------------------------------------------------------------- #
def test_generator_is_seeded_reproducible_and_covers_part_c(tmp_path: Path) -> None:
    gen = _load_tool("gen_synthetic")
    cfg = gen.GenConfig(models=10, tables=6, columns=4, cross_model_edges=3, seed=42)

    m_a = gen.generate(cfg, tmp_path / "a", with_fake_responses=True)
    gen.generate(cfg, tmp_path / "b", with_fake_responses=True)

    # Same seed -> byte-identical manifests (modulo the absolute out path).
    a_txt = (tmp_path / "a" / "manifest.json").read_text("utf-8")
    b_txt = (tmp_path / "b" / "manifest.json").read_text("utf-8")
    assert a_txt == b_txt, "generator is not reproducible for a fixed seed"

    assert len(m_a["models"]) == 10
    # SAS+Python default mix expresses every usage_kind.
    required = {r["usage_kind"] for r in PART_C["rules"]}
    assert required <= set(m_a["coverage"]["usage_kinds"])

    # Each model file and each fake response was written.
    for model in m_a["models"]:
        assert (tmp_path / "a" / model["source_file"]).exists()
    responses = list((tmp_path / "a" / "fake_responses").glob("*.json"))
    assert len(responses) == len(m_a["models"])
    for r in responses:
        json.loads(r.read_text("utf-8"))
