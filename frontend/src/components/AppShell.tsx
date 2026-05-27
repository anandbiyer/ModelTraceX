/**
 * App-shell header + underline tab bar (SDD §13.4.0, decisions D2/D11). The
 * "Modelis" suite wordmark + app switcher (MVA · ModelTraceX) express two sibling
 * apps under one suite; the run context + provider/security badge bind to RunMeta.
 */
import type { ReactNode } from "react";

import { type Tab, useUI } from "../store/ui";
import { useRunState } from "../lib/queries";

const TABS: Tab[] = ["Upload", "Review", "Lineage", "Data Quality", "Chat"];

export function AppShell({ children }: { children: ReactNode }) {
  const { tab, setTab, runId } = useUI();
  const { data: state } = useRunState(runId);
  const meta = state?.run;
  const languages = state ? [...new Set(state.models.map((m) => m.language))].join(", ") : "";

  return (
    <div className="flex h-screen flex-col bg-bg text-text">
      <header className="flex items-center gap-3 border-b border-border bg-sidebar px-4 py-2.5">
        <span className="font-extrabold tracking-tight">Modelis</span>
        <nav className="flex items-center gap-1 rounded border border-border bg-elev px-1 py-0.5 text-xs">
          <span className="px-1.5 text-muted">MVA</span>
          <span className="rounded bg-accent-soft px-1.5 py-0.5 text-accent">ModelTraceX</span>
        </nav>
        <span className="rounded border border-border px-1.5 py-0.5 text-xs text-dim">v2</span>
        {runId && (
          <span className="text-xs text-muted" data-testid="run-context">
            Run #{runId.slice(0, 8)}
            {state ? ` · ${state.models.length} models` : ""}
            {languages ? ` · ${languages}` : ""}
          </span>
        )}
        <span className="ml-auto rounded border border-border bg-elev px-2 py-1 text-xs text-dim">
          {meta ? `${meta.llm_provider} · ${meta.security_mode} mode` : "Claude · cloud mode"}
        </span>
      </header>

      <nav className="flex gap-4 border-b border-border-soft px-4">
        {TABS.map((t) => (
          <button
            key={t}
            data-testid={`tab-${t.replace(/\s/g, "-")}`}
            onClick={() => setTab(t)}
            className={
              "border-b-2 py-2 text-sm " +
              (t === tab
                ? "border-accent text-text"
                : "border-transparent text-dim hover:text-text")
            }
          >
            {t}
          </button>
        ))}
      </nav>

      <main className="min-h-0 flex-1 overflow-auto p-4">{children}</main>
    </div>
  );
}
