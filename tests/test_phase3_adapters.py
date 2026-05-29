"""Phase 3 R + VBA adapter tests (P3-T3).

Drives each language-coverage fixture through its adapter and asserts the
``StructuralScan`` inputs/outputs match the corpus golden and the expected Part C
usages are present (a superset is fine — adapters legitimately find more). Also
asserts detection routes each language to the correct adapter.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import modeltracex.adapters  # noqa: F401  (registers built-ins)
from modeltracex.adapters.base import ADAPTERS, detect_language
from modeltracex.state import Language

LANGUAGES = Path(__file__).parent / "fixtures" / "corpus" / "languages"


def _cases() -> list[tuple[str, str, dict]]:
    out: list[tuple[str, str, dict]] = []
    for lang_dir in ("r", "vba"):
        data = json.loads((LANGUAGES / lang_dir / "expected.json").read_text(encoding="utf-8"))
        for filename, spec in data["fixtures"].items():
            out.append((lang_dir, filename, spec))
    return out


@pytest.mark.parametrize(
    "lang_dir,filename,spec", _cases(), ids=lambda v: v if isinstance(v, str) else ""
)
def test_adapter_structural_scan(lang_dir: str, filename: str, spec: dict) -> None:
    lang = Language.R if lang_dir == "r" else Language.VBA
    code = (LANGUAGES / lang_dir / filename).read_text(encoding="utf-8")
    scan = ADAPTERS[lang].scan(code, "m")

    assert scan.inputs == spec["inputs"], f"{filename} inputs"
    assert scan.outputs == spec["outputs"], f"{filename} outputs"

    found = {(u.element, u.usage_kind.value) for u in scan.usages}
    expected = {(u["element"], u["usage_kind"]) for u in spec["usages"]}
    assert expected <= found, f"{filename} missing {expected - found}"


@pytest.mark.parametrize(
    "filename,expected_lang",
    [
        ("languages/sas/macro_heavy.sas", Language.SAS),
        ("languages/python/etl_pipeline.py", Language.PYTHON),
        ("languages/r/dplyr_pipeline.R", Language.R),
        ("languages/r/model_fit.R", Language.R),
        ("languages/vba/etl_macro.bas", Language.VBA),
        ("languages/vba/report_build.bas", Language.VBA),
    ],
)
def test_detection_routes_to_correct_adapter(filename: str, expected_lang: Language) -> None:
    code = (LANGUAGES.parent / filename).read_text(encoding="utf-8")
    assert detect_language(Path(filename).name, code).language is expected_lang


def test_all_four_adapters_registered() -> None:
    assert {Language.SAS, Language.PYTHON, Language.R, Language.VBA} <= set(ADAPTERS)


def test_r_and_vba_split_points_are_offsets() -> None:
    r_code = (LANGUAGES / "r" / "model_fit.R").read_text(encoding="utf-8")
    vba_code = (LANGUAGES / "vba" / "etl_macro.bas").read_text(encoding="utf-8")
    # VBA has a Sub -> at least one split point; both must be valid char offsets.
    vba_pts = ADAPTERS[Language.VBA].split_points(vba_code)
    assert vba_pts and all(0 <= p <= len(vba_code) for p in vba_pts)
    assert all(0 <= p <= len(r_code) for p in ADAPTERS[Language.R].split_points(r_code))
