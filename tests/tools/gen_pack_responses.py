#!/usr/bin/env python
"""Derive offline FakeProvider responses + a lineage golden from the sample pack.

The financial sample pack expresses its inputs/outputs only in docstrings and
``# CHAIN_INPUT/CHAIN_OUTPUT`` comments (not as ``read_csv``/``to_csv`` calls), so
the deterministic adapters can't recover the chain offline. This tool reads those
comments + the manifest and emits canned, schema-neutral ``ModelExtraction`` JSON
(keyed by model label) so the pack runs **deterministically offline** through the
real pipeline — the same trick as ``gen_synthetic.py --with-fake-responses``.

It is stdlib-only and operates on the committed copy by default:

    python tests/tools/gen_pack_responses.py            # uses tests/acceptance/sample_pack
    python tests/tools/gen_pack_responses.py --pack <other-pack>

Outputs under ``<pack>/fake_responses/{chained,python,sas}/<label>.json`` and
``<pack>/expected_chain.json`` (the 10-node Source→…→Output golden). Re-running on
unchanged inputs produces no diff.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

DEFAULT_PACK = Path(__file__).resolve().parents[1] / "acceptance" / "sample_pack"

RE_CHAIN_IN = re.compile(r'#\s*CHAIN_INPUT\s*=\s*"([^"]+)"')
RE_CHAIN_OUT = re.compile(r'#\s*CHAIN_OUTPUT\s*=\s*"([^"]+)"')
RE_CHAIN_ORDER = re.compile(r"#\s*CHAIN_ORDER\s*=\s*(\d+)")
RE_PURPOSE = re.compile(r"Purpose:\s*(.+)")


def _docstring_purpose(text: str) -> str:
    m = RE_PURPOSE.search(text)
    if m:
        return m.group(1).strip()
    # else: first non-empty line of a leading triple-quoted docstring
    doc = re.match(r'\s*(?:"""|\'\'\')(.*?)(?:"""|\'\'\')', text, re.S)
    if doc:
        for line in doc.group(1).splitlines():
            if line.strip():
                return line.strip()
    return ""


def _purposes_from_manifest(pack: Path) -> dict[str, str]:
    """Map a file *stem* -> purpose, from manifest.csv (SAS/Python pairs share a stem)."""
    out: dict[str, str] = {}
    manifest = pack / "manifest.csv"
    if not manifest.exists():
        return out
    with manifest.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            stem = Path(row["file"]).stem
            if row.get("purpose"):
                out[stem] = row["purpose"]
    return out


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def generate(pack: Path) -> dict:
    responses_root = pack / "fake_responses"
    manifest_purpose = _purposes_from_manifest(pack)
    summary = {"chained": 0, "python": 0, "sas": 0}

    # --- chained: parse CHAIN_* comments into a stitchable extraction --------- #
    chained: list[tuple[int, str, str, str, str]] = []  # (order, label, input, output, purpose)
    for path in sorted((pack / "chained").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        m_in, m_out, m_ord = (
            RE_CHAIN_IN.search(text),
            RE_CHAIN_OUT.search(text),
            RE_CHAIN_ORDER.search(text),
        )
        if not (m_in and m_out and m_ord):
            continue
        chained.append(
            (
                int(m_ord.group(1)),
                path.stem,
                m_in.group(1),
                m_out.group(1),
                _docstring_purpose(text),
            )
        )
    chained.sort()

    for _order, label, chain_in, chain_out, purpose in chained:
        _write(
            responses_root / "chained" / f"{label}.json",
            {
                "purpose": purpose,
                "input_tables": [{"name": chain_in, "columns": ["record"]}],
                "output_tables": [{"name": chain_out, "columns": ["record"]}],
                "lineage_rows": [f"{chain_in}.record -> {chain_out}.record"],
            },
        )
        summary["chained"] += 1

    # --- standalone python / sas: purpose enrichment (adapter scan does the rest) #
    for path in sorted((pack / "python").glob("*.py")):
        purpose = manifest_purpose.get(path.stem, _docstring_purpose(path.read_text("utf-8")))
        _write(
            responses_root / "python" / f"{path.stem}.json",
            {
                "purpose": purpose,
                "input_tables": [{"name": f"{path.stem}_input"}],
                "output_tables": [{"name": f"{path.stem}_output"}],
            },
        )
        summary["python"] += 1

    for path in sorted((pack / "sas").glob("*.sas")):
        purpose = manifest_purpose.get(path.stem, "")
        _write(responses_root / "sas" / f"{path.stem}.json", {"purpose": purpose})
        summary["sas"] += 1

    # --- expected chain golden: Source -> ... -> Output node path ------------- #
    order = [chained[0][2]] + [c[3] for c in chained] if chained else []
    expected = {
        "node_path": order,
        "edges": [[c[2], c[3]] for c in chained],
        "source": order[0] if order else None,
        "output": order[-1] if order else None,
    }
    (pack / "expected_chain.json").write_text(
        json.dumps(expected, indent=2) + "\n", encoding="utf-8"
    )

    return summary


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--pack", type=Path, default=DEFAULT_PACK)
    args = parser.parse_args(argv)
    summary = generate(args.pack)
    print(f"generated responses under {args.pack / 'fake_responses'}: {summary}")
    print(f"wrote {args.pack / 'expected_chain.json'}")


if __name__ == "__main__":
    main()
