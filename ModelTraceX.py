import os, json, re, argparse, html
from dataclasses import dataclass, field
from typing import List, Dict, Tuple
from dotenv import load_dotenv
from openai import OpenAI
import gradio as gr
import networkx as nx
import matplotlib.pyplot as plt
from graphviz import Digraph

load_dotenv()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
client = OpenAI()

# Data structures
# -----------------------------
@dataclass
class TableSpec:
    table_name: str
    attributes: List[str] = field(default_factory=list)

@dataclass
class ModelAnalysis:
    model_label: str
    purpose: str
    input_tables: List[TableSpec]
    data_transforms: List[str]
    calc_logic: List[str]
    output_tables: List[TableSpec]
    lineage_rows: List[Dict[str, str]] = field(default_factory=list)

    # -----------------------------
# Normalizers (robust JSON coercion)
# -----------------------------
def _normalize_tables(value) -> List[Dict[str, List[str]]]:
    """
    Accepts:
      - list of dicts: [{"table_name": "...", "attributes": [...]}, ...]
      - list of strings: ["work.raw_data", "scored.out"]
      - single dict, or single string, or comma-separated string
      - None
    Returns a clean list of {"table_name": str, "attributes": List[str]}
    """
    if value is None:
        return []
    if isinstance(value, dict):
        name = value.get("table_name") or value.get("name") or ""
        attrs = value.get("attributes") or []
        if isinstance(attrs, str):
            attrs = [a.strip() for a in attrs.split(",") if a.strip()]
        return [{"table_name": name, "attributes": attrs}]
    if isinstance(value, str):
        names = [n.strip() for n in value.split(",") if n.strip()]
        return [{"table_name": n, "attributes": []} for n in names]
    if isinstance(value, list):
        out = []
        for item in value:
            if isinstance(item, dict):
                name = item.get("table_name") or item.get("name") or ""
                attrs = item.get("attributes") or []
                if isinstance(attrs, str):
                    attrs = [a.strip() for a in attrs.split(",") if a.strip()]
                out.append({"table_name": name, "attributes": list(attrs)})
            elif isinstance(item, str):
                out.append({"table_name": item, "attributes": []})
        return out
    return []

def _to_tablespec_list(value) -> List["TableSpec"]:
    tbls = _normalize_tables(value)
    return [TableSpec(t["table_name"], t.get("attributes", []) or []) for t in tbls]

def _normalize_lineage_rows(value) -> List[Dict[str, str]]:
    """
    Ensure lineage_rows is a list of dicts with expected keys.
    If it’s a string or None, return [].
    If items are strings, skip them (can’t build row).
    """
    if not value:
        return []
    if isinstance(value, dict):
        value = [value]
    if isinstance(value, str):
        return []
    KEYS = ["source_code_name","source_data_element","output_generated","links_to_code_name","output_data_element"]
    out = []
    for item in value:
        if isinstance(item, dict):
            out.append({k: str(item.get(k, "")) for k in KEYS})
    return out

def _norm_lines(value):
    """
    Return a list of clean text lines from value.
    - None -> []
    - str  -> split by newlines into lines
    - list -> flatten, splitting any string elements by newlines
    - other -> [str(value)]
    """
    if value is None:
        return []
    if isinstance(value, str):
        return [ln.strip() for ln in re.split(r"[\r\n]+", value) if ln.strip()]
    if isinstance(value, list):
        out = []
        for v in value:
            if v is None:
                continue
            if isinstance(v, str):
                out += [ln.strip() for ln in re.split(r"[\r\n]+", v) if ln.strip()]
            else:
                out.append(str(v))
        return out
    return [str(value)]


# -----------------------------
# SAS Heuristics (regex scan)
# -----------------------------
SAS_CREATE_TABLE_REGEX = re.compile(r'create\s+table\s+([a-zA-Z0-9_.]+)', re.IGNORECASE)
SAS_DATA_STEP_OUT_REGEX = re.compile(r'\bdata\s+([a-zA-Z0-9_.]+)\s*;', re.IGNORECASE)
SAS_SET_IN_REGEX = re.compile(r'\bset\s+([a-zA-Z0-9_.]+)\s*;', re.IGNORECASE)
SAS_FROM_REGEX = re.compile(r'\bfrom\s+([a-zA-Z0-9_.]+)', re.IGNORECASE)

def heuristic_scan_tables(sas_code: str) -> Tuple[List[TableSpec], List[TableSpec]]:
    """
    Return (inputs, outputs) using quick regex scans (table names only).
    """
    inputs = set()
    outputs = set()

    for m in SAS_SET_IN_REGEX.finditer(sas_code):
        inputs.add(m.group(1))
    for m in SAS_FROM_REGEX.finditer(sas_code):
        inputs.add(m.group(1))
    for m in SAS_DATA_STEP_OUT_REGEX.finditer(sas_code):
        outputs.add(m.group(1))
    for m in SAS_CREATE_TABLE_REGEX.finditer(sas_code):
        outputs.add(m.group(1))

    return [TableSpec(t, []) for t in sorted(inputs)], [TableSpec(t, []) for t in sorted(outputs)]


# -----------------------------
# LLM Prompts
# -----------------------------
SYSTEM_PROMPT_REVIEWER = """You are a SAS modeling expert.
Return JSON with fields: purpose, input_tables, data_transforms, calc_logic, output_tables, lineage_rows.
- input_tables/output_tables: each item like {"table_name": "lib.table", "attributes": ["col1","col2",...]}
- lineage_rows: list of {"source_code_name","source_data_element","output_generated","links_to_code_name","output_data_element"}
Return ONLY valid JSON. No prose."""

SYSTEM_PROMPT_LINEAGE = """You are a data lineage architect.
Given multiple per-model JSON reviews, return JSON with field:
- lineage_rows: list of {"source_code_name","source_data_element","output_generated","links_to_code_name","output_data_element"}
Return ONLY valid JSON. No prose."""


# -----------------------------
# LLM Calls
# -----------------------------
def llm_analyze_single_model(model_label: str, sas_code: str) -> ModelAnalysis:
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        response_format={"type": "json_object"},  # enforce JSON
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_REVIEWER},
            {"role": "user", "content": f"Model: {model_label}\n\nSAS CODE:\n{sas_code}"}
        ]
    )
    raw = resp.choices[0].message.content or "{}"
    parsed = json.loads(raw)

    # Heuristic hints (table names only)
    h_inputs, h_outputs = heuristic_scan_tables(sas_code)

    # Normalize LLM structures
    inputs_llm  = _to_tablespec_list(parsed.get("input_tables"))
    outputs_llm = _to_tablespec_list(parsed.get("output_tables"))
    lineage_llm = _normalize_lineage_rows(parsed.get("lineage_rows"))

    # Merge tables by name, union attributes
    def merge_tables(a: List[TableSpec], b: List[TableSpec]) -> List[TableSpec]:
        by = {}
        for t in a + b:
            by.setdefault(t.table_name, set()).update(t.attributes or [])
        return [TableSpec(name, sorted(list(attrs))) for name, attrs in by.items()]

    return ModelAnalysis(
        model_label=model_label,
        purpose=parsed.get("purpose", "") or "",
        input_tables=merge_tables(inputs_llm, h_inputs),
        data_transforms=_norm_lines(parsed.get("data_transforms")),  # <-- FIXED
        calc_logic=_norm_lines(parsed.get("calc_logic")),            # <-- FIXED
        output_tables=merge_tables(outputs_llm, h_outputs),
        lineage_rows=lineage_llm
    )

def llm_synthesize_lineage(all_models: List[ModelAnalysis]) -> List[Dict[str, str]]:
    # Serialize dataclasses to plain dicts for the LLM
    reviews = []
    for m in all_models:
        reviews.append({
            "model_label": m.model_label,
            "purpose": m.purpose,
            "input_tables": [t.__dict__ for t in m.input_tables],
            "data_transforms": m.data_transforms,
            "calc_logic": m.calc_logic,
            "output_tables": [t.__dict__ for t in m.output_tables],
            "lineage_rows": m.lineage_rows
        })
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        response_format={"type": "json_object"},  # enforce JSON
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_LINEAGE},
            {"role": "user", "content": json.dumps(reviews)}
        ]
    )
    raw = resp.choices[0].message.content or "{}"
    parsed = json.loads(raw)
    return _normalize_lineage_rows(parsed.get("lineage_rows"))




# -----------------------------
# Writers
# -----------------------------
def write_model_review_txt(all_models: List[ModelAnalysis], out_path="output.txt"):
    """
    Plain text version (clean, no Markdown bolds).
    Ensures multi-line strings are split into lines instead of characters.
    """
    lines = []
    lines.append("SAS Model Review\n")
    for m in all_models:
        lines.append(f"Model: {m.model_label}\n")

        # 1) Inputs
        lines.append("1) Input Data Elements")
        if m.input_tables:
            for t in m.input_tables:
                attrs = ", ".join(t.attributes) if t.attributes else "(attributes: unknown)"
                lines.append(f"- {t.table_name}: {attrs}")
        else:
            lines.append("- (none)")

        # 2) Details
        lines.append("\n2) Code Details")
        lines.append(f"a. Purpose of the code: {(m.purpose or '').strip() or '(none)'}")

        # b. Data transformation logic
        lines.append("b. Data transformation logic implemented")
        if m.data_transforms:
            if isinstance(m.data_transforms, str):
                for ln in re.split(r"[\r\n]+", m.data_transforms):
                    if ln.strip():
                        lines.append(f"- {ln.strip()}")
            elif isinstance(m.data_transforms, list):
                for d in m.data_transforms:
                    if isinstance(d, str):
                        for ln in re.split(r"[\r\n]+", d):
                            if ln.strip():
                                lines.append(f"- {ln.strip()}")
                    else:
                        lines.append(f"- {d}")
            else:
                lines.append(f"- {str(m.data_transforms)}")
        else:
            lines.append("- (none)")

        # c. Calculation logic
        lines.append("c. Calculation Logic implemented")
        if m.calc_logic:
            if isinstance(m.calc_logic, str):
                for ln in re.split(r"[\r\n]+", m.calc_logic):
                    if ln.strip():
                        lines.append(f"- {ln.strip()}")
            elif isinstance(m.calc_logic, list):
                for c in m.calc_logic:
                    if isinstance(c, str):
                        for ln in re.split(r"[\r\n]+", c):
                            if ln.strip():
                                lines.append(f"- {ln.strip()}")
                    else:
                        lines.append(f"- {c}")
            else:
                lines.append(f"- {str(m.calc_logic)}")
        else:
            lines.append("- (none)")

        # 3) Outputs
        lines.append("\n3) Output Data Elements")
        if m.output_tables:
            for t in m.output_tables:
                attrs = ", ".join(t.attributes) if t.attributes else "(attributes: unknown)"
                lines.append(f"- {t.table_name}: {attrs}")
        else:
            lines.append("- (none)")

        lines.append("\n---\n")

    open(out_path, "w", encoding="utf-8").write("\n".join(lines))
    return out_path

def write_lineage_csv(lineage_rows: List[Dict[str, str]], out_csv="lineage_table.csv"):
    import csv
    header = ["Source Code name", "Source Data Element", "Output Generated", "Links to Code name", "Output Data Element"]
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for r in lineage_rows:
            writer.writerow([
                r.get("source_code_name",""),
                r.get("source_data_element",""),
                r.get("output_generated",""),
                r.get("links_to_code_name",""),
                r.get("output_data_element","")
            ])
    return out_csv


#def _shorten(s: str, maxlen=36):
#    if not s: return ""
#    s = str(s)
#    return s if len(s) <= maxlen else s[:maxlen-1] + "…"


def _safe_id(name: str) -> str:
    """
    Turn any node name into a Graphviz-safe identifier: [A-Za-z_][A-Za-z0-9_]*
    (avoids spaces, dots, dashes). Keeps a readable skeleton.
    """
    if not name:
        return "n"
    s = re.sub(r'[^A-Za-z0-9_]', '_', str(name))
    if re.match(r'^\d', s):
        s = "n_" + s
    return s or "n"

def _esc(s: str) -> str:
    """Escape text for Graphviz HTML-like labels."""
    return html.escape(str(s), quote=True)

def draw_lineage_clustered(
    all_models: List["ModelAnalysis"],
    out_path: str = "lineage_clustered.png",
    lanes: List[str] = ("Sources", "Models", "Outputs"),
    lane_colors: Dict[str, str] = None,
    lane_override: Dict[str, str] = None,
    fmt: str = "png",   # "png" or "svg"
):
    """
    Render a neat, layered lineage diagram with Graphviz clusters:
      - Big colored swim-lanes arranged left→right
      - Tables/models as compact cards (HTML-like labels, escaped)
      - Edges flow Sources → Models → Outputs
    """
    lane_colors = lane_colors or {
        "Sources": "#cfe2ff",   # light blue
        "Models":  "#f8d7da",   # light red
        "Outputs": "#d1e7dd",   # light green
    }
    lane_override = lane_override or {}

    # lane -> { safe_id: {"name": original_name, "attrs": [...] } }
    lane_nodes: Dict[str, Dict[str, Dict[str, object]]] = {ln: {} for ln in lanes}
    edges: List[Tuple[str, str]] = []

    def which_lane(name: str, kind: str) -> str:
        if name in lane_override:
            return lane_override[name]
        if kind == "input":
            return "Sources" if "Sources" in lanes else lanes[0]
        if kind == "model":
            return "Models"  if "Models"  in lanes else lanes[min(1, len(lanes)-1)]
        if kind == "output":
            return "Outputs" if "Outputs" in lanes else lanes[-1]
        return lanes[-1]

    # Collect nodes/edges from models
    for m in all_models:
        m_id = _safe_id(m.model_label)
        m_lane = which_lane(m.model_label, "model")
        lane_nodes[m_lane].setdefault(m_id, {"name": m.model_label, "attrs": []})

        for t in m.input_tables:
            t_id = _safe_id(t.table_name)
            t_lane = which_lane(t.table_name, "input")
            lane_nodes[t_lane].setdefault(t_id, {"name": t.table_name, "attrs": t.attributes or []})
            edges.append((t_id, m_id))

        for t in m.output_tables:
            t_id = _safe_id(t.table_name)
            t_lane = which_lane(t.table_name, "output")
            lane_nodes[t_lane].setdefault(t_id, {"name": t.table_name, "attrs": t.attributes or []})
            edges.append((m_id, t_id))

    # Graphviz doc
    dot = Digraph("Lineage", format=fmt)
    #dot.attr(rankdir="LR", splines="spline", nodesep="0.35", ranksep="1.0")
    dot.attr(
    rankdir="LR",
    splines="spline",
    nodesep="0.4",
    ranksep="1.5",
    size="16,9!",
    orientation="landscape"
    )
    dot.attr("node", shape="plaintext", fontname="Helvetica")

    # Clusters (lanes)
    for idx, lane in enumerate(lanes):
        color = lane_colors.get(lane, "#eeeeee")
        cluster = f"cluster_{idx}"
        dot.body.append(f'subgraph {cluster} {{')
        dot.body.append('  style="rounded,filled";')
        dot.body.append(f'  color="{color}";')
        dot.body.append(f'  label="{_esc(lane)}";')
        dot.body.append('  labelloc="t";')
        dot.body.append('  fontsize="18";')

        for node_id, meta in lane_nodes[lane].items():
            title = _esc(meta["name"])
            cols = [ _esc(a) for a in (meta.get("attrs") or [])[:12] ]
            more = "" if len(meta.get("attrs") or []) <= 12 else "…"
            rows_html = "".join(f'<TR><TD ALIGN="LEFT">{c}</TD></TR>' for c in cols) or '<TR><TD></TD></TR>'

            # Note: no <HR/> row (some Windows Graphviz builds choke on it)
            label_html = f"""<
<TABLE BORDER="1" CELLBORDER="0" CELLPADDING="4" BGCOLOR="white">
  <TR><TD ALIGN="LEFT"><B>{title}</B></TD></TR>
  {rows_html}
  <TR><TD ALIGN="RIGHT">{_esc(more)}</TD></TR>
</TABLE>>"""

            dot.node(node_id, label=label_html)

        dot.body.append("}")

    # Edges
    for u, v in edges:
        dot.edge(u, v, arrowsize="0.7", color="#666666")

    # Render
    stem, _ = os.path.splitext(out_path)
    final_path = dot.render(filename=stem, cleanup=True)
    if final_path != out_path:
        try:
            os.replace(final_path, out_path)
        except Exception:
            pass
    return out_path



# -----------------------------
# Core Orchestration
# -----------------------------
def analyze_models(model_inputs: List[Tuple[str, str]]):
    """
    model_inputs: list of (label, sas_code)
    Returns paths: output.txt, lineage_table.csv, lineage_clustered.png
    """
    # upstream functions assumed present: llm_analyze_single_model, write_model_review_txt,
    # llm_synthesize_lineage, write_lineage_csv
    models = [llm_analyze_single_model(label, code or "") for label, code in model_inputs]

    out_txt = write_model_review_txt(models)       # plain text only
    lineage = llm_synthesize_lineage(models)
    out_csv = write_lineage_csv(lineage)

    # New clustered Graphviz lineage (replaces any previous spring-layout image)
    out_img = draw_lineage_clustered(
        models,
        out_path="lineage_clustered.png",
        lanes=("Sources", "Models", "Outputs"),
        lane_override={},   # optional: map specific nodes to custom lanes
        fmt="png",
    )

    return out_txt, out_csv, out_img


# -----------------------------
# Gradio UI (Textbox for SAS code)
# -----------------------------
def launch_ui():
    with gr.Blocks(title="SAS Model Reviewer & Data Lineage") as demo:
        gr.Markdown("# SAS Model Reviewer & Data Lineage\nPaste your SAS code for each model below.")

        num_models = gr.Slider(1, 5, value=1, step=1, label="Number of SAS models to review")

        model_labels = []
        model_codes = []
        for i in range(1, 6):
            with gr.Accordion(f"Model {i}", open=(i == 1)):
                lbl = gr.Textbox(label=f"Model {i} Label", value=f"Code_{i}")
                code = gr.Textbox(label=f"Model {i} SAS Code", lines=18, show_copy_button=True)
                model_labels.append(lbl)
                model_codes.append(code)

        run_btn = gr.Button("Analyze", variant="primary")
        #out_md  = gr.File(label="output.md", interactive=False)
        out_txt = gr.File(label="output.txt (download)", interactive=False)
        out_csv = gr.File(label="lineage_table.csv (download)", interactive=False)
        out_img = gr.Image(label="lineage_clustered.png (preview)", type="filepath")

        def run(n, *vals):
            pairs = []
            for i in range(int(n)):
                label = vals[2*i] or f"Code_{i+1}"
                code = vals[2*i + 1] or ""
                pairs.append((label.strip(), code))
            out_txt_p, out_csv_p, out_img_p = analyze_models(pairs)
            return out_txt_p, out_csv_p, out_img_p

        run_btn.click(
            fn=run,
            inputs=[num_models] + sum([[model_labels[i], model_codes[i]] for i in range(5)], []),
            outputs=[out_txt, out_csv, out_img]
        )

    demo.launch()



# -----------------------------
# CLI Helpers (safe sentinel)
# -----------------------------
def read_sas_block(terminator="<<<END>>>"):
    print(f"Paste SAS code. Type {terminator} on its own line to finish.")
    buf = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip().strip(";").upper() == terminator.strip().strip(";").upper():
            break
        buf.append(line)
    return "\n".join(buf)


# -----------------------------
# Entry Point (UI default; --cli for terminal)
# -----------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cli", action="store_true", help="Run in CLI mode instead of UI")
    args, _ = parser.parse_known_args()

    if args.cli:
        n = int(input("How many models? "))
        pairs = []
        for i in range(n):
            label = (input(f"Label for model {i+1}: ") or f"Code_{i+1}").strip()
            print("Paste SAS code, end with <<<END>>> on its own line:")
            sas_code = read_sas_block("<<<END>>>")
            pairs.append((label, sas_code))
        out_md, out_csv, out_img = analyze_models(pairs)
        print("Generated:", out_md, out_csv, out_img)
    else:
        launch_ui()

