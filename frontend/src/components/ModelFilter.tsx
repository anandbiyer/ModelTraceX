/**
 * Shared per-model filter (Phase 4D, P4D-5).
 *
 * Drives both the Lineage canvas and the DQ rule register: filter nodes/edges
 * by ``produced_by ∪ consumed_by`` containing the selected model_id, and DQ
 * rules by ``DQRule.model_ids`` containing it. ``null`` = show every model
 * (the default). Persisted in the Zustand UI store so navigating away/back
 * preserves the filter.
 */
import type { ModelDoc } from "../types";

export function ModelFilter({
  models,
  value,
  onChange,
}: {
  models: ModelDoc[];
  value: string | null;
  onChange: (id: string | null) => void;
}) {
  return (
    <label className="flex items-center gap-2 text-xs text-muted" data-testid="model-filter">
      <span className="font-semibold uppercase tracking-wide">Model</span>
      <select
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value || null)}
        className="mono max-w-[18rem] truncate rounded border border-border bg-elev px-2 py-1 text-xs text-text"
        data-testid="model-filter-select"
      >
        <option value="">All models ({models.length})</option>
        {models.map((m) => (
          <option key={m.model_id} value={m.model_id}>
            {m.label}
          </option>
        ))}
      </select>
      {value && (
        <button
          className="text-[11px] text-accent hover:underline"
          onClick={() => onChange(null)}
          data-testid="model-filter-clear"
        >
          clear
        </button>
      )}
    </label>
  );
}
