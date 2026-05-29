"""Phase 3 targeted-rerun tests (P3-T2, EXIT): the stage DAG re-runs the minimal set.

set_table_role triggers no LLM call (re-stitch/DQ/export only); reanalyze_scope([m])
re-runs only that model; set_lineage_detail re-analyzes the affected models.
LLM calls are counted via a wrapping provider.
"""

from __future__ import annotations

import json

from pydantic import BaseModel

from modeltracex import ids
from modeltracex.analysis.orchestrator import ModelInput
from modeltracex.analysis.rerun import INVALIDATION, IncrementalRun, Stage, triggers_llm
from modeltracex.llm.fake import FakeProvider
from modeltracex.llm.provider import LLMResult
from modeltracex.state import Language

_RESP = {
    "alpha": json.dumps(
        {
            "input_tables": [{"name": "raw.events"}],
            "output_tables": [{"name": "work.staging"}],
        }
    ),
    "beta": json.dumps(
        {
            "input_tables": [{"name": "work.staging"}],
            "output_tables": [{"name": "mart.scores"}],
        }
    ),
    "gamma": json.dumps(
        {
            "input_tables": [{"name": "mart.scores"}],
            "output_tables": [{"name": "report.final"}],
        }
    ),
}


class CountingProvider:
    name = "fake"
    model = "fake-1"

    def __init__(self) -> None:
        self.inner = FakeProvider(responses=_RESP)
        self.calls = 0

    def complete_json(self, system: str, user: str, schema: type[BaseModel]) -> LLMResult:
        self.calls += 1
        return self.inner.complete_json(system, user, schema)


def _inputs() -> list[ModelInput]:
    return [
        ModelInput(
            label=lbl, language=Language.SAS, source_files=[f"{lbl}.sas"], code=f"data {lbl};"
        )
        for lbl in ("alpha", "beta", "gamma")
    ]


def _mid(label: str) -> str:
    return ids.model_id(label, [f"{label}.sas"])


def test_stage_dag_declares_what_each_mutation_invalidates() -> None:
    # Projection-only: never touches the (token-bearing) analysis stage.
    assert Stage.ANALYSIS not in INVALIDATION["set_table_role"]
    assert triggers_llm("set_table_role") is False
    assert triggers_llm("accept_rule") is False
    # Analysis-bearing.
    assert Stage.ANALYSIS in INVALIDATION["reanalyze_scope"]
    assert triggers_llm("reanalyze_scope") is True
    assert triggers_llm("set_lineage_detail") is True


def test_set_table_role_triggers_no_llm_call() -> None:
    provider = CountingProvider()
    run = IncrementalRun(provider, _inputs(), run_id="R")
    state = run.full()
    base_calls = provider.calls
    assert base_calls == 3  # one chunk per model

    staging = next(t for t in state.tables if t.name == "work.staging")
    outcome = run.apply("set_table_role", {"table_id": staging.table_id, "role": "Output"})

    assert outcome.llm_used is False
    assert outcome.reanalyzed == []
    assert provider.calls == base_calls  # zero token cost
    changed = next(t for t in outcome.state.tables if t.table_id == staging.table_id)
    assert changed.role.value == "Output"


def test_reanalyze_scope_reruns_only_the_named_model() -> None:
    provider = CountingProvider()
    run = IncrementalRun(provider, _inputs(), run_id="R")
    run.full()
    before = provider.calls

    outcome = run.apply("reanalyze_scope", {"model_ids": [_mid("gamma")]})

    assert outcome.reanalyzed == [_mid("gamma")]
    assert outcome.llm_used is True
    assert provider.calls == before + 1  # only gamma re-analyzed (its single chunk)


def test_set_lineage_detail_reanalyzes_affected_model() -> None:
    provider = CountingProvider()
    run = IncrementalRun(provider, _inputs(), run_id="R")
    run.full()
    before = provider.calls

    outcome = run.apply("set_lineage_detail", {"detail": "column", "model_ids": [_mid("alpha")]})

    assert outcome.reanalyzed == [_mid("alpha")]
    assert provider.calls == before + 1
    assert run.detail[_mid("alpha")].value == "column"
