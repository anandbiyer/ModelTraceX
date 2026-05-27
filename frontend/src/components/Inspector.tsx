/**
 * Inspector — the single reusable right-rail shell (SDD §13.4.0/§13.4.3). Renders
 * the selected entity (table node *or* edge *or* DQ rule) with provenance +
 * confidence and an accept / reject / edit cluster (NFR-5). Writes go to
 * `POST /overrides`; an edit flips review_status server-side (R9/D1).
 */
import { type ReactNode, useState } from "react";

import type { Confidence, Provenance, ReviewStatus } from "../types";
import { Button, ConfidenceDot, ProvenancePill } from "./primitives";

export interface EditableField {
  field: string;
  label: string;
  value: string;
  options: string[];
}

export function Inspector({
  title,
  subtitle,
  rows,
  provenance,
  confidence,
  reviewStatus,
  statusField = "review_status",
  editable = [],
  onOverride,
  busy = false,
}: {
  title: ReactNode;
  subtitle?: string;
  rows: { label: string; value: ReactNode }[];
  provenance?: Provenance;
  confidence?: Confidence;
  reviewStatus?: ReviewStatus | string;
  statusField?: string;
  editable?: EditableField[];
  onOverride: (field: string, value: string) => void;
  busy?: boolean;
}) {
  const [editing, setEditing] = useState(false);

  return (
    <aside
      className="flex w-80 shrink-0 flex-col gap-3 rounded-lg border border-border bg-panel p-4"
      data-testid="inspector"
    >
      <div>
        <div className="mono text-sm font-semibold text-text" data-testid="inspector-title">
          {title}
        </div>
        {subtitle && <div className="text-xs text-muted">{subtitle}</div>}
      </div>

      <div className="flex items-center gap-2">
        {provenance && <ProvenancePill source={provenance} />}
        {confidence && <ConfidenceDot confidence={confidence} />}
        {reviewStatus && (
          <span
            className="ml-auto text-[11px] uppercase tracking-wide text-muted"
            data-testid="review-status"
          >
            {reviewStatus}
          </span>
        )}
      </div>

      <dl className="flex flex-col gap-1.5 text-xs">
        {rows.map((r) => (
          <div key={r.label} className="flex justify-between gap-3">
            <dt className="text-muted">{r.label}</dt>
            <dd className="mono text-right text-dim">{r.value}</dd>
          </div>
        ))}
      </dl>

      {editing &&
        editable.map((f) => (
          <label key={f.field} className="flex flex-col gap-1 text-xs text-muted">
            {f.label}
            <select
              defaultValue={f.value}
              data-testid={`edit-${f.field}`}
              onChange={(e) => onOverride(f.field, e.target.value)}
              className="rounded border border-border bg-elev px-2 py-1 text-text"
            >
              {f.options.map((o) => (
                <option key={o} value={o}>
                  {o}
                </option>
              ))}
            </select>
          </label>
        ))}

      <div className="mt-auto flex gap-2 pt-2">
        <Button testid="accept" onClick={() => onOverride(statusField, "Accepted")} disabled={busy}>
          ✓ Accept
        </Button>
        <Button
          testid="reject"
          variant="secondary"
          onClick={() => onOverride(statusField, "Rejected")}
          disabled={busy}
        >
          ✕ Reject
        </Button>
        {editable.length > 0 && (
          <Button testid="edit" variant="secondary" onClick={() => setEditing((v) => !v)}>
            ✎ Edit
          </Button>
        )}
      </div>
    </aside>
  );
}
