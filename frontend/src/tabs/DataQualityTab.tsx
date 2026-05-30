/**
 * Data Quality tab (SDD §13.4.4): metrics row + dimension/severity/low-conf filter
 * chips + the Sheet-7 rule register with inline code evidence and inline accept /
 * reject (same override pattern as the Lineage inspector, generalized; NFR-5).
 */
import { ModelFilter } from "../components/ModelFilter";
import { Card, ConfidenceDot, FilterChip, ProvenancePill } from "../components/primitives";
import { useOverride, useRunState } from "../lib/queries";
import { useUI } from "../store/ui";
import type { DQRule } from "../types";

const DIMENSIONS = ["Completeness", "Validity", "Uniqueness", "Consistency", "Accuracy", "Timeliness"];

const DIM_COLOR: Record<string, string> = {
  Completeness: "text-green bg-green-soft",
  Validity: "text-accent bg-accent-soft",
  Uniqueness: "text-purple bg-purple-soft",
  Consistency: "text-amber bg-amber-soft",
  Accuracy: "text-red bg-red-soft",
  Timeliness: "text-dim bg-elev",
};
const SEV_COLOR: Record<string, string> = {
  High: "text-red",
  Medium: "text-amber",
  Low: "text-dim",
};

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded border border-border bg-elev px-3 py-2">
      <div className="text-lg font-bold text-text">{value}</div>
      <div className="text-xs text-muted">{label}</div>
    </div>
  );
}

export function DataQualityTab() {
  const {
    runId,
    dimensionFilter,
    setDimensionFilter,
    highSeverityOnly,
    toggleHighSeverity,
    modelFilter,
    setModelFilter,
    sharedOnly,
    toggleSharedOnly,
  } = useUI();
  const { data: state, isLoading } = useRunState(runId);
  const override = useOverride(runId ?? "");

  if (!runId) return <div className="p-8 text-center text-sm text-muted">Analyze a project first.</div>;
  if (isLoading || !state) return <div className="p-8 text-center text-sm text-muted">Loading…</div>;

  // Phase 4D model filter: rules carry the list of contributing model_ids,
  // populated by infer_rules. If model_ids is empty (older runs predating the
  // backend field), we don't filter that rule out — fail open.
  const rules = state.dq_rules;
  const filtered = rules.filter(
    (r) =>
      (!modelFilter || r.model_ids.length === 0 || r.model_ids.includes(modelFilter)) &&
      (!dimensionFilter || r.dimension === dimensionFilter) &&
      (!highSeverityOnly || r.severity === "High") &&
      (!sharedOnly || r.model_ids.length >= 2),
  );
  const metrics = {
    candidate: filtered.length,
    high: filtered.filter((r) => r.severity === "High").length,
    pending: filtered.filter((r) => r.status === "Proposed").length,
    accepted: filtered.filter((r) => r.status === "Accepted").length,
  };

  function setStatus(rule: DQRule, status: "Accepted" | "Rejected") {
    override.mutate({ target: rule.rule_id, field: "status", new: status });
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex gap-2" data-testid="dq-metrics">
        <Metric label="Candidate rules" value={metrics.candidate} />
        <Metric label="High severity" value={metrics.high} />
        <Metric label="Pending review" value={metrics.pending} />
        <Metric label="Accepted" value={metrics.accepted} />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <ModelFilter models={state.models} value={modelFilter} onChange={setModelFilter} />
      </div>

      <div className="flex flex-wrap gap-1">
        <FilterChip label="All dims" active={!dimensionFilter} onClick={() => setDimensionFilter(null)} />
        {DIMENSIONS.map((d) => (
          <FilterChip
            key={d}
            label={d}
            active={dimensionFilter === d}
            onClick={() => setDimensionFilter(dimensionFilter === d ? null : d)}
          />
        ))}
        <FilterChip label="High severity" active={highSeverityOnly} onClick={toggleHighSeverity} />
        <FilterChip
          label="Shared (≥ 2 models)"
          active={sharedOnly}
          onClick={toggleSharedOnly}
        />
      </div>
      <div className="text-[11px] text-muted" data-testid="dq-rule-counts">
        Showing {filtered.length} of {rules.length} rules
        {highSeverityOnly && <> · High severity only (toggle the chip for all)</>}
      </div>

      <Card>
        <table className="w-full text-left text-xs">
          <thead className="text-muted">
            <tr>
              <th>Element</th>
              <th>Dimension</th>
              <th>Rule (+ evidence)</th>
              <th>Sev</th>
              <th>Src</th>
              <th>Conf</th>
              <th>Review</th>
            </tr>
          </thead>
          <tbody data-testid="rule-register">
            {filtered.map((r) => (
              <tr key={r.rule_id} className="border-t border-border-soft align-top">
                <td className="mono text-text">
                  <div className="flex items-center gap-1.5">
                    <span className="truncate">{r.element}</span>
                    {r.model_ids.length > 1 && (
                      <span
                        className="rounded border border-accent/40 bg-accent-soft px-1 py-0.5 text-[9px] font-semibold uppercase text-accent"
                        title={`Used by ${r.model_ids.length} models: ${r.model_ids.slice(0, 5).join(", ")}${r.model_ids.length > 5 ? ", …" : ""}`}
                        data-testid={`rule-shared-${r.rule_id}`}
                      >
                        × {r.model_ids.length} models
                      </span>
                    )}
                  </div>
                </td>
                <td>
                  <span className={`rounded px-1.5 py-0.5 ${DIM_COLOR[r.dimension] ?? "text-dim"}`}>
                    {r.dimension}
                  </span>
                </td>
                <td className="text-dim">
                  {r.rule_statement}
                  {r.code_evidence && (
                    <div className="mono mt-0.5 text-[10px] text-muted">«{r.code_evidence}»</div>
                  )}
                </td>
                <td className={SEV_COLOR[r.severity]}>{r.severity}</td>
                <td>
                  <ProvenancePill source={r.source} />
                </td>
                <td>
                  <ConfidenceDot confidence={r.confidence} />
                </td>
                <td>
                  {r.status === "Proposed" ? (
                    <span className="flex gap-1">
                      <button
                        data-testid={`accept-rule-${r.rule_id}`}
                        onClick={() => setStatus(r, "Accepted")}
                        className="text-green hover:brightness-125"
                      >
                        ✓
                      </button>
                      <button
                        data-testid={`reject-rule-${r.rule_id}`}
                        onClick={() => setStatus(r, "Rejected")}
                        className="text-red hover:brightness-125"
                      >
                        ✕
                      </button>
                    </span>
                  ) : (
                    <span className={r.status === "Accepted" ? "text-green" : "text-red"}>
                      {r.status}
                    </span>
                  )}
                </td>
              </tr>
            ))}
            {!filtered.length && (
              <tr>
                <td colSpan={7} className="py-4 text-center text-muted">
                  No rules match the current filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
