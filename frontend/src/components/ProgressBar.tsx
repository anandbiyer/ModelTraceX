/**
 * Reusable progress bar (Phase 4D, P4D-5 follow-up).
 *
 * Visual %-fill driven by ``value``/``max`` plus a status line above the bar.
 * Used by UploadTab's analyze flow to replace the prior text-only event log.
 */
export function ProgressBar({
  value,
  max,
  label,
  tone = "accent",
}: {
  value: number;
  max: number;
  label?: string;
  tone?: "accent" | "red" | "green";
}) {
  const pct = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0;
  const fillClass =
    tone === "red" ? "bg-red" : tone === "green" ? "bg-green" : "bg-accent";
  return (
    <div className="flex flex-col gap-1" data-testid="progress-bar">
      {label && (
        <div className="flex items-center justify-between text-xs">
          <span className="text-dim">{label}</span>
          <span className="mono text-muted" data-testid="progress-pct">
            {value} / {max} · {pct}%
          </span>
        </div>
      )}
      <div className="h-2 w-full overflow-hidden rounded bg-elev" role="progressbar" aria-valuenow={pct}>
        <div
          className={`h-full ${fillClass} transition-[width] duration-300 ease-out`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

/** Three-step phase indicator: Ingesting → Analyzing → Persisting. */
export function PhaseSteps({
  current,
}: {
  current: "ingesting" | "analyzing" | "persisting" | "done" | "failed";
}) {
  const steps = ["ingesting", "analyzing", "persisting"] as const;
  const order = current === "done" || current === "failed" ? 3 : steps.indexOf(current as (typeof steps)[number]);
  return (
    <ol className="flex items-center gap-2 text-[11px]" data-testid="phase-steps">
      {steps.map((s, i) => {
        const done = i < order || current === "done";
        const active = i === order && current !== "done" && current !== "failed";
        const failed = current === "failed" && i === order;
        const cls = failed
          ? "border-red text-red"
          : done
            ? "border-green text-green"
            : active
              ? "border-accent text-accent"
              : "border-border text-muted";
        return (
          <li key={s} className="flex items-center gap-1">
            <span
              className={`rounded-full border px-2 py-0.5 uppercase tracking-wide ${cls}`}
              data-testid={`phase-${s}`}
            >
              {done && !failed ? "✓ " : active ? "• " : ""}
              {s}
            </span>
            {i < steps.length - 1 && <span className="text-muted">→</span>}
          </li>
        );
      })}
    </ol>
  );
}
