"""SAS adapter (SDD §5.2) — migrates and extends the v1 ``SAS_*_REGEX`` heuristics.

SAS is macro-heavy with no reliable AST, so this is regex/heuristic (the v1
migration path). It emits ``UsageObservation``s for every Part C signal the corpus
``dq_coverage`` SAS twins exercise, with light context disambiguation (e.g. ``BY``
under PROC MEANS is an aggregation grain, not a join key; ``input()`` is a cast,
not a date parse; ``BETWEEN`` is a time window, not a numeric range).
"""

from __future__ import annotations

import re

from modeltracex.adapters.base import DetectionResult, StructuralScan, register
from modeltracex.state import Confidence, Language, Provenance, UsageKind, UsageObservation

# --- structural (migrated from v1, expanded for FR-1.5) ---
RE_DATA_OUT = re.compile(r"\bdata\s+([a-zA-Z0-9_.]+)\s*;", re.I)
RE_SET_IN = re.compile(r"\bset\s+([a-zA-Z0-9_.]+)", re.I)
RE_MERGE_IN = re.compile(r"\bmerge\s+([a-zA-Z0-9_.\s()=]+?);", re.I)
RE_FROM = re.compile(r"\bfrom\s+([a-zA-Z0-9_.]+)", re.I)
RE_CREATE = re.compile(r"create\s+table\s+([a-zA-Z0-9_.]+)", re.I)
RE_PROC_DATA = re.compile(r"\bdata\s*=\s*([a-zA-Z0-9_.]+)", re.I)
RE_OUT_OUT = re.compile(r"\boutput\s+out\s*=\s*([a-zA-Z0-9_.]+)", re.I)
RE_LIBNAME = re.compile(r"\blibname\s+(\w+)\s+[\"']?([^\"';]+)", re.I)
RE_PROC_SQL = re.compile(r"\bproc\s+sql\b", re.I)
RE_PROC_AGG = re.compile(r"\bproc\s+(means|summary|freq)\b", re.I)
RE_TABLE_TOKEN = re.compile(r"[a-zA-Z0-9_.]+")

# --- DQ usage signals (Part C triggers) ---
RE_DIVISOR = re.compile(r"/\s*([a-zA-Z_]\w*)")  # denominator (not a numeric literal)
RE_BY = re.compile(r"\bby\s+([a-zA-Z0-9_.\s]+?);", re.I)
RE_BETWEEN = re.compile(r"\bwhere\b[^;]*?\b(\w+)\s+between\b", re.I)
RE_WHERE_RNG = re.compile(r"\bwhere\b[^;]*?\b(\w+)\s*(?:>|<)\s*\d", re.I)
RE_DATEFUNC = re.compile(r"\b(?:datepart|mdy|intnx)\s*\(\s*(\w+)", re.I)
RE_INPUT = re.compile(r"\binput\s*\(\s*(\w+)", re.I)
RE_INSET = re.compile(r"\b(\w+)\s+in\s*\(", re.I)
RE_ON = re.compile(r"\bon\s+\w+\.(\w+)\s*=", re.I)
RE_GROUPBY = re.compile(r"\bgroup\s+by\s+([a-zA-Z0-9_.,\s]+?)\s*(?:;|having\b|$)", re.I)
RE_ASSIGN = re.compile(r"^\s*(\w+)\s*=", re.M)
RE_KEEP = re.compile(r"\bkeep\s+([\w\s]+);", re.I)
RE_SPLIT = re.compile(r"\b(?:data|proc)\b", re.I)
RE_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
RE_LINE_COMMENT = re.compile(r"(?m)^\s*\*[^;]*;")
RE_STRING = re.compile(r"\"[^\"]*\"|'[^']*'")


def _strip_comments(content: str) -> str:
    """Drop `/* ... */` and `* ... ;` comments so prose never trips the regexes."""
    return RE_LINE_COMMENT.sub(" ", RE_BLOCK_COMMENT.sub(" ", content))


class SASAdapter:
    language = Language.SAS
    file_extensions: tuple[str, ...] = (".sas",)

    def detect(self, filename: str, content: str) -> DetectionResult:
        score, ev = 0.0, []
        if filename.lower().endswith(".sas"):
            score += 0.5
            ev.append("ext .sas")
        if re.search(r"\bdata\b.*;|\bproc\s+\w+", content, re.I):
            score += 0.4
            ev.append("data/proc step")
        if RE_LIBNAME.search(content):
            score += 0.1
            ev.append("libname")
        return DetectionResult(Language.SAS, min(score, 1.0), "; ".join(ev))

    def scan(self, content: str, model_id: str) -> StructuralScan:
        s = StructuralScan()
        code = _strip_comments(content)
        s.libnames = {m.group(1): m.group(2).strip() for m in RE_LIBNAME.finditer(code)}

        merge_tables: set[str] = set()
        for m in RE_MERGE_IN.finditer(code):
            for tok in RE_TABLE_TOKEN.findall(m.group(1)):
                if "=" not in tok and tok.lower() != "in":
                    merge_tables.add(tok)

        # Libnames + merge captured; blank string literals so paths/date-literals
        # (e.g. a libname path "/data/oracle") don't trip the divisor/filter regexes.
        code = RE_STRING.sub(" ", code)

        inputs = (
            {m.group(1) for m in RE_SET_IN.finditer(code)}
            | {m.group(1) for m in RE_FROM.finditer(code)}
            | {m.group(1) for m in RE_PROC_DATA.finditer(code)}
            | merge_tables
        )
        outputs = (
            {m.group(1) for m in RE_DATA_OUT.finditer(code)}
            | {m.group(1) for m in RE_CREATE.finditer(code)}
            | {m.group(1) for m in RE_OUT_OUT.finditer(code)}
        )
        s.inputs = sorted(inputs)
        s.outputs = sorted(outputs)

        has_proc_agg = bool(RE_PROC_AGG.search(code))
        n_libnames = len(s.libnames)

        def obs(
            col: str, kind: UsageKind, evidence: str, conf: Confidence = Confidence.HIGH
        ) -> None:
            s.usages.append(
                UsageObservation(
                    element=col,
                    usage_kind=kind,
                    evidence=evidence.strip(),
                    model_id=model_id,
                    source=Provenance.HEURISTIC,
                    confidence=conf,
                )
            )

        for m in RE_DIVISOR.finditer(code):
            obs(m.group(1), UsageKind.DENOMINATOR, m.group(0))
        for m in RE_BY.finditer(code):
            kind = UsageKind.AGGREGATED if has_proc_agg else UsageKind.JOIN_KEY
            for key in m.group(1).split():
                obs(key, kind, m.group(0))
        for m in RE_GROUPBY.finditer(code):  # PROC SQL GROUP BY -> aggregation grain
            for key in re.split(r"[,\s]+", m.group(1).strip()):
                if key:
                    obs(key, UsageKind.AGGREGATED, m.group(0))
        for m in RE_DATEFUNC.finditer(code):
            obs(m.group(1), UsageKind.DATE_PARSE, m.group(0))
        for m in RE_INPUT.finditer(code):
            obs(m.group(1), UsageKind.TYPE_CAST, m.group(0))
        for m in RE_BETWEEN.finditer(code):
            obs(m.group(1), UsageKind.TIME_WINDOW, m.group(0))
        for m in RE_WHERE_RNG.finditer(code):
            obs(m.group(1), UsageKind.RANGE_FILTER, m.group(0))
        for m in RE_INSET.finditer(code):
            obs(m.group(1), UsageKind.EQUALITY_SET, m.group(0))
        for m in RE_ON.finditer(code):
            kind = UsageKind.CROSS_SYSTEM_JOIN if n_libnames >= 2 else UsageKind.JOIN_KEY
            obs(m.group(1), kind, m.group(0))

        # output_measure: assigned columns explicitly kept in an output step.
        kept = {tok for m in RE_KEEP.finditer(code) for tok in m.group(1).split()}
        if kept:
            assigned = {m.group(1) for m in RE_ASSIGN.finditer(code)}
            for col in sorted(assigned & kept):
                obs(col, UsageKind.OUTPUT_MEASURE, f"{col} = ... ; keep {col}")

        s.split_points = self.split_points(content)
        return s

    def split_points(self, content: str) -> list[int]:
        return [m.start() for m in RE_SPLIT.finditer(content)]

    def prompt_fragment(self) -> str:
        return (
            "The code is SAS. Treat `DATA <x>;` and `PROC SQL ... CREATE TABLE` as output "
            "datasets; `SET`/`MERGE`/`FROM` and `DATA=` as inputs; `BY` variables as "
            "join/group keys; `libname` as a source-system mapping. Resolve two-level "
            "names lib.table. Recognize MERGE as a join and PROC MEANS/SUMMARY as aggregation."
        )


register(SASAdapter())

__all__ = ["SASAdapter"]
