"""Legacy 5-column lineage CSV (FR-5.4) — migrates v1 ``write_lineage_csv``.

A flat compatibility export, not a replacement for the XLSX workbook. Prefers
column-level edges; falls back to table-level edges when no column lineage exists.
"""

from __future__ import annotations

import csv
from pathlib import Path

from modeltracex.state import RunState

HEADERS = ["Source Element", "Target Element", "Model ID", "Transformation Type", "Edge ID"]


class CsvCompatExporter:
    fmt = "csv"

    def export(self, state: RunState, out_dir: str) -> list[str]:
        path = Path(out_dir) / "lineage_table.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(HEADERS)
            if state.column_edges:
                for ce in state.column_edges:
                    writer.writerow(
                        [
                            ce.source_element,
                            ce.target_element,
                            ce.model_id,
                            ce.transformation_type.value,
                            ce.edge_id,
                        ]
                    )
            else:
                names = {t.table_id: t.name for t in state.tables}
                for te in state.table_edges:
                    writer.writerow(
                        [
                            names.get(te.source_table_id, te.source_table_id),
                            names.get(te.target_table_id, te.target_table_id),
                            te.model_id,
                            te.transformation_type.value,
                            te.edge_id,
                        ]
                    )
        return [str(path)]


__all__ = ["CsvCompatExporter", "HEADERS"]
