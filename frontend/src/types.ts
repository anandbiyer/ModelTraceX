/**
 * TypeScript mirrors of the API JSON contracts (SDD §13.1). These track the
 * Pydantic models in `modeltracex/state.py` + `modeltracex/api/*`; they are the
 * shape the projections (Review/Lineage/DQ) render from — never free text.
 */

export type Provenance = "E" | "H" | "I" | "U";
export type Confidence = "High" | "Medium" | "Low";
export type ReviewStatus = "Proposed" | "Accepted" | "Rejected";
export type TableRole = "Source" | "Intermediate" | "Output";
export type ModelStatus = "Analyzed" | "Partial" | "Failed";
export type RuleStatus = "Proposed" | "Accepted" | "Rejected";
export type DQDimension =
  | "Completeness"
  | "Validity"
  | "Uniqueness"
  | "Consistency"
  | "Accuracy"
  | "Timeliness";
export type Severity = "High" | "Medium" | "Low";

export interface RunCreated {
  run_id: string;
  status: string;
}

/** One row in the Recent runs history panel (Phase 4D P4D-8). */
export interface RunSummary {
  run_id: string;
  timestamp: string;
  tool_version: string;
  provider: string;
  model: string;
  tokens: number;
  est_cost: number;
  security_mode: string;
  status?: string;
  counts: {
    models: number;
    tables: number;
    table_edges: number;
    column_edges: number;
    dq_rules: number;
    issues: number;
  };
}

/** Public-safe runtime config returned by GET /config (Phase 4 P4-6, D6). */
export interface RunConfig {
  security_mode: "cloud" | "local";
  allowed_security_modes: ("cloud" | "local")[];
  retain_source: boolean;
  detail_level: "table" | "column";
  provider: string;
  model: string;
}

export interface CandidateFile {
  filename: string;
  evidence: string;
}
export interface CandidateModel {
  index: number;
  label: string;
  language: string;
  language_overridden: boolean;
  files: CandidateFile[];
}
export interface IngestView {
  run_id: string;
  status: string;
  files: number;
  models: CandidateModel[];
}

export interface Estimate {
  models: number;
  tokens_in: number;
  tokens_out: number;
  tokens: number;
  est_cost: number;
  per_model: { label: string; tokens_in: number; tokens_out: number }[];
}

export interface Provenanced {
  provenance: Provenance;
  confidence: Confidence;
  review_status: ReviewStatus;
}

export interface GraphNode {
  id: string;
  type: string;
  lane: TableRole;
  lane_index: number;
  data: Provenanced & {
    name: string;
    role: TableRole;
    source_system: string | null;
    grain: string | null;
    column_count: number;
    produced_by: string[];
    consumed_by: string[];
  };
}
export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  label: string;
  data: Provenanced & {
    transformation_type: string;
    model_id: string;
    notes: string;
  };
}
export interface TableGraph {
  level: "table";
  nodes: GraphNode[];
  edges: GraphEdge[];
  counts: {
    tables: number;
    table_edges: number;
    column_edges: number;
    pending_review: number;
  };
}

export interface ColumnNode {
  id: string;
  table_id: string;
  data: Provenanced & { name: string; role: string; used_in: string[] };
}
export interface ColumnEdge {
  id: string;
  source: string;
  target: string;
  source_table_id: string | null;
  target_table_id: string | null;
  label: string;
  data: Provenanced & {
    transformation_type: string;
    expression: string | null;
    join_keys: string[];
    model_id: string;
  };
}
export interface ColumnSubgraph {
  level: "column";
  table_id: string;
  table_name: string;
  columns: ColumnNode[];
  column_edges: ColumnEdge[];
}

export interface Calculation {
  target: string;
  expression: string;
}
export interface ModelDoc {
  model_id: string;
  label: string;
  language: string;
  source_files: string[];
  purpose: string;
  executive_summary: string;
  assumptions: string[];
  methodology_steps: string[];
  calculations: Calculation[];
  limitations: string[];
  status: ModelStatus;
  confidence: Confidence;
  telemetry: { tokens_in: number; tokens_out: number; est_cost: number };
}
export interface Column {
  name: string;
  inferred_type: string | null;
  role: string;
  used_in: string[];
  source: Provenance;
  confidence: Confidence;
  review_status: ReviewStatus;
}
export interface Table {
  table_id: string;
  name: string;
  role: TableRole;
  source_system: string | null;
  grain: string | null;
  produced_by: string[];
  consumed_by: string[];
  columns: Column[];
  source: Provenance;
  confidence: Confidence;
  review_status: ReviewStatus;
}
export interface DQRule {
  rule_id: string;
  element: string;
  related_elements: string[];
  dimension: DQDimension;
  rule_statement: string;
  rationale: string;
  code_evidence: string;
  severity: Severity;
  source: Provenance;
  confidence: Confidence;
  status: RuleStatus;
  model_ids: string[];
}
export interface RunMeta {
  run_id: string;
  timestamp: string;
  tool_version: string;
  llm_provider: string;
  llm_model: string;
  tokens: number;
  est_cost: number;
  security_mode: string;
}
/** Column-level lineage edge as serialized in `RunState.column_edges`
 *  (the canonical Pydantic shape, distinct from the `ColumnEdge` API view
 *  above which is the column-subgraph projection). */
export interface ColumnEdgeRaw {
  edge_id: string;
  source_element: string;
  target_element: string;
  model_id: string;
  transformation_type: string;
  expression: string | null;
  join_keys: string[];
  source: Provenance;
  confidence: Confidence;
  review_status: ReviewStatus;
}

export interface RunState {
  run: RunMeta;
  models: ModelDoc[];
  tables: Table[];
  table_edges: unknown[];
  column_edges: ColumnEdgeRaw[];
  dq_rules: DQRule[];
  source_systems: { name: string; tables: string[] }[];
  issues: { model_id: string | null; severity: string; message: string }[];
}

export type SSEEvent =
  | { type: "run_started"; run_id: string; total: number }
  | {
      type: "model";
      model_id: string;
      label: string;
      status: string;
      completed: number;
      total: number;
    }
  | { type: "run_completed"; run_id: string; status: "done"; counts: Record<string, number> }
  | { type: "run_failed"; run_id: string; status: "failed"; error: string };

export interface OverrideResult {
  ok: boolean;
  target: string;
  entity: Record<string, unknown>;
  pending_review: number;
}

/** Chat mutation as returned by `/runs/{id}/chat` (SDD §13.2/§13.3). */
export interface ChatMutation {
  op: string;
  args: Record<string, unknown>;
  requires_confirmation: boolean;
  triggers_llm: boolean;
  invalidates: string[];
}
export interface ChatPlan {
  rationale: string;
  mutations: ChatMutation[];
}
export interface ChatApplyResult {
  ok: boolean;
  reanalyzed: string[];
  llm_used: boolean;
  counts: { tables: number; table_edges: number; dq_rules: number; pending_review: number };
}
