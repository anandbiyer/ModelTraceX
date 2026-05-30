"""Canonical structured state — ``RunState`` and all entities (SDD §4, Spec Part D).

THE single source of truth: the model document, lineage workbook, diagrams, and
OpenLineage export are all pure projections of ``RunState``. The chat loop and
human overrides are the only writers back into it.

Implemented in Phase 0 (P0-1). Enum *values* are the schema-neutral contract the
synthetic corpus (`tests/fixtures`) and exporters depend on — do not rename them.
The narrower per-model LLM target (``ModelExtraction``) lives in
``modeltracex.llm.schema`` so the provider layer never imports the whole state.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

# --------------------------------------------------------------------------- #
# §4.1 Enumerations
# --------------------------------------------------------------------------- #


class Language(str, Enum):
    SAS = "SAS"
    PYTHON = "Python"
    R = "R"
    VBA = "VBA"


class Provenance(str, Enum):
    """Spec source legend (E/H/I/U)."""

    EXTRACTED = "E"  # LLM-extracted from code
    HEURISTIC = "H"  # parser/heuristic-derived
    INFERRED = "I"  # LLM-inferred, lower confidence
    USER = "U"  # user-provided/overridden


class Confidence(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class TableRole(str, Enum):
    SOURCE = "Source"
    INTERMEDIATE = "Intermediate"
    OUTPUT = "Output"


class ColumnRole(str, Enum):
    KEY = "Key"
    MEASURE = "Measure"
    ATTRIBUTE = "Attribute"
    DERIVED = "Derived"


class TransformationType(str, Enum):
    """R1: superset incl. ``union`` (Spec is the output contract)."""

    FILTER = "filter"
    JOIN = "join"
    AGGREGATE = "aggregate"
    DERIVE = "derive"
    RENAME = "rename"
    CAST = "cast"
    PASSTHROUGH = "passthrough"
    UNION = "union"


class UsageKind(str, Enum):
    """R3: fine-grained signals that drive DQ inference (Part C)."""

    DENOMINATOR = "denominator"
    JOIN_KEY = "join_key"
    DATE_PARSE = "date_parse"
    RANGE_FILTER = "range_filter"
    AGGREGATED = "aggregated"
    TYPE_CAST = "type_cast"
    EQUALITY_SET = "equality_set"
    OUTPUT_MEASURE = "output_measure"
    TIME_WINDOW = "time_window"
    CROSS_SYSTEM_JOIN = "cross_system_join"
    FILTER = "filter"  # coarse fallback
    OUTPUT = "output"  # coarse fallback


class DQDimension(str, Enum):
    COMPLETENESS = "Completeness"
    VALIDITY = "Validity"
    UNIQUENESS = "Uniqueness"
    CONSISTENCY = "Consistency"
    ACCURACY = "Accuracy"
    TIMELINESS = "Timeliness"


class Severity(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class ModelStatus(str, Enum):
    ANALYZED = "Analyzed"
    PARTIAL = "Partial"
    FAILED = "Failed"


class RuleStatus(str, Enum):
    """DQ rules (Spec Sheet 7 / Part C)."""

    PROPOSED = "Proposed"
    ACCEPTED = "Accepted"
    REJECTED = "Rejected"


class ReviewStatus(str, Enum):
    """R9/D1: human review disposition on any extracted fact + edges."""

    PROPOSED = "Proposed"
    ACCEPTED = "Accepted"
    REJECTED = "Rejected"


class SecurityMode(str, Enum):
    CLOUD = "cloud"
    LOCAL = "local"


# --------------------------------------------------------------------------- #
# §4.2 Provenance mixin
# --------------------------------------------------------------------------- #


class Provenanced(BaseModel):
    """Inherited by tables, columns, and edges (R9/D1) so any of them is
    accept/reject-able (NFR-5). DQ rules keep their own ``RuleStatus``."""

    source: Provenance
    confidence: Confidence = Confidence.MEDIUM
    review_status: ReviewStatus = ReviewStatus.PROPOSED


# --------------------------------------------------------------------------- #
# §4.3 Core entities
# --------------------------------------------------------------------------- #


class Column(Provenanced):
    name: str
    inferred_type: str | None = None
    role: ColumnRole = ColumnRole.ATTRIBUTE
    used_in: list[str] = Field(default_factory=list)  # roll-up of UsageObservation (R3)


class Table(Provenanced):
    table_id: str  # deterministic (R7, §9.2)
    name: str
    role: TableRole
    source_system: str | None = None
    grain: str | None = None
    produced_by: list[str] = Field(default_factory=list)  # model_ids
    consumed_by: list[str] = Field(default_factory=list)
    columns: list[Column] = Field(default_factory=list)


class Calculation(Provenanced):
    target: str  # "table.column"
    expression: str  # denormalized projection of the derive column-edge (R4)


class ModelTelemetry(BaseModel):
    """R2: per-model token + cost telemetry."""

    tokens_in: int = 0
    tokens_out: int = 0
    est_cost: float = 0.0


class ModelDoc(BaseModel):
    model_id: str  # deterministic
    label: str
    language: Language
    source_files: list[str] = Field(default_factory=list)
    purpose: str = ""
    executive_summary: str = ""
    assumptions: list[str] = Field(default_factory=list)
    methodology_steps: list[str] = Field(default_factory=list)
    calculations: list[Calculation] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    status: ModelStatus = ModelStatus.ANALYZED
    confidence: Confidence = Confidence.MEDIUM
    telemetry: ModelTelemetry = Field(default_factory=ModelTelemetry)


class TableEdge(Provenanced):
    edge_id: str  # deterministic
    source_table_id: str
    target_table_id: str
    model_id: str
    transformation_type: TransformationType
    notes: str = ""


class ColumnEdge(Provenanced):
    edge_id: str  # deterministic; authoritative home of expressions (R4)
    source_element: str  # "table.column"
    target_element: str
    model_id: str
    transformation_type: TransformationType
    expression: str | None = None
    join_keys: list[str] = Field(default_factory=list)


class UsageObservation(Provenanced):
    """R3: adapter output; feeds the DQ engine (Part C)."""

    element: str  # "table.column"
    usage_kind: UsageKind
    evidence: str  # the code snippet that triggered it
    model_id: str


class DQRule(BaseModel):
    rule_id: str  # deterministic
    element: str
    related_elements: list[str] = Field(default_factory=list)  # R6
    dimension: DQDimension
    rule_statement: str
    rationale: str = ""
    code_evidence: str = ""
    severity: Severity = Severity.MEDIUM
    source: Provenance = Provenance.HEURISTIC  # E/H/I only (R5)
    confidence: Confidence = Confidence.HIGH
    status: RuleStatus = RuleStatus.PROPOSED
    # Models whose UsageObservations contributed to this rule (Phase 4D P4D-5
    # follow-up: per-model DQ filter on the UI). Populated by ``infer_rules``.
    model_ids: list[str] = Field(default_factory=list)


class SourceSystem(BaseModel):
    """R8: derived projection grouping tables by their physical system."""

    name: str
    tables: list[str] = Field(default_factory=list)  # table_ids


class Issue(BaseModel):
    model_id: str | None = None
    severity: str
    message: str


class Override(BaseModel):
    target: str  # entity id
    field: str
    old: object | None = None
    new: object | None = None
    by: str = "user"
    timestamp: str


class RunMeta(BaseModel):
    run_id: str  # time-random (the only non-deterministic id)
    timestamp: str
    tool_version: str
    llm_provider: str
    llm_model: str
    tokens: int = 0
    est_cost: float = 0.0
    security_mode: SecurityMode = SecurityMode.CLOUD


class RunState(BaseModel):
    """THE single source of truth (Spec Part D). Every artifact is a projection."""

    run: RunMeta
    models: list[ModelDoc] = Field(default_factory=list)
    tables: list[Table] = Field(default_factory=list)
    table_edges: list[TableEdge] = Field(default_factory=list)
    column_edges: list[ColumnEdge] = Field(default_factory=list)
    usage_observations: list[UsageObservation] = Field(default_factory=list)  # R3
    dq_rules: list[DQRule] = Field(default_factory=list)
    source_systems: list[SourceSystem] = Field(default_factory=list)
    issues: list[Issue] = Field(default_factory=list)
    overrides: list[Override] = Field(default_factory=list)


__all__ = [
    # enums
    "Language",
    "Provenance",
    "Confidence",
    "TableRole",
    "ColumnRole",
    "TransformationType",
    "UsageKind",
    "DQDimension",
    "Severity",
    "ModelStatus",
    "RuleStatus",
    "ReviewStatus",
    "SecurityMode",
    # entities
    "Provenanced",
    "Column",
    "Table",
    "Calculation",
    "ModelTelemetry",
    "ModelDoc",
    "TableEdge",
    "ColumnEdge",
    "UsageObservation",
    "DQRule",
    "SourceSystem",
    "Issue",
    "Override",
    "RunMeta",
    "RunState",
]
