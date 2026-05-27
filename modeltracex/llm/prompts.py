"""Prompt composition (SDD §6.2).

    SYSTEM = BASE_REVIEWER + adapter.prompt_fragment() + detail-level fragment
           + schema instruction
    USER   = label + libnames + code chunk

The base prompt is provider-neutral; structured output is requested via the
provider's native mechanism and always re-validated locally (§6.3).
"""

from __future__ import annotations

from modeltracex.config import DetailLevel

BASE_REVIEWER = (
    "You are a meticulous model-risk documentation reviewer. From the supplied code, "
    "extract ONLY facts present in the code: the model's purpose, executive summary, "
    "input and output tables (with columns), the ordered processing/methodology steps, "
    "calculations (target and expression), and the source-element -> target-element "
    "data lineage. Do not invent tables, columns, or logic that are not in the code; "
    "prefer omission over speculation."
)

_DETAIL_FRAGMENT = {
    DetailLevel.TABLE: (
        "Report lineage at TABLE granularity: which input tables feed which output tables."
    ),
    DetailLevel.COLUMN: (
        "Report lineage at COLUMN granularity: for each output column, the source "
        "columns and the expression that derives it."
    ),
}

_SCHEMA_INSTRUCTION = (
    "Return a SINGLE JSON object matching the ModelExtraction schema with keys: "
    "purpose, executive_summary, assumptions, methodology_steps, limitations, "
    "input_tables[{name,columns}], output_tables[{name,columns}], transformations, "
    "calculations[{target,expression}], lineage_rows[{source_element,target_element,"
    "transformation_type}]. No prose outside the JSON."
)


def build_system_prompt(adapter_fragment: str, detail_level: DetailLevel) -> str:
    return "\n\n".join(
        [BASE_REVIEWER, adapter_fragment, _DETAIL_FRAGMENT[detail_level], _SCHEMA_INSTRUCTION]
    )


def build_user_prompt(label: str, language: str, libnames: dict[str, str], code: str) -> str:
    libs = ", ".join(f"{k}={v}" for k, v in libnames.items()) or "(none)"
    return f"Model: {label}\nLanguage: {language}\nLibnames: {libs}\n\nCODE:\n{code}"


__all__ = ["BASE_REVIEWER", "build_system_prompt", "build_user_prompt"]
