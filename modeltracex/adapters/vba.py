"""VBA adapter (SDD §5.1) — heuristic/regex (no robust VBA grammar exists).

Worksheets act as the tables: a ``Set ws = Worksheets("Name")`` binding maps a
variable to a sheet; a sheet written to (``ws.Cells(r, c).Value = ...``) is an
output, one read from is an input. ``Cells(row, N)`` columns are surfaced as
``<sheet>.colN`` so divisor/range signals carry a meaningful element (the corpus
VBA twins assert exactly this shape).
"""

from __future__ import annotations

import re

from modeltracex.adapters.base import DetectionResult, StructuralScan, line_offsets, register
from modeltracex.state import Confidence, Language, Provenance, UsageKind, UsageObservation

RE_COMMENT = re.compile(r"(?m)'.*$")
RE_SHEET_BIND = re.compile(
    r"\bSet\s+(\w+)\s*=\s*(?:\w+\.)*(?:Sheets|Worksheets)\(\s*\"([^\"]+)\"\s*\)", re.I
)
# An assignment whose LHS is a worksheet cell/range write: `ws.Cells(r, c).Value = ...`
RE_ASSIGN = re.compile(r"^\s*(\w+)\.(?:Cells|Range)\([^)]*\)(?:\.\w+)*\s*=(?!=)", re.I)
RE_REF = re.compile(r"(\w+)\.(?:Cells|Range|UsedRange)", re.I)
RE_DIVISOR = re.compile(r"/\s*(\w+)\.Cells\(\s*\w+\s*,\s*(\d+)\s*\)", re.I)
RE_RANGE = re.compile(
    r"(\w+)\.Cells\(\s*\w+\s*,\s*(\d+)\s*\)(?:\.Value)?\s*(?:>=|<=|>|<)\s*[\d.]", re.I
)
RE_SUB = re.compile(r"(?im)^\s*(?:Public\s+|Private\s+)?(?:Sub|Function)\s+\w+")


class VBAAdapter:
    language = Language.VBA
    file_extensions: tuple[str, ...] = (".bas", ".vba", ".cls")

    def detect(self, filename: str, content: str) -> DetectionResult:
        score, ev = 0.0, []
        if filename.lower().endswith((".bas", ".vba", ".cls")):
            score += 0.5
            ev.append("ext .bas/.vba/.cls")
        if re.search(r"(?im)^\s*(?:Public\s+|Private\s+)?(?:Sub|Function)\s+\w+", content):
            score += 0.3
            ev.append("Sub/Function")
        if re.search(r"\b(?:Dim|Worksheet|ThisWorkbook|Attribute\s+VB_Name)\b", content):
            score += 0.2
            ev.append("VBA keywords")
        return DetectionResult(Language.VBA, min(score, 1.0), "; ".join(ev))

    def scan(self, content: str, model_id: str) -> StructuralScan:
        s = StructuralScan()
        code = RE_COMMENT.sub("", content)
        var2sheet = {m.group(1): m.group(2) for m in RE_SHEET_BIND.finditer(code)}

        write_vars: set[str] = set()
        read_vars: set[str] = set()
        for raw in code.splitlines():
            line = raw.strip()
            assign = RE_ASSIGN.match(line)
            if assign:
                write_vars.add(assign.group(1))
                rhs = line.split("=", 1)[1]
                read_vars.update(m.group(1) for m in RE_REF.finditer(rhs))
            else:
                read_vars.update(m.group(1) for m in RE_REF.finditer(line))

        s.outputs = sorted({var2sheet[v] for v in write_vars if v in var2sheet})
        out_set = set(s.outputs)
        s.inputs = sorted(
            {var2sheet[v] for v in read_vars if v in var2sheet and var2sheet[v] not in out_set}
        )

        def obs(elem: str, kind: UsageKind, ev: str) -> None:
            s.usages.append(
                UsageObservation(
                    element=elem,
                    usage_kind=kind,
                    evidence=ev.strip(),
                    model_id=model_id,
                    source=Provenance.HEURISTIC,
                    confidence=Confidence.HIGH,
                )
            )

        for m in RE_DIVISOR.finditer(code):
            sheet = var2sheet.get(m.group(1), m.group(1))
            obs(f"{sheet}.col{m.group(2)}", UsageKind.DENOMINATOR, m.group(0))
        for m in RE_RANGE.finditer(code):
            sheet = var2sheet.get(m.group(1), m.group(1))
            obs(f"{sheet}.col{m.group(2)}", UsageKind.RANGE_FILTER, m.group(0))

        s.split_points = self.split_points(content)
        return s

    def split_points(self, content: str) -> list[int]:
        offsets = line_offsets(content)
        return [offsets[content.count(chr(10), 0, m.start())] for m in RE_SUB.finditer(content)]

    def prompt_fragment(self) -> str:
        return (
            "The code is VBA (Excel macros). Treat each worksheet as a table: a sheet "
            "written via `ws.Cells/.Range = ...` is an output, one read from is an input; "
            "`Cells(row, N)` is column N of that sheet. Recognize `/` as a denominator and "
            "`> n` comparisons as range filters."
        )


register(VBAAdapter())

__all__ = ["VBAAdapter"]
