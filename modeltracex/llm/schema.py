"""``ModelExtraction`` — the narrower per-model LLM target schema (SDD §4, §6.2).

The orchestrator asks the LLM for one ``ModelExtraction`` per model (not the whole
``RunState``): smaller schemas validate more reliably and keep per-model calls
independent (NFR-7). The orchestrator then assembles ``RunState`` from many
extractions + adapter scans.

The ``mode="before"`` field validators here *are* the replacement for v1's
hand-written ``_normalize_tables`` / ``_normalize_lineage_rows`` (SDD §6.3): the
schema coerces the malformed shapes the LLM emits (tables as dict/string/CSV/None,
lineage rows as scalars) so the ``structured_call`` retry loop only burns a retry
when coercion genuinely can't recover. The corpus set ``fake_provider/malformed``
(S-5) is the golden for this behaviour.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from modeltracex.state import TransformationType


class TableSpec(BaseModel):
    """A table reference the LLM returned: a name plus optional columns."""

    name: str
    columns: list[str] = Field(default_factory=list)

    @field_validator("columns", mode="before")
    @classmethod
    def _coerce_columns(cls, v: Any) -> Any:
        if v is None:
            return []
        if isinstance(v, str):
            return [c.strip() for c in v.split(",") if c.strip()]
        return v


class LineageRow(BaseModel):
    """One source-element → target-element hop the LLM reported."""

    source_element: str
    target_element: str
    transformation_type: TransformationType | None = None


class CalcSpec(BaseModel):
    target: str
    expression: str


class ModelExtraction(BaseModel):
    """What a single LLM call returns for one model. Tolerant on input, strict on shape."""

    purpose: str = ""
    executive_summary: str = ""
    assumptions: list[str] = Field(default_factory=list)
    methodology_steps: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    input_tables: list[TableSpec] = Field(default_factory=list)
    output_tables: list[TableSpec] = Field(default_factory=list)
    transformations: list[str] = Field(default_factory=list)
    calculations: list[CalcSpec] = Field(default_factory=list)
    lineage_rows: list[LineageRow] = Field(default_factory=list)

    @field_validator("input_tables", "output_tables", mode="before")
    @classmethod
    def _coerce_tables(cls, v: Any) -> Any:
        if v is None:
            return []
        if isinstance(v, str):
            # single bare name, or a comma-separated list of names
            return [{"name": n.strip()} for n in v.split(",") if n.strip()]
        if isinstance(v, dict):
            if "name" in v:  # already a single table object
                return [v]
            # a {table_name: [columns]} mapping
            return [{"name": k, "columns": val} for k, val in v.items()]
        if isinstance(v, list):
            out: list[Any] = []
            for item in v:
                out.append({"name": item.strip()} if isinstance(item, str) else item)
            return out
        return v

    @field_validator("lineage_rows", mode="before")
    @classmethod
    def _coerce_lineage(cls, v: Any) -> Any:
        if v is None:
            return []
        if isinstance(v, str):
            v = [v]
        if not isinstance(v, list):
            return v
        out: list[Any] = []
        for item in v:
            if isinstance(item, str):
                if "->" in item:
                    src, tgt = item.split("->", 1)
                    out.append({"source_element": src.strip(), "target_element": tgt.strip()})
                # a scalar with no arrow carries no edge — drop it
            elif isinstance(item, dict):
                row = dict(item)
                if "source" in row and "source_element" not in row:
                    row["source_element"] = row.pop("source")
                if "target" in row and "target_element" not in row:
                    row["target_element"] = row.pop("target")
                out.append(row)
            else:
                out.append(item)
        return out


__all__ = ["TableSpec", "LineageRow", "CalcSpec", "ModelExtraction"]
