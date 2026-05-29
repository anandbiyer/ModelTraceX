"""OpenLineage exporter (SDD §8.2, NFR-8, Q4) — Phase 4 P4-1, export-only.

Emits one OpenLineage **RunEvent** per ``ModelDoc``:

- ``run.runId`` = the run's UUID (``RunMeta.run_id``), per-event eventTime.
- ``job`` = ``{namespace=modeltracex, name=<model_id>}`` so the same model across
  re-runs maps to one job — required for catalog-side history.
- ``inputs`` / ``outputs`` = datasets, one per table in the model's I/O set;
  dataset name = canonical ``table.name``.
- Each output dataset carries a ``columnLineage`` facet built from
  ``ColumnEdge``s whose target_element resolves to that output, so the catalog
  ingests **column-level** lineage (NFR-8).

We don't import ``openlineage-python``; the format is small and stable enough to
emit directly as JSON-serializable dicts. The schema-validation test (P4-T2)
checks the structure against vendored required-field rules — a manual Marquez
load is the acceptance gate.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

from modeltracex.state import (
    ColumnEdge,
    ModelDoc,
    RunState,
    Table,
    TableEdge,
)

_PRODUCER = "https://github.com/anthropics/modeltracex/v2"
_SCHEMA_URL = "https://openlineage.io/spec/2-0-2/OpenLineage.json#/$defs/RunEvent"
_FACET_SCHEMA = (
    "https://openlineage.io/spec/facets/1-0-2/ColumnLineageDatasetFacet.json"
    "#/$defs/ColumnLineageDatasetFacet"
)
NAMESPACE = "modeltracex"


def _dataset(table: Table) -> dict[str, object]:
    return {"namespace": NAMESPACE, "name": table.name}


def _column_facet_for(
    output: Table,
    column_edges: list[ColumnEdge],
    table_by_id: dict[str, Table],
) -> dict[str, object] | None:
    """Build the OL columnLineage facet for one output table from its column edges."""
    fields: dict[str, dict[str, object]] = {}
    for edge in column_edges:
        # `table.col` and `db.schema.table.col` both occur; the column is always
        # the final segment, the table is everything before it.
        target_parts = edge.target_element.rsplit(".", 1)
        if len(target_parts) != 2:
            continue
        target_table, target_col = target_parts
        if target_table != output.name or not target_col:
            continue
        source_parts = edge.source_element.rsplit(".", 1)
        if len(source_parts) != 2:
            continue
        source_table, source_col = source_parts
        # The source dataset name is canonical (lower-cased on canonicalization upstream)
        # so the catalog can join across runs by name.
        src_ds_name = table_by_id.get(_table_id_by_name(source_table, table_by_id))
        ds_name = src_ds_name.name if src_ds_name is not None else source_table
        entry = fields.setdefault(
            target_col,
            {"inputFields": [], "transformationType": "DIRECT"},
        )
        input_fields: list[dict[str, str]] = entry["inputFields"]  # type: ignore[assignment]
        input_fields.append(
            {
                "namespace": NAMESPACE,
                "name": ds_name,
                "field": source_col,
                "transformationDescription": edge.expression or "",
                "transformationType": edge.transformation_type.value,
            }
        )
    if not fields:
        return None
    return {
        "_producer": _PRODUCER,
        "_schemaURL": _FACET_SCHEMA,
        "fields": fields,
    }


def _table_id_by_name(name: str, table_by_id: dict[str, Table]) -> str:
    for tid, t in table_by_id.items():
        if t.name == name:
            return tid
    return ""


def _output_dataset(
    table: Table, column_edges: list[ColumnEdge], table_by_id: dict[str, Table]
) -> dict[str, object]:
    ds = _dataset(table)
    facet = _column_facet_for(table, column_edges, table_by_id)
    if facet is not None:
        ds["facets"] = {"columnLineage": facet}
    return ds


def _model_io(model: ModelDoc, state: RunState) -> tuple[list[Table], list[Table]]:
    inputs = [t for t in state.tables if model.model_id in t.consumed_by]
    outputs = [t for t in state.tables if model.model_id in t.produced_by]
    return inputs, outputs


def _edges_for(model_id: str, edges: Iterable[ColumnEdge | TableEdge]) -> list[ColumnEdge]:
    return [e for e in edges if isinstance(e, ColumnEdge) and e.model_id == model_id]


class OpenLineageExporter:
    """Emit one ``RunEvent`` per model and one project-level event keyed off ``RunMeta``."""

    fmt = "openlineage"

    def events(self, state: RunState) -> list[dict[str, object]]:
        table_by_id = {t.table_id: t for t in state.tables}
        # Group column edges by model for the column-facet build.
        column_by_model: dict[str, list[ColumnEdge]] = defaultdict(list)
        for ce in state.column_edges:
            column_by_model[ce.model_id].append(ce)

        events: list[dict[str, object]] = []
        ts = state.run.timestamp
        for model in state.models:
            inputs, outputs = _model_io(model, state)
            event: dict[str, object] = {
                "eventTime": ts,
                "eventType": "COMPLETE",
                "producer": _PRODUCER,
                "schemaURL": _SCHEMA_URL,
                "run": {"runId": state.run.run_id},
                "job": {"namespace": NAMESPACE, "name": model.model_id},
                "inputs": [_dataset(t) for t in inputs],
                "outputs": [
                    _output_dataset(t, column_by_model.get(model.model_id, []), table_by_id)
                    for t in outputs
                ],
            }
            events.append(event)
        return events

    def export(self, state: RunState, out_dir: str) -> list[str]:
        """Write a single newline-delimited-JSON file (one RunEvent per line)."""
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        path = str(Path(out_dir) / "openlineage.jsonl")
        with open(path, "w", encoding="utf-8") as fp:
            for event in self.events(state):
                fp.write(json.dumps(event, sort_keys=True))
                fp.write("\n")
        return [path]


__all__ = ["NAMESPACE", "OpenLineageExporter"]
