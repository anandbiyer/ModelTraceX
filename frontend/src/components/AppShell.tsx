/**
 * App-shell header + underline tab bar (SDD §13.4.0, decisions D2/D11). The
 * "Modelis" suite wordmark + app switcher (MVA · ModelTraceX) express two sibling
 * apps under one suite; the run context + provider/security badge bind to RunMeta.
 */
import { type ReactNode, useState } from "react";

import { api } from "../api/client";
import { type Tab, useUI } from "../store/ui";
import { useRunState } from "../lib/queries";

const TABS: Tab[] = ["Upload", "Review", "Lineage", "Data Quality", "Chat"];

const DOWNLOADS: { kind: string; label: string; hint: string }[] = [
  { kind: "zip", label: "Everything (ZIP)", hint: "DOCX + XLSX + lineage + OL + draw.io" },
  { kind: "docx", label: "Model Document (DOCX)", hint: "Part A, 13 sections per model" },
  { kind: "xlsx", label: "Lineage Workbook (XLSX)", hint: "Part B, 9 sheets" },
  { kind: "svg", label: "Lineage Diagram (SVG)", hint: "Graphviz; .gv fallback if dot is absent" },
  { kind: "drawio", label: "Lineage Diagram (draw.io)", hint: "Open at app.diagrams.net" },
  { kind: "mermaid", label: "Lineage (Mermaid text)", hint: "For embedding in markdown" },
  { kind: "openlineage", label: "OpenLineage events (JSONL)", hint: "Load into Marquez/DataHub" },
];

function DownloadMenu({ runId }: { runId: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="rounded border border-accent bg-accent-soft px-2 py-1 text-xs font-semibold text-accent hover:brightness-110"
        data-testid="download-menu"
      >
        ↓ Download Report
      </button>
      {open && (
        <div
          className="absolute right-0 z-20 mt-1 flex w-72 flex-col rounded border border-border bg-panel p-1 text-xs shadow-elev"
          data-testid="download-menu-list"
        >
          {DOWNLOADS.map((d) => (
            <a
              key={d.kind}
              href={api.exportUrl(runId, d.kind)}
              className="rounded px-2 py-1.5 hover:bg-elev"
              data-testid={`download-${d.kind}`}
              onClick={() => setOpen(false)}
            >
              <div className="text-text">{d.label}</div>
              <div className="text-[10px] text-muted">{d.hint}</div>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}

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
        {meta && (
          <span
            className="ml-auto rounded border border-border bg-elev px-2 py-1 text-xs text-dim"
            data-testid="cost-telemetry"
            title="Total tokens / estimated cost across this run (NFR-6)"
          >
            {meta.tokens.toLocaleString()} tok · ${meta.est_cost.toFixed(4)}
          </span>
        )}
        <span
          className={
            "rounded border border-border bg-elev px-2 py-1 text-xs text-dim " +
            (meta ? "" : "ml-auto")
          }
        >
          {meta ? `${meta.llm_provider} · ${meta.security_mode} mode` : "Claude · cloud mode"}
        </span>
        {runId && state && <DownloadMenu runId={runId} />}
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
