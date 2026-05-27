"""Idempotent merge of per-chunk ``ModelExtraction``s (SDD §7.3).

Merging is keyed so that re-seeing the same fact is a no-op: tables merge by name
(union of columns), lineage rows dedupe by (source, target), calculations by
(target, expression). Result: a chunked run and an unchunked run of the same model
produce an identical merged extraction (the idempotence the chunk-merge test asserts).
"""

from __future__ import annotations

from modeltracex.llm.schema import LineageRow, ModelExtraction, TableSpec


def _merge_tables(acc: dict[str, TableSpec], tables: list[TableSpec]) -> None:
    for t in tables:
        existing = acc.get(t.name)
        if existing is None:
            acc[t.name] = TableSpec(name=t.name, columns=list(t.columns))
        else:
            for col in t.columns:
                if col not in existing.columns:
                    existing.columns.append(col)


def merge_extractions(parts: list[ModelExtraction]) -> ModelExtraction:
    if len(parts) == 1:
        return parts[0]

    merged = ModelExtraction()
    inputs: dict[str, TableSpec] = {}
    outputs: dict[str, TableSpec] = {}
    seen_lineage: set[tuple[str, str]] = set()
    seen_calc: set[tuple[str, str]] = set()

    for p in parts:
        merged.purpose = merged.purpose or p.purpose
        merged.executive_summary = merged.executive_summary or p.executive_summary
        for a in p.assumptions:
            if a not in merged.assumptions:
                merged.assumptions.append(a)
        merged.methodology_steps.extend(p.methodology_steps)
        merged.transformations.extend(p.transformations)
        for limitation in p.limitations:
            if limitation not in merged.limitations:
                merged.limitations.append(limitation)
        _merge_tables(inputs, p.input_tables)
        _merge_tables(outputs, p.output_tables)
        for c in p.calculations:
            key = (c.target, c.expression)
            if key not in seen_calc:
                seen_calc.add(key)
                merged.calculations.append(c)
        for r in p.lineage_rows:
            key = (r.source_element, r.target_element)
            if key not in seen_lineage:
                seen_lineage.add(key)
                merged.lineage_rows.append(
                    LineageRow(
                        source_element=r.source_element,
                        target_element=r.target_element,
                        transformation_type=r.transformation_type,
                    )
                )

    merged.input_tables = list(inputs.values())
    merged.output_tables = list(outputs.values())
    return merged


__all__ = ["merge_extractions"]
