/**
 * Recent runs history panel (Phase 4D P4D-8).
 *
 * Lives at the top of the Upload tab. Reads from `useRunsList` (the
 * ``GET /runs`` feed) and renders newest-first as compact rows. Clicking a
 * row sets the active ``runId`` in the UI store — the Results card below
 * picks that up and renders that run's RunState. Solves the "Upload tab
 * looks empty after I tab away and come back" bug by giving the user an
 * explicit way back to any prior run.
 */
import { useRunsList } from "../lib/queries";
import { useUI } from "../store/ui";
import type { RunSummary } from "../types";
import { Card } from "./primitives";

function fmtTimeAgo(iso: string): string {
  if (!iso) return "in progress";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return iso;
  const diffSec = Math.max(0, Math.floor((Date.now() - t) / 1000));
  if (diffSec < 60) return `${diffSec}s ago`;
  if (diffSec < 3_600) return `${Math.floor(diffSec / 60)}m ago`;
  if (diffSec < 86_400) return `${Math.floor(diffSec / 3_600)}h ago`;
  return `${Math.floor(diffSec / 86_400)}d ago`;
}

function StatusDot({ status }: { status?: string }) {
  const color =
    status === "failed" ? "bg-red"
    : status === "analyzing" ? "bg-amber animate-pulse"
    : status === "ingested" || status === "created" ? "bg-dim"
    : "bg-green";
  return <span className={`inline-block h-2 w-2 rounded-full ${color}`} title={status ?? "done"} />;
}

function Row({
  summary,
  active,
  onPick,
}: {
  summary: RunSummary;
  active: boolean;
  onPick: () => void;
}) {
  const { counts } = summary;
  return (
    <button
      onClick={onPick}
      data-testid={`recent-run-${summary.run_id}`}
      className={
        "flex w-full flex-col gap-0.5 rounded border px-2.5 py-1.5 text-left text-xs transition-colors " +
        (active
          ? "border-accent bg-accent-soft/30"
          : "border-border bg-elev hover:border-accent/40")
      }
    >
      <div className="flex items-center gap-2">
        <StatusDot status={summary.status} />
        <span className="mono text-text">{summary.run_id.slice(0, 14)}</span>
        <span className="text-muted">· {fmtTimeAgo(summary.timestamp)}</span>
        {summary.provider && (
          <span className="ml-auto rounded border border-border-soft px-1.5 py-0.5 text-[10px] text-dim">
            {summary.provider} · {summary.model}
          </span>
        )}
      </div>
      <div className="flex items-center gap-3 text-[11px] text-muted">
        <span><span className="text-text">{counts.models}</span> models</span>
        <span><span className="text-text">{counts.tables}</span> tables</span>
        <span><span className="text-text">{counts.table_edges}</span> edges</span>
        <span><span className="text-text">{counts.dq_rules}</span> rules</span>
        <span className="ml-auto mono text-dim">
          {summary.tokens.toLocaleString()} tok · ${summary.est_cost.toFixed(4)}
        </span>
      </div>
    </button>
  );
}

export function RecentRunsPanel() {
  const { runId, setRunId } = useUI();
  const { data: runs, isLoading, refetch } = useRunsList();

  // Hide entirely until we know whether there's history — avoids flicker on first load.
  if (isLoading) return null;
  const list = runs ?? [];
  if (list.length === 0) return null;

  return (
    <Card data-testid="recent-runs-panel">
      <div className="mb-1.5 flex items-center justify-between">
        <div className="text-xs font-semibold uppercase tracking-wide text-muted">
          Recent runs ({list.length})
        </div>
        <button
          onClick={() => void refetch()}
          className="text-[11px] text-accent hover:underline"
          data-testid="recent-runs-refresh"
          title="Refresh the history"
        >
          ↻ Refresh
        </button>
      </div>
      <div className="flex max-h-48 flex-col gap-1 overflow-auto pr-1">
        {list.map((s) => (
          <Row
            key={s.run_id}
            summary={s}
            active={s.run_id === runId}
            onPick={() => setRunId(s.run_id)}
          />
        ))}
      </div>
    </Card>
  );
}
