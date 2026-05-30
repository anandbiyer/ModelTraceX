"""SAS adapter (SDD §5.2) — migrates and extends the v1 ``SAS_*_REGEX`` heuristics.

SAS is macro-heavy with no reliable AST, so this is regex/heuristic (the v1
migration path). It emits ``UsageObservation``s for every Part C signal the corpus
``dq_coverage`` SAS twins exercise, with light context disambiguation (e.g. ``BY``
under PROC MEANS is an aggregation grain, not a join key; ``input()`` is a cast,
not a date parse; ``BETWEEN`` is a time window, not a numeric range).

Phase 4D follow-up fixes two issues caught against the financial sample pack:

1. **Bogus column names from function calls** (e.g. ``/ max(...)`` capturing
   ``max`` as a denominator column). Solved by a negative-lookahead on the
   divisor regex + a stoplist of SAS reserved words / function names applied
   uniformly in ``obs()``.
2. **Bare column elements** (``balance``) instead of ``table.column`` —
   reviewers couldn't tell which table a DQ rule applied to. Solved by a
   linear-scan ``_scope_for(pos)`` that resolves the surrounding DATA step,
   PROC SQL ``CREATE TABLE``, or ``FROM`` target and qualifies every emitted
   element as ``<table>.<column>``.
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
RE_RUN = re.compile(r"\b(?:run|quit)\s*;", re.I)
RE_DATA_STEP = re.compile(r"\bdata\s+([a-zA-Z0-9_.]+)\s*;", re.I)
RE_CREATE_TABLE = re.compile(r"\bcreate\s+table\s+([a-zA-Z0-9_.]+)\s+as\b", re.I)
RE_FROM_TABLE = re.compile(r"\bfrom\s+([a-zA-Z0-9_.]+)", re.I)

# --- DQ usage signals (Part C triggers) ---
# Negative lookahead `(?!\s*\()` excludes function calls like `/ max(...)` so
# SAS function names never get captured as denominator columns (P4D-7). The
# `\b` between the capture and the lookahead prevents the regex engine from
# backtracking inside the identifier — without it, `/ max(...)` would shrink
# the capture from "max" to "ma" to make the lookahead succeed.
RE_DIVISOR = re.compile(r"/\s*([a-zA-Z_]\w*)\b(?!\s*\()")
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

# Stoplist of SAS reserved words + built-in function names. Any "column" capture
# whose lower-cased name lands here is dropped — these are language tokens, not
# data elements. Kept conservative: only names that would never sensibly be a
# real column name (e.g. `count`, `max` could collide if a project literally has
# a column called `count`; we accept that tradeoff because the false-positive
# rate of NOT excluding them is much higher).
_SAS_NON_COLUMNS: frozenset[str] = frozenset(
    {
        # SQL keywords
        "calculated",
        "case",
        "when",
        "then",
        "else",
        "end",
        "having",
        "where",
        "from",
        "as",
        "null",
        "distinct",
        "union",
        "select",
        "by",
        "on",
        "and",
        "or",
        "not",
        "is",
        "in",
        # Aggregate / numeric functions
        "max",
        "min",
        "sum",
        "avg",
        "count",
        "mean",
        "var",
        "std",
        "range",
        "abs",
        "log",
        "log2",
        "log10",
        "exp",
        "sqrt",
        "floor",
        "ceil",
        "round",
        "int",
        "mod",
        "lag",
        "dif",
        "missing",
        "coalesce",
        "nmiss",
        "cmiss",
        "rand",
        "ranuni",
        "streaminit",
        # String functions
        "substr",
        "cats",
        "catx",
        "compress",
        "upcase",
        "lowcase",
        "put",
        "input",
        "length",
        "index",
        "scan",
        "strip",
        "trim",
        "tranwrd",
        "translate",
        "left",
        "right",
        "find",
        "verify",
        # Date / time functions
        "mdy",
        "datepart",
        "intnx",
        "intck",
        "today",
        "date",
        "datetime",
        "time",
        "year",
        "month",
        "day",
        "weekday",
        "qtr",
        "hms",
        "dhms",
        # SAS control keywords
        "run",
        "quit",
        "do",
        "to",
        "while",
        "until",
        "if",
        "output",
        "set",
        "merge",
        "data",
        "proc",
        "format",
        "informat",
        "options",
        "macro",
        "mend",
        "let",
        "global",
        "local",
    }
)


def _strip_comments(content: str) -> str:
    """Drop `/* ... */` and `* ... ;` comments so prose never trips the regexes."""
    return RE_LINE_COMMENT.sub(" ", RE_BLOCK_COMMENT.sub(" ", content))


def _build_scopes(code: str) -> list[tuple[int, int, str]]:
    """Linear-scan the (comment-stripped) code into ``(start, end, table)`` scopes.

    A *scope* is the region inside one DATA step or one PROC SQL CREATE TABLE
    block; emitted usages inside that region get the table as their qualifier.
    We prefer the **source** table (the SET/FROM/MERGE target inside the block)
    because that's where the column physically lives — a ``where amount > 1000``
    inside ``data work.large; set sales.orders;`` belongs to ``sales.orders.amount``,
    not ``work.large.amount``. We fall back to the output table only when the
    block has no readable input (e.g. a synthetic ``do ... output`` generator).
    Selecting the **innermost** scope when ranges overlap keeps nested PROC SQL
    inside a DATA step from being mis-qualified.
    """
    scopes: list[tuple[int, int, str]] = []

    def _scope_end_from(start: int) -> int:
        """Find the matching ``run;`` / ``quit;`` after ``start``; else EOF."""
        m = RE_RUN.search(code, pos=start)
        return m.end() if m else len(code)

    def _input_in(start: int, end: int) -> str | None:
        """First SET/FROM/MERGE target inside [start, end), or None."""
        block = code[start:end]
        for pattern in (RE_SET_IN, RE_FROM, RE_PROC_DATA):
            m = pattern.search(block)
            if m:
                return m.group(1)
        for m in RE_MERGE_IN.finditer(block):
            for tok in RE_TABLE_TOKEN.findall(m.group(1)):
                if "=" not in tok and tok.lower() != "in":
                    return tok
        return None

    for m in RE_DATA_STEP.finditer(code):
        end = _scope_end_from(m.end())
        scopes.append((m.start(), end, _input_in(m.end(), end) or m.group(1)))
    for m in RE_CREATE_TABLE.finditer(code):
        end = _scope_end_from(m.end())
        # PROC SQL: source is the FROM inside the block; fall back to the
        # created-table name if there's no FROM (rare).
        scopes.append((m.start(), end, _input_in(m.end(), end) or m.group(1)))
    # Sort by start so binary lookups in `_scope_for` are deterministic.
    scopes.sort(key=lambda s: s[0])
    return scopes


def _scope_for(pos: int, scopes: list[tuple[int, int, str]]) -> str | None:
    """Return the smallest enclosing scope's table name, or ``None``."""
    enclosing = [(end - start, table) for start, end, table in scopes if start <= pos < end]
    if not enclosing:
        return None
    enclosing.sort()  # smallest range wins (innermost block)
    return enclosing[0][1]


def _qualify(table: str | None, column: str) -> str:
    """Combine table + column into a Spec-shaped element, or fall back to bare."""
    return f"{table}.{column}" if table else column


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
        scopes = _build_scopes(code)

        def obs(
            col: str,
            kind: UsageKind,
            m: re.Match[str],
            conf: Confidence = Confidence.HIGH,
        ) -> None:
            """Emit a usage observation, qualified with the enclosing table.

            Drops captures whose name is a SAS reserved word / function (P4D fix);
            qualifies the rest as ``<table>.<column>`` when a scope is in effect.
            """
            if not col or col.lower() in _SAS_NON_COLUMNS:
                return
            element = _qualify(_scope_for(m.start(), scopes), col)
            s.usages.append(
                UsageObservation(
                    element=element,
                    usage_kind=kind,
                    evidence=m.group(0).strip(),
                    model_id=model_id,
                    source=Provenance.HEURISTIC,
                    confidence=conf,
                )
            )

        for m in RE_DIVISOR.finditer(code):
            obs(m.group(1), UsageKind.DENOMINATOR, m)
        for m in RE_BY.finditer(code):
            kind = UsageKind.AGGREGATED if has_proc_agg else UsageKind.JOIN_KEY
            for key in m.group(1).split():
                obs(key, kind, m)
        for m in RE_GROUPBY.finditer(code):  # PROC SQL GROUP BY -> aggregation grain
            for key in re.split(r"[,\s]+", m.group(1).strip()):
                if key:
                    obs(key, UsageKind.AGGREGATED, m)
        for m in RE_DATEFUNC.finditer(code):
            obs(m.group(1), UsageKind.DATE_PARSE, m)
        for m in RE_INPUT.finditer(code):
            obs(m.group(1), UsageKind.TYPE_CAST, m)
        for m in RE_BETWEEN.finditer(code):
            obs(m.group(1), UsageKind.TIME_WINDOW, m)
        for m in RE_WHERE_RNG.finditer(code):
            obs(m.group(1), UsageKind.RANGE_FILTER, m)
        for m in RE_INSET.finditer(code):
            obs(m.group(1), UsageKind.EQUALITY_SET, m)
        for m in RE_ON.finditer(code):
            kind = UsageKind.CROSS_SYSTEM_JOIN if n_libnames >= 2 else UsageKind.JOIN_KEY
            obs(m.group(1), kind, m)

        # output_measure: assigned columns explicitly kept in an output step.
        # Scoped per `keep` statement so the element is qualified with its DATA
        # step's table (the global cross-scope dedupe from v1 dropped table id).
        for keep_m in RE_KEEP.finditer(code):
            kept_in_scope = set(keep_m.group(1).split())
            if not kept_in_scope:
                continue
            scope_table = _scope_for(keep_m.start(), scopes)
            # Limit assignment scan to the same scope so we don't cross DATA boundaries.
            scope_range = next(
                ((start, end) for start, end, _ in scopes if start <= keep_m.start() < end),
                (0, len(code)),
            )
            block = code[scope_range[0] : scope_range[1]]
            assigned_here = {am.group(1) for am in RE_ASSIGN.finditer(block)}
            for col in sorted(assigned_here & kept_in_scope):
                if col.lower() in _SAS_NON_COLUMNS:
                    continue
                s.usages.append(
                    UsageObservation(
                        element=_qualify(scope_table, col),
                        usage_kind=UsageKind.OUTPUT_MEASURE,
                        evidence=f"{col} = ... ; keep {col}",
                        model_id=model_id,
                        source=Provenance.HEURISTIC,
                        confidence=Confidence.HIGH,
                    )
                )

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
