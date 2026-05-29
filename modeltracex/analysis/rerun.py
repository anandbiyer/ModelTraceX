"""Targeted / incremental re-run (SDD §13.3, FR-9.3, decision D8).

A stage-dependency DAG drives minimal re-execution:

    ingest → per-model analysis(m) → cross-model stitch → DQ → exports

``IncrementalRun`` caches each model's per-model result, so a mutation re-runs only
the minimal downstream set: a *projection-only* mutation (e.g. ``set_table_role``)
re-stitches + re-DQ + re-exports at **zero token cost** (no LLM), while
``reanalyze_scope([m3])`` re-runs the LLM for m3 alone and reuses the rest. Which
stages a mutation invalidates is declared in ``INVALIDATION`` and is the unit the
targeted-rerun tests assert.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from modeltracex import ids
from modeltracex.analysis.orchestrator import (
    ModelInput,
    ProgressFn,
    _ModelResult,
    analyze_one,
    assemble_run_state,
    new_run_meta,
    run_models,
)
from modeltracex.config import DetailLevel
from modeltracex.llm.provider import LLMProvider
from modeltracex.security.redactor import Redactor
from modeltracex.state import Language, RuleStatus, RunState, TableRole


class Stage(str, Enum):
    ANALYSIS = "analysis"  # the per-model LLM call (the only token-bearing stage)
    STITCH = "stitch"
    DQ = "dq"
    EXPORT = "export"


# Minimal downstream set each mutation invalidates (the stage DAG, §13.3).
_PROJECTION = frozenset({Stage.STITCH, Stage.DQ, Stage.EXPORT})
_ANALYSIS = frozenset({Stage.ANALYSIS}) | _PROJECTION

INVALIDATION: dict[str, frozenset[Stage]] = {
    "set_table_role": _PROJECTION,
    "accept_rule": frozenset({Stage.DQ, Stage.EXPORT}),
    "reject_rule": frozenset({Stage.DQ, Stage.EXPORT}),
    "reanalyze_scope": _ANALYSIS,
    "set_lineage_detail": _ANALYSIS,
    "set_detail_level": _ANALYSIS,
    "set_language_hint": _ANALYSIS,
    "merge_models": _ANALYSIS,
    "split_model": _ANALYSIS,
}


def triggers_llm(op: str) -> bool:
    """True if the mutation re-runs the analysis (token-bearing) stage."""
    return Stage.ANALYSIS in INVALIDATION.get(op, _ANALYSIS)


@dataclass
class MutationOutcome:
    state: RunState
    reanalyzed: list[str] = field(default_factory=list)  # model_ids re-run through the LLM
    llm_used: bool = False
    note: str = ""


class IncrementalRun:
    """Caches per-model results so a mutation re-runs only the minimal set."""

    def __init__(
        self,
        provider: LLMProvider,
        inputs: list[ModelInput],
        *,
        detail_level: DetailLevel = DetailLevel.TABLE,
        run_id: str | None = None,
        tool_version: str = "2.0.0-dev",
        redactor: Redactor | None = None,
    ) -> None:
        self.provider = provider
        self.tool_version = tool_version
        self.inputs: dict[str, ModelInput] = {
            ids.model_id(mi.label, mi.source_files): mi for mi in inputs
        }
        self.detail: dict[str, DetailLevel] = dict.fromkeys(self.inputs, detail_level)
        self.results: dict[str, _ModelResult] = {}
        self.role_overrides: dict[str, TableRole] = {}
        self.rule_status: dict[str, RuleStatus] = {}
        self.run_id = run_id or new_run_meta(provider).run_id
        self.redactor = redactor

    # -- analysis stage --------------------------------------------------- #
    def full(self, on_progress: ProgressFn | None = None) -> RunState:
        results = run_models(
            self.provider,
            list(self.inputs.values()),
            on_progress=on_progress,
            redactor=self.redactor,
        )
        self.results = {r.model_ref: r for r in results}
        return self._assemble()

    def reanalyze(self, model_ids: list[str]) -> None:
        for mid in model_ids:
            mi = self.inputs[mid]
            self.results[mid] = analyze_one(
                self.provider, mi, detail_level=self.detail[mid], redactor=self.redactor
            )

    # -- assembly (projection) stage; no LLM ------------------------------ #
    def _assemble(self) -> RunState:
        ordered = [self.results[mid] for mid in self.inputs if mid in self.results]
        run = new_run_meta(self.provider, run_id=self.run_id, tool_version=self.tool_version)
        state = assemble_run_state(ordered, run=run, role_overrides=self.role_overrides)
        for rule in state.dq_rules:
            if rule.rule_id in self.rule_status:
                rule.status = self.rule_status[rule.rule_id]
        return state

    # -- mutation dispatch ------------------------------------------------ #
    def apply(self, op: str, args: dict) -> MutationOutcome:
        if op == "set_table_role":
            self.role_overrides[args["table_id"]] = TableRole(args["role"])
            return MutationOutcome(self._assemble(), note="re-stitch only (no LLM)")

        if op in ("accept_rule", "reject_rule"):
            status = RuleStatus.ACCEPTED if op == "accept_rule" else RuleStatus.REJECTED
            for rid in _rule_ids(args):
                self.rule_status[rid] = status
            return MutationOutcome(self._assemble(), note="DQ projection only (no LLM)")

        if op == "reanalyze_scope":
            scope = list(args["model_ids"])
            self.reanalyze(scope)
            return MutationOutcome(self._assemble(), reanalyzed=scope, llm_used=bool(scope))

        if op in ("set_lineage_detail", "set_detail_level"):
            detail = DetailLevel(args["detail"])
            scope = list(args.get("model_ids") or self.inputs)
            for mid in scope:
                self.detail[mid] = detail
            self.reanalyze(scope)
            return MutationOutcome(self._assemble(), reanalyzed=scope, llm_used=bool(scope))

        if op == "set_language_hint":
            mid = args["model_id"]
            self.inputs[mid].language = Language(args["language"])
            self.reanalyze([mid])
            return MutationOutcome(self._assemble(), reanalyzed=[mid], llm_used=True)

        if op == "merge_models":
            merged_id = self._merge(args["model_ids"], args.get("label"))
            self.reanalyze([merged_id])
            return MutationOutcome(self._assemble(), reanalyzed=[merged_id], llm_used=True)

        raise ValueError(f"unsupported mutation op for incremental re-run: {op!r}")

    def _merge(self, model_ids: list[str], label: str | None) -> str:
        chosen = [self.inputs[mid] for mid in model_ids if mid in self.inputs]
        if len(chosen) < 2:
            raise ValueError("merge_models needs >=2 known model ids")
        files = [f for mi in chosen for f in mi.source_files]
        merged = ModelInput(
            label=label or chosen[0].label,
            language=chosen[0].language,
            source_files=files,
            code="\n\n".join(mi.code for mi in chosen),
        )
        merged_id = ids.model_id(merged.label, merged.source_files)
        for mid in model_ids:
            self.inputs.pop(mid, None)
            self.results.pop(mid, None)
            self.detail.pop(mid, None)
        self.inputs[merged_id] = merged
        self.detail[merged_id] = DetailLevel.TABLE
        return merged_id


def _rule_ids(args: dict) -> list[str]:
    if "rule_ids" in args:
        return list(args["rule_ids"])
    return [args["rule_id"]] if "rule_id" in args else []


__all__ = ["Stage", "INVALIDATION", "triggers_llm", "MutationOutcome", "IncrementalRun"]
