#!/usr/bin/env python
"""Parametric synthetic-corpus generator (Phase S, activities S-10/11/12).

Emits valid-enough synthetic SAS / Python / R / VBA projects from templates with
controllable knobs, so later phases can exercise scale (bounded concurrency,
rate limiting, chunking, large-graph rendering) without real client IP and
without a live LLM. The RNG is fully seeded, so a given ``--seed`` always
produces an identical project + manifest.

    # 50-model project with matching FakeProvider responses
    python tests/tools/gen_synthetic.py --models 50 --seed 7 --with-fake-responses \
        --out tests/fixtures/corpus/_generated/scale_50

    # 500-model stress project (sources only)
    python tests/tools/gen_synthetic.py --models 500 --seed 7 \
        --out tests/fixtures/corpus/_generated/scale_500

Knobs: ``--models``, ``--tables`` (source pool), ``--columns`` (per table),
``--cross-model-edges`` (staging hand-offs), ``--dq-mix`` (usage_kinds cycled
across models), ``--language-mix``, ``--chunk-pressure`` (extra steps per model
to inflate size). ``--with-fake-responses`` also writes a schema-neutral
``ModelExtraction``-shaped JSON per model under ``fake_responses/``.
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path

# usage_kinds the generator knows how to inject, with their canonical file ext.
ALL_DQ = [
    "denominator",
    "join_key",
    "date_parse",
    "range_filter",
    "aggregated",
    "type_cast",
    "equality_set",
    "output_measure",
    "time_window",
    "cross_system_join",
]
EXT = {"SAS": ".sas", "Python": ".py", "R": ".R", "VBA": ".bas"}
SEMANTIC_COLS = ["cust_id", "amount", "txn_ts", "status", "region", "score", "headcount"]


@dataclass
class GenConfig:
    models: int = 10
    tables: int = 8
    columns: int = 6
    cross_model_edges: int = 3
    chunk_pressure: int = 0
    dq_mix: list[str] = field(default_factory=lambda: list(ALL_DQ))
    language_mix: list[str] = field(default_factory=lambda: ["SAS", "Python"])
    seed: int = 0


# --------------------------------------------------------------------------- #
# DQ snippet injectors — return (lines, usage{element,usage_kind}) per language
# --------------------------------------------------------------------------- #
def _sas_snippet(kind: str, inp: str, cols: list[str]) -> tuple[list[str], dict]:
    c = cols[0]
    if kind == "denominator":
        return ([f"    ratio = amount / {c};"], {"element": f"{inp}.{c}", "usage_kind": kind})
    if kind == "join_key":
        return (["    by cust_id;"], {"element": "cust_id", "usage_kind": kind})
    if kind == "date_parse":
        return ([f"    d = datepart({c});"], {"element": f"{inp}.{c}", "usage_kind": kind})
    if kind == "range_filter":
        return ([f"    where {c} > 1000;"], {"element": f"{inp}.{c}", "usage_kind": kind})
    if kind == "type_cast":
        return ([f"    n = input({c}, 8.);"], {"element": f"{inp}.{c}", "usage_kind": kind})
    if kind == "equality_set":
        return ([f"    where {c} in ('A', 'B');"], {"element": f"{inp}.{c}", "usage_kind": kind})
    if kind == "output_measure":
        return (["    score = amount * 0.5;"], {"element": "score", "usage_kind": kind})
    if kind == "time_window":
        return (
            ["    where txn_ts between '01JAN2026'd and '31MAR2026'd;"],
            {"element": f"{inp}.txn_ts", "usage_kind": kind},
        )
    # aggregated / cross_system_join handled by the caller (need step shape changes)
    return ([f"    v = {c};"], {"element": f"{inp}.{c}", "usage_kind": kind})


def _py_snippet(kind: str, df: str, inp: str, cols: list[str]) -> tuple[list[str], dict]:
    c = cols[0]
    mapping = {
        "denominator": (
            f'    {df}["ratio"] = {df}["amount"] / {df}["{c}"]',
            {"element": f"{inp}.{c}", "usage_kind": kind},
        ),
        "date_parse": (
            f'    {df}["d"] = pd.to_datetime({df}["{c}"])',
            {"element": f"{inp}.{c}", "usage_kind": kind},
        ),
        "range_filter": (
            f'    {df} = {df}[{df}["{c}"] > 1000]',
            {"element": f"{inp}.{c}", "usage_kind": kind},
        ),
        "type_cast": (
            f'    {df}["n"] = {df}["{c}"].astype(float)',
            {"element": f"{inp}.{c}", "usage_kind": kind},
        ),
        "equality_set": (
            f'    {df} = {df}[{df}["{c}"].isin(["A", "B"])]',
            {"element": f"{inp}.{c}", "usage_kind": kind},
        ),
        "output_measure": (
            f'    {df}["score"] = {df}["amount"] * 0.5',
            {"element": "score", "usage_kind": kind},
        ),
        "time_window": (
            f'    {df} = {df}[{df}["txn_ts"].between("2026-01-01", "2026-03-31")]',
            {"element": f"{inp}.txn_ts", "usage_kind": kind},
        ),
    }
    if kind in mapping:
        line, usage = mapping[kind]
        return ([line], usage)
    return ([f'    {df}["v"] = {df}["{c}"]'], {"element": f"{inp}.{c}", "usage_kind": kind})


# --------------------------------------------------------------------------- #
# Language emitters
# --------------------------------------------------------------------------- #
def _emit_sas(
    out: str, inputs: list[str], kind: str, cols: list[str], chunk: int
) -> tuple[str, dict]:
    lines = [f"/* generated SAS model -> {out} (dq: {kind}) */"]
    usage: dict
    if kind == "aggregated":
        lines += [
            f"proc means data={inputs[0]} noprint;",
            "    by region;",
            "    var amount;",
            f"    output out={out}_s0 sum=total_amount;",
            "run;",
        ]
        usage = {"element": f"{inputs[0]}.region", "usage_kind": kind}
    elif kind == "cross_system_join" and len(inputs) >= 2:
        lines += [
            'libname sysa "/data/a";',
            'libname sysb "/data/b";',
            "proc sql;",
            f"    create table {out}_s0 as",
            f"    select a.cust_id from {inputs[0]} as a",
            f"    inner join {inputs[1]} as b on a.cust_id = b.cust_id;",
            "quit;",
        ]
        usage = {"element": "cust_id", "usage_kind": kind}
    elif kind == "join_key" and len(inputs) >= 2:
        lines += [
            f"data {out}_s0;",
            f"    merge {inputs[0]} {inputs[1]};",
            "    by cust_id;",
            "run;",
        ]
        usage = {"element": "cust_id", "usage_kind": kind}
    else:
        snip, usage = _sas_snippet(kind, inputs[0], cols)
        lines += [f"data {out}_s0;", f"    set {inputs[0]};", *snip, "run;"]

    prev = f"{out}_s0"
    for n in range(1, chunk + 1):
        cur = f"{out}_s{n}"
        lines += [
            "",
            f"data {cur};",
            f"    set {prev};",
            f"    p{n} = p{n - 1 if n > 1 else 0} + 1;",
            "run;",
        ]
        prev = cur
    lines += ["", f"data {out};", f"    set {prev};", "run;", ""]
    return "\n".join(lines), usage


def _emit_python(
    out: str, inputs: list[str], kind: str, cols: list[str], chunk: int
) -> tuple[str, dict]:
    df = "df"
    lines = [f'"""generated Python model -> {out} (dq: {kind})."""', "", "import pandas as pd", ""]
    for i, inp in enumerate(inputs):
        lines.append(f'r{i} = pd.read_csv("{_csv(inp)}")')
    lines.append("")
    lines.append("def build():")
    if kind == "aggregated":
        lines.append(
            f'    {df} = r0.groupby("region").agg(total_amount=("amount", "sum")).reset_index()'
        )
        usage = {"element": f"{inputs[0]}.region", "usage_kind": kind}
    elif kind in ("join_key", "cross_system_join") and len(inputs) >= 2:
        lines.append(f'    {df} = r0.merge(r1, on="cust_id", how="inner")')
        usage = {"element": "cust_id", "usage_kind": kind}
    else:
        lines.append(f"    {df} = r0")
        snip, usage = _py_snippet(kind, df, inputs[0], cols)
        lines += snip
    for n in range(1, chunk + 1):
        lines.append(f'    {df}["p{n}"] = {df}.get("p{n - 1}", 0)')
    lines.append(f'    {df}.to_csv("{_csv(out)}", index=False)')
    lines += ["", 'if __name__ == "__main__":', "    build()", ""]
    return "\n".join(lines), usage


def _emit_r(
    out: str, inputs: list[str], kind: str, cols: list[str], chunk: int
) -> tuple[str, dict]:
    lines = [
        f"# generated R model -> {out} (dq: {kind})",
        "library(readr)",
        f'd <- read_csv("{_csv(inputs[0])}")',
    ]
    if kind == "denominator":
        lines.append(f"d$ratio <- d$amount / d${cols[0]}")
        usage = {"element": f"{inputs[0]}.{cols[0]}", "usage_kind": kind}
    elif kind == "range_filter":
        lines.append(f"d <- d[d${cols[0]} > 1000, ]")
        usage = {"element": f"{inputs[0]}.{cols[0]}", "usage_kind": kind}
    else:
        lines.append(f"d$v <- d${cols[0]}")
        usage = {"element": f"{inputs[0]}.{cols[0]}", "usage_kind": kind}
    lines.append(f'write_csv(d, "{_csv(out)}")')
    return "\n".join(lines) + "\n", usage


def _emit_vba(
    out: str, inputs: list[str], kind: str, cols: list[str], chunk: int
) -> tuple[str, dict]:
    sheet_in = _sheet(inputs[0])
    sheet_out = _sheet(out)
    lines = [
        f'Attribute VB_Name = "Mod_{sheet_out}"',
        f"' generated VBA model -> {out} (dq: {kind})",
        "Sub Build()",
        "    Dim src As Worksheet, dst As Worksheet",
        f'    Set src = Worksheets("{sheet_in}")',
        f'    Set dst = Worksheets("{sheet_out}")',
        "    Dim r As Long",
        "    For r = 2 To src.UsedRange.Rows.Count",
    ]
    if kind == "range_filter":
        lines += [
            "        If src.Cells(r, 2).Value > 1000 Then",
            "            dst.Cells(r, 1).Value = src.Cells(r, 1).Value",
            "        End If",
        ]
        usage = {"element": f"{sheet_in}.col2", "usage_kind": kind}
    else:
        lines += ["        dst.Cells(r, 1).Value = src.Cells(r, 1).Value / src.Cells(r, 2).Value"]
        usage = {"element": f"{sheet_in}.col2", "usage_kind": "denominator"}
    lines += ["    Next r", "End Sub", ""]
    return "\n".join(lines), usage


EMITTERS = {"SAS": _emit_sas, "Python": _emit_python, "R": _emit_r, "VBA": _emit_vba}


def _csv(table: str) -> str:
    return table.replace(".", "_") + ".csv"


def _sheet(table: str) -> str:
    return table.replace(".", "_")


# --------------------------------------------------------------------------- #
# Generation
# --------------------------------------------------------------------------- #
def generate(cfg: GenConfig, out_dir: Path, with_fake_responses: bool) -> dict:
    rng = random.Random(cfg.seed)
    out_dir = out_dir.resolve()
    models_dir = out_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    source_pool = [f"src.table_{i:03d}" for i in range(cfg.tables)]
    cols = [SEMANTIC_COLS[i % len(SEMANTIC_COLS)] for i in range(max(cfg.columns, 1))]

    produced: list[str] = []
    models: list[dict] = []
    edges: list[dict] = []

    needs_two = {"join_key", "cross_system_join"}

    for i in range(cfg.models):
        lang = cfg.language_mix[i % len(cfg.language_mix)]
        kind = cfg.dq_mix[i % len(cfg.dq_mix)]
        label = f"model_{i:03d}"
        out_table = f"stg.{label}_out" if i < cfg.models - 1 else f"mart.{label}_out"

        # One input may be a previously produced output (a cross-model stitch edge).
        inputs: list[str] = []
        if produced and i <= cfg.cross_model_edges:
            inputs.append(rng.choice(produced))
        while len(inputs) < (2 if kind in needs_two else 1):
            cand = rng.choice(source_pool)
            if cand not in inputs:
                inputs.append(cand)

        chunk = cfg.chunk_pressure
        source, usage = EMITTERS[lang](out_table, inputs, kind, cols, chunk)
        fname = f"{label}__{lang.lower()}{EXT[lang]}"
        (models_dir / fname).write_text(source, encoding="utf-8")

        for inp in inputs:
            edges.append({"source": inp, "target": out_table, "model": label})
        models.append(
            {
                "id": label,
                "label": label,
                "language": lang,
                "source_file": f"models/{fname}",
                "inputs": inputs,
                "outputs": [out_table],
                "usages": [usage],
            }
        )
        produced.append(out_table)

        if with_fake_responses:
            fr_dir = out_dir / "fake_responses"
            fr_dir.mkdir(parents=True, exist_ok=True)
            (fr_dir / f"{label}.json").write_text(
                json.dumps(
                    {
                        "purpose": f"Synthetic {lang} model {label} exercising {kind}.",
                        "input_tables": [{"name": t, "columns": cols} for t in inputs],
                        "output_tables": [{"name": out_table, "columns": cols}],
                        "usages": [usage],
                        "lineage_rows": [
                            {
                                "source_element": f"{inputs[0]}.{cols[0]}",
                                "target_element": f"{out_table}.{cols[0]}",
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

    all_tables = sorted({t for m in models for t in (m["inputs"] + m["outputs"])})
    manifest = {
        "config": asdict(cfg),
        "with_fake_responses": with_fake_responses,
        "models": models,
        "tables": all_tables,
        "table_edges": edges,
        "coverage": {
            "usage_kinds": sorted({m["usages"][0]["usage_kind"] for m in models}),
            "languages": sorted({m["language"] for m in models}),
        },
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def _parse_args(argv: list[str] | None = None) -> tuple[GenConfig, Path, bool]:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--models", type=int, default=10)
    p.add_argument("--tables", type=int, default=8)
    p.add_argument("--columns", type=int, default=6)
    p.add_argument("--cross-model-edges", type=int, default=3)
    p.add_argument("--chunk-pressure", type=int, default=0)
    p.add_argument("--dq-mix", default=",".join(ALL_DQ))
    p.add_argument("--language-mix", default="SAS,Python")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--with-fake-responses", action="store_true")
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args(argv)
    cfg = GenConfig(
        models=a.models,
        tables=a.tables,
        columns=a.columns,
        cross_model_edges=a.cross_model_edges,
        chunk_pressure=a.chunk_pressure,
        dq_mix=[k.strip() for k in a.dq_mix.split(",") if k.strip()],
        language_mix=[normalize_lang(s) for s in a.language_mix.split(",") if s.strip()],
        seed=a.seed,
    )
    return cfg, a.out, a.with_fake_responses


def normalize_lang(s: str) -> str:
    return {"sas": "SAS", "python": "Python", "py": "Python", "r": "R", "vba": "VBA"}.get(
        s.strip().lower(), s.strip()
    )


def main(argv: list[str] | None = None) -> None:
    cfg, out, with_fr = _parse_args(argv)
    manifest = generate(cfg, out, with_fr)
    print(f"generated {len(manifest['models'])} models -> {out}")
    print(
        f"  tables={len(manifest['tables'])} edges={len(manifest['table_edges'])} "
        f"usage_kinds={manifest['coverage']['usage_kinds']}"
    )


if __name__ == "__main__":
    main()
