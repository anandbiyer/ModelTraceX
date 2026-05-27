"""Python adapter (SDD §5.1/§5.2) — stdlib ``ast`` (tree-sitter deferred to Phase 3).

``ast`` gives a high-fidelity call/assignment graph, which is enough for the
deterministic ``StructuralScan``: pandas ``read_*``/``to_*`` as inputs/outputs,
and the Part C usage signals (``/`` divisor, ``merge(on=)``, ``groupby().agg``,
``to_datetime``, ``.astype``, ``.isin``, ``.between``, numeric comparison filter,
assigned-then-written output measures). Split points are the top-level ``def``s.
"""

from __future__ import annotations

import ast

from modeltracex.adapters.base import DetectionResult, StructuralScan, line_offsets, register
from modeltracex.state import Confidence, Language, Provenance, UsageKind, UsageObservation

_READ = {"read_csv", "read_parquet", "read_sql", "read_table", "read_excel", "read_json"}
_WRITE = {"to_csv", "to_parquet", "to_sql", "to_excel", "to_json"}


def _str_arg(node: ast.expr | None) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _col(node: ast.expr | None) -> str | None:
    """The column name for a `df["col"]` subscript (or None)."""
    if isinstance(node, ast.Subscript):
        return _str_arg(node.slice)
    return None


class _Scanner(ast.NodeVisitor):
    def __init__(self, model_id: str) -> None:
        self.model_id = model_id
        self.scan = StructuralScan()
        self._read_kinds: set[str] = set()
        self._assigned_cols: list[str] = []
        self._has_output = False

    def _obs(self, col: str | None, kind: UsageKind, evidence: str) -> None:
        if col:
            self.scan.usages.append(
                UsageObservation(
                    element=col,
                    usage_kind=kind,
                    evidence=evidence,
                    model_id=self.model_id,
                    source=Provenance.HEURISTIC,
                    confidence=Confidence.HIGH,
                )
            )

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            first = node.args[0] if node.args else None
            if attr in _READ:
                self._read_kinds.add(attr)
                path = _str_arg(first)
                if path and attr != "read_sql":
                    self.scan.inputs.append(path)
            elif attr in _WRITE:
                self._has_output = True
                path = _str_arg(first)
                if path:
                    self.scan.outputs.append(path)
            elif attr in {"merge", "join"}:
                key = next((_str_arg(kw.value) for kw in node.keywords if kw.arg == "on"), None)
                self._obs(key, UsageKind.JOIN_KEY, f".{attr}(on={key!r})")
            elif attr == "groupby":
                self._obs(_str_arg(first), UsageKind.AGGREGATED, ".groupby(...)")
            elif attr == "to_datetime":
                self._obs(_col(first), UsageKind.DATE_PARSE, "to_datetime(...)")
            elif attr == "astype":
                self._obs(_col(node.func.value), UsageKind.TYPE_CAST, ".astype(...)")
            elif attr == "isin":
                self._obs(_col(node.func.value), UsageKind.EQUALITY_SET, ".isin([...])")
            elif attr == "between":
                self._obs(_col(node.func.value), UsageKind.TIME_WINDOW, ".between(...)")
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp) -> None:
        if isinstance(node.op, ast.Div):
            col = _col(node.right) or (node.right.id if isinstance(node.right, ast.Name) else None)
            self._obs(col, UsageKind.DENOMINATOR, "x / <col>")
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> None:
        if (
            len(node.ops) == 1
            and isinstance(node.ops[0], ast.Gt | ast.Lt | ast.GtE | ast.LtE)
            and isinstance(node.comparators[0], ast.Constant)
            and isinstance(node.comparators[0].value, int | float)
        ):
            self._obs(_col(node.left), UsageKind.RANGE_FILTER, "df[col] > n")
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            col = _col(target)
            if col:
                self._assigned_cols.append(col)
        self.generic_visit(node)


class PythonAdapter:
    language = Language.PYTHON
    file_extensions: tuple[str, ...] = (".py",)

    def detect(self, filename: str, content: str) -> DetectionResult:
        score, ev = 0.0, []
        if filename.lower().endswith(".py"):
            score += 0.5
            ev.append("ext .py")
        try:
            ast.parse(content)
            score += 0.3
            ev.append("parses as python")
        except SyntaxError:
            pass
        if "import pandas" in content or "pd." in content:
            score += 0.2
            ev.append("pandas")
        return DetectionResult(Language.PYTHON, min(score, 1.0), "; ".join(ev))

    def scan(self, content: str, model_id: str) -> StructuralScan:
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return StructuralScan()
        scanner = _Scanner(model_id)
        scanner.visit(tree)
        s = scanner.scan

        # output_measure: a column assigned in-frame that is later written out.
        if scanner._has_output:
            for col in dict.fromkeys(scanner._assigned_cols):
                s.usages.append(
                    UsageObservation(
                        element=col,
                        usage_kind=UsageKind.OUTPUT_MEASURE,
                        evidence=f'df["{col}"] = ...; df.to_*()',
                        model_id=model_id,
                        source=Provenance.HEURISTIC,
                        confidence=Confidence.MEDIUM,
                    )
                )
        # cross_system_join: a join whose two reads came from different system kinds.
        if len(scanner._read_kinds) >= 2:
            for u in s.usages:
                if u.usage_kind is UsageKind.JOIN_KEY:
                    u.usage_kind = UsageKind.CROSS_SYSTEM_JOIN

        s.inputs = sorted(set(s.inputs))
        s.outputs = sorted(set(s.outputs))
        s.split_points = self.split_points(content)
        return s

    def split_points(self, content: str) -> list[int]:
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return []
        offsets = line_offsets(content)
        return [
            offsets[node.lineno - 1]
            for node in tree.body
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        ]

    def prompt_fragment(self) -> str:
        return (
            "The code is Python (pandas). Treat `pd.read_*` as inputs and `df.to_*` as "
            "outputs; `merge`/`join` `on=` as join keys; `groupby().agg` as aggregation; "
            "`/` as a denominator; `to_datetime` as a date parse; `.astype` as a cast."
        )


register(PythonAdapter())

__all__ = ["PythonAdapter"]
