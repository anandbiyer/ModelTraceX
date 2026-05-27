"""Deterministic, content-addressed ID helpers (SDD §9.2, R7).

Stable IDs are load-bearing for NFR-4 (diffable re-runs) and FR-3.3 (idempotent
chunk-merge dedupe): same input -> same id, so diff is a set operation and human
overrides keyed by id survive re-runs. Only ``run_id`` is time-random.

Implemented in Phase 0 (P0-2). ``canonical_table_name`` resolves libname/schema
aliases + case/whitespace so ``work.staging`` written by one model and read by
another collapses to a single ``table_id`` (the cross-model stitch, FR-5.3).
"""

from __future__ import annotations

import hashlib

# Unit-separator join char (SDD §9.2) — unlikely to appear inside a name.
_SEP = "␟"


def _h(*parts: str) -> str:
    """sha1 of the lower/stripped parts, truncated to 12 hex chars (SDD §9.2)."""
    joined = _SEP.join(p.lower().strip() for p in parts)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:12]  # noqa: S324 (id, not security)


def canonical_table_name(name: str, aliases: dict[str, str] | None = None) -> str:
    """Normalize a table reference so equivalent references collapse to one id.

    Lower-cases, collapses internal whitespace, and (for two-level ``lib.table``
    names) resolves the ``lib``/schema part through ``aliases`` (e.g. a SAS
    ``libname`` map) so ``stg.events`` and ``work.events`` become the same name
    when ``stg`` resolves to ``work``.
    """
    n = " ".join(name.strip().split()).lower()
    if "." in n and aliases:
        schema, _, table = n.partition(".")
        low = {k.strip().lower(): v for k, v in aliases.items()}
        if schema in low:
            schema = " ".join(low[schema].strip().split()).lower()
            n = f"{schema}.{table}"
    return n


def table_id(name: str, aliases: dict[str, str] | None = None) -> str:
    return "t_" + _h(canonical_table_name(name, aliases))


def model_id(label: str, files: list[str] | tuple[str, ...]) -> str:
    return "m_" + _h(label, *sorted(files))


def table_edge_id(source_table_id: str, target_table_id: str, model_id: str, ttype: str) -> str:
    return "te_" + _h(source_table_id, target_table_id, model_id, ttype)


def column_edge_id(source_element: str, target_element: str, model_id: str, ttype: str) -> str:
    return "ce_" + _h(source_element, target_element, model_id, ttype)


def rule_id(element: str, dimension: str, statement: str) -> str:
    return "dq_" + _h(element, dimension, statement)


__all__ = [
    "canonical_table_name",
    "table_id",
    "model_id",
    "table_edge_id",
    "column_edge_id",
    "rule_id",
]
