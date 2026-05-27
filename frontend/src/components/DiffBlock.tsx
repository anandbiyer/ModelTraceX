/**
 * Diff block (SDD §13.4.0) — the visual form of a state mutation: old (−, red) /
 * new (+, green). Used by the Chat tab (Phase 3) and to preview an override edit.
 */
export function DiffBlock({ rows }: { rows: { label: string; old: string; next: string }[] }) {
  return (
    <div className="mono rounded border border-border bg-elev p-2 text-xs" data-testid="diff-block">
      {rows.map((r) => (
        <div key={r.label}>
          <div className="text-red">
            − {r.label}: {r.old}
          </div>
          <div className="text-green">
            + {r.label}: {r.next}
          </div>
        </div>
      ))}
    </div>
  );
}
