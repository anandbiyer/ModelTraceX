"""R adapter (SDD §5.1) — regex/heuristic over base R + the tidyverse.

R has a tree-sitter-r grammar, but it requires a native build; a focused regex
scanner over the idioms the corpus exercises (``read_*``/``read.*`` I/O, dplyr
``filter``/``group_by``/``*_join``, ``$``-column derivations, ``/`` divisors) is
enough for the deterministic ``StructuralScan`` and avoids a platform-specific
build. Emits the same Part C ``UsageObservation``s as the other adapters.
"""

from __future__ import annotations

import re

from modeltracex.adapters.base import DetectionResult, StructuralScan, line_offsets, register
from modeltracex.state import Confidence, Language, Provenance, UsageKind, UsageObservation

RE_COMMENT = re.compile(r"(?m)#.*$")
RE_STRING = re.compile(r"\"[^\"]*\"|'[^']*'")

# read_csv("x") / read.csv("x") / readRDS("x") / fread("x") -> input path (1st string arg)
RE_READ = re.compile(
    r"\b(?:read_csv2?|read\.csv|read_delim|read_tsv|read_parquet|read_excel|"
    r"read_xlsx|readRDS|fread)\s*\(\s*[\"']([^\"']+)[\"']",
    re.I,
)
# write_csv(df, "x") / write.csv(df, "x", ...) / saveRDS(df, "x") -> output path (2nd arg)
RE_WRITE = re.compile(
    r"\b(?:write_csv2?|write\.csv|write_delim|write_tsv|write_parquet|write_xlsx|"
    r"saveRDS|fwrite)\s*\(\s*[^,]+,\s*[\"']([^\"']+)[\"']",
    re.I,
)
RE_WRITE_DF = re.compile(
    r"\b(?:write_csv2?|write\.csv|write_delim|write_tsv|write_parquet|write_xlsx|"
    r"saveRDS|fwrite)\s*\(\s*([A-Za-z_.][\w.]*)\s*,",
    re.I,
)
RE_JOIN = re.compile(
    r"\b(?:inner_join|left_join|right_join|full_join|semi_join|anti_join|merge)\s*"
    r"\([^;]*?\bby\s*=\s*[\"']([^\"']+)[\"']",
    re.I,
)
RE_GROUP = re.compile(r"\bgroup_by\s*\(([^)]*)\)", re.I)
RE_FILTER = re.compile(r"\bfilter\s*\(([^)]*)\)", re.I)
RE_FILTER_COL = re.compile(r"([A-Za-z_]\w*)\s*(?:>=|<=|>|<)\s*[\d.]")
RE_DIVISOR = re.compile(r"/\s*(?:[\w.]+\$)?([A-Za-z_]\w*)")
RE_ASSIGN_COL = re.compile(r"\b(\w+)\$(\w+)\s*(?:<-|=)\s*[^=]")
RE_FUNC_DEF = re.compile(r"(?m)^\s*[\w.]+\s*(?:<-|=)\s*function\s*\(")


def _last_segment(path: str) -> str:
    return re.split(r"[\\/]", path)[-1]


class RAdapter:
    language = Language.R
    file_extensions: tuple[str, ...] = (".r",)

    def detect(self, filename: str, content: str) -> DetectionResult:
        score, ev = 0.0, []
        if filename.lower().endswith(".r"):
            score += 0.5
            ev.append("ext .R")
        if "<-" in content or "%>%" in content or re.search(r"\blibrary\s*\(", content):
            score += 0.3
            ev.append("R assignment/pipe/library")
        if re.search(r"\b(?:read|write)(?:_|\.)|\bdata\.frame\b|\bdplyr\b", content, re.I):
            score += 0.2
            ev.append("R I/O or dplyr")
        return DetectionResult(Language.R, min(score, 1.0), "; ".join(ev))

    def scan(self, content: str, model_id: str) -> StructuralScan:
        s = StructuralScan()
        code = RE_COMMENT.sub("", content)

        # I/O + joins need the string literals, so capture them before stripping strings.
        s.inputs = sorted({_last_segment(m.group(1)) for m in RE_READ.finditer(code)})
        s.outputs = sorted({_last_segment(m.group(1)) for m in RE_WRITE.finditer(code)})
        written_dfs = {m.group(1) for m in RE_WRITE_DF.finditer(code)}
        join_keys = [m.group(1) for m in RE_JOIN.finditer(code)]

        bare = RE_STRING.sub(" ", code)

        def obs(elem: str, kind: UsageKind, ev: str, conf: Confidence = Confidence.HIGH) -> None:
            s.usages.append(
                UsageObservation(
                    element=elem,
                    usage_kind=kind,
                    evidence=ev.strip(),
                    model_id=model_id,
                    source=Provenance.HEURISTIC,
                    confidence=conf,
                )
            )

        for key in join_keys:
            obs(key, UsageKind.JOIN_KEY, f'by = "{key}"')
        for m in RE_GROUP.finditer(bare):
            for col in re.split(r"[,\s]+", m.group(1).strip()):
                if col:
                    obs(col, UsageKind.AGGREGATED, m.group(0))
        for m in RE_FILTER.finditer(bare):
            for col in RE_FILTER_COL.findall(m.group(1)):
                obs(col, UsageKind.RANGE_FILTER, f"filter({m.group(1).strip()})")
        for m in RE_DIVISOR.finditer(bare):
            obs(m.group(1), UsageKind.DENOMINATOR, m.group(0))
        # output_measure: a `$`-column assigned onto a data frame that is later written out.
        for m in RE_ASSIGN_COL.finditer(bare):
            df, col = m.group(1), m.group(2)
            if df in written_dfs:
                obs(col, UsageKind.OUTPUT_MEASURE, f"{df}${col} <- ...", Confidence.MEDIUM)

        s.split_points = self.split_points(content)
        return s

    def split_points(self, content: str) -> list[int]:
        offsets = line_offsets(content)
        points: list[int] = []
        for m in RE_FUNC_DEF.finditer(content):
            line = content.count("\n", 0, m.start())
            points.append(offsets[line])
        return points

    def prompt_fragment(self) -> str:
        return (
            "The code is R (base + tidyverse). Treat `read_*`/`read.*` as inputs and "
            "`write_*`/`write.*`/`saveRDS` as outputs; `*_join(..., by=)` as join keys; "
            "`group_by`/`summarise` as aggregation; `filter` as a range/value filter; "
            "`df$col <- expr` as a derived output column; `/` as a denominator."
        )


register(RAdapter())

__all__ = ["RAdapter"]
