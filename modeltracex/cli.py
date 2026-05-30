"""Headless CLI entrypoint.

Phase 0 (P0-7) adds ``--demo``: a fully offline ``FakeProvider`` run driven
through the orchestrator into a persisted, schema-valid ``RunState`` — the
Phase-0 exit path. The Phase-1 milestone (P1-10) wires real ingestion +
adapters + exporters behind this same entrypoint.
"""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

from modeltracex import __version__
from modeltracex.config import get_settings

if TYPE_CHECKING:
    from modeltracex.llm.provider import LLMProvider
    from modeltracex.state import RunState

_DEMO_M1 = (
    '{"purpose": "Build the staging table from raw customer events.",'
    ' "input_tables": [{"name": "raw.customer_events",'
    ' "columns": ["cust_id", "gross_amount", "tax_amount", "event_type"]}],'
    ' "output_tables": [{"name": "work.staging", "columns": ["cust_id", "amount_net"]}],'
    ' "lineage_rows": ["raw.customer_events.gross_amount -> work.staging.amount_net"]}'
)
_DEMO_M2 = (
    '{"purpose": "Score customers from the staging table.",'
    ' "input_tables": [{"name": "work.staging", "columns": ["cust_id", "amount_net"]}],'
    ' "output_tables": [{"name": "mart.customer_scores", "columns": ["cust_id", "total_net"]}],'
    ' "lineage_rows": ["work.staging.amount_net -> mart.customer_scores.total_net"]}'
)


def _run_demo() -> int:
    from modeltracex.analysis.orchestrator import ModelInput, analyze_run
    from modeltracex.llm.fake import FakeProvider
    from modeltracex.state import Language
    from modeltracex.store.db import RunStore

    provider = FakeProvider(responses={"m1_build_staging": _DEMO_M1, "m2_score": _DEMO_M2})
    inputs = [
        ModelInput(label="m1_build_staging", language=Language.SAS, source_files=["m1.sas"]),
        ModelInput(label="m2_score", language=Language.SAS, source_files=["m2.sas"]),
    ]
    state = analyze_run(provider, inputs)

    store = RunStore(":memory:")
    store.save(state)
    reloaded = store.load(state.run.run_id)

    print(f"FakeProvider demo run: {state.run.run_id}")
    print(
        f"  models={len(state.models)} tables={len(state.tables)} "
        f"table_edges={len(state.table_edges)} source_systems={len(state.source_systems)}"
    )
    for table in state.tables:
        print(f"    [{table.role.value:<12}] {table.name}")
    print(f"  round-trip equal after persist+load: {reloaded == state}")
    return 0


_SOURCE_SUFFIXES = {".sas", ".py", ".r", ".bas", ".vba", ".docx", ".pdf", ".txt"}


def _ingest_paths(paths: list[str]) -> list:
    from pathlib import Path

    from modeltracex.ingestion import read_path, unzip_project

    artifacts = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            for child in sorted(p.rglob("*")):
                if child.is_file() and child.suffix.lower() in _SOURCE_SUFFIXES:
                    artifacts.append(read_path(child))
        elif p.suffix.lower() == ".zip":
            artifacts.extend(unzip_project(p))
        else:
            artifacts.append(read_path(p))
    return artifacts


def run_project(
    paths: list[str], out_dir: str, provider: LLMProvider | None = None
) -> tuple[RunState, list[str]]:
    """Headless: ingest -> analyze -> persist -> export.

    Emits DOCX (Part A), XLSX (Part B, 9 sheets), legacy CSV, Mermaid lineage
    text, Graphviz SVG/PDF lineage, OpenLineage RunEvents (NFR-8), and draw.io
    XML — full parity with the API export endpoint (Phase 4D P4D-1). Any one
    of the lineage/interop exporters that fails (e.g. missing `dot` binary)
    is logged and skipped; the run still produces every other artifact.
    """
    from pathlib import Path

    from modeltracex.analysis.orchestrator import analyze_run
    from modeltracex.exporters.csv_compat import CsvCompatExporter
    from modeltracex.exporters.docx_report import DocxExporter
    from modeltracex.exporters.xlsx_workbook import XlsxExporter
    from modeltracex.ingestion import assemble_models
    from modeltracex.lineage.drawio import DrawioExporter
    from modeltracex.lineage.graph import LineageGraph
    from modeltracex.lineage.openlineage import OpenLineageExporter
    from modeltracex.lineage.render_graphviz import GraphvizRenderer
    from modeltracex.lineage.render_mermaid import MermaidRenderer
    from modeltracex.llm.provider import build_provider
    from modeltracex.security import default_redactor, scrub_for_retention
    from modeltracex.store.db import RunStore

    cfg = get_settings()
    if provider is None:
        provider = build_provider(cfg)

    models = assemble_models(_ingest_paths(paths))
    state = analyze_run(provider, models, redactor=default_redactor())
    state.run.security_mode = cfg.security_mode
    scrub_for_retention(state, retain_source=cfg.retain_source)

    Path(out_dir).mkdir(parents=True, exist_ok=True)
    RunStore(str(Path(out_dir) / "runs.db")).save(state)
    print(f"  run_id: {state.run.run_id}")

    graph = LineageGraph(state)
    outputs: list[str] = []
    outputs += DocxExporter().export(state, out_dir)
    outputs += XlsxExporter().export(state, out_dir)
    outputs += CsvCompatExporter().export(state, out_dir)

    lineage_stem = str(Path(out_dir) / "lineage")
    try:
        outputs.append(MermaidRenderer().render(graph, lineage_stem))
    except Exception as exc:  # noqa: BLE001 — exporter failures should not stall the run
        print(f"  ! mermaid export skipped: {exc}")
    try:
        outputs.append(GraphvizRenderer().render(graph, lineage_stem))
    except Exception as exc:  # noqa: BLE001
        print(f"  ! graphviz SVG/PDF export skipped: {exc}")
    try:
        outputs += OpenLineageExporter().export(state, out_dir)
    except Exception as exc:  # noqa: BLE001
        print(f"  ! OpenLineage export skipped: {exc}")
    try:
        outputs += DrawioExporter().export(state, out_dir)
    except Exception as exc:  # noqa: BLE001
        print(f"  ! draw.io export skipped: {exc}")
    return state, outputs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="modeltracex", description="ModelTraceX v2")
    parser.add_argument("--version", action="version", version=f"modeltracex {__version__}")
    parser.add_argument(
        "--show-config",
        action="store_true",
        help="Print the resolved (secret-free) settings and exit.",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run an offline FakeProvider analysis into a persisted RunState and exit.",
    )
    parser.add_argument(
        "--run", nargs="+", metavar="PATH", help="Analyze files/dirs/zip headlessly and export."
    )
    parser.add_argument(
        "--out", default="output", help="Output directory for --run (default: output)."
    )
    parser.add_argument(
        "--provider", default=None, help="Override the configured provider (e.g. fake)."
    )
    args = parser.parse_args(argv)

    if args.demo:
        return _run_demo()

    if args.run:
        provider = None
        if args.provider:
            import os

            os.environ["MODELTRACEX_PROVIDER"] = args.provider
            from modeltracex.llm.provider import build_provider

            provider = build_provider(get_settings())
        state, outputs = run_project(args.run, args.out, provider)
        print(
            f"Analyzed {len(state.models)} model(s) -> {len(state.tables)} tables, "
            f"{len(state.table_edges)} edges, {len(state.dq_rules)} DQ rules."
        )
        for path in outputs:
            print(f"  wrote {path}")
        return 0

    if args.show_config:
        cfg = get_settings()
        printable = cfg.model_dump(
            exclude={
                "anthropic_api_key",
                "openai_api_key",
                "azure_openai_api_key",
                "azure_openai_endpoint",
            }
        )
        for key, value in printable.items():
            print(f"{key} = {value}")
        return 0

    print(f"ModelTraceX v{__version__} — scaffold. The headless pipeline lands in Phase 1 (P1-10).")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
