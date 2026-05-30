/**
 * Upload tab (SDD §13.4.1): dropzone / multi-file / paste, the file→model table
 * with the language badge as the override control (D5) and row-merge (FR-2.4),
 * the analysis-settings panel with a pre-flight token/cost estimate (D4/NFR-6),
 * and Analyze — which starts the orchestrator and streams per-model progress.
 */
import { type ChangeEvent, useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { api, subscribeEvents } from "../api/client";
import { Button, Card, ConfidenceDot, FilterChip, StatusBadge } from "../components/primitives";
import { PhaseSteps, ProgressBar } from "../components/ProgressBar";
import { RecentRunsPanel } from "../components/RecentRunsPanel";
import { keys, useRunState } from "../lib/queries";
import { useUI } from "../store/ui";
import type { Estimate, IngestView, RunConfig, SSEEvent } from "../types";

type Phase = "idle" | "analyzing" | "completed" | "failed";

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded border border-border bg-elev px-3 py-2">
      <div className="text-lg font-bold text-text">{value}</div>
      <div className="text-xs text-muted">{label}</div>
    </div>
  );
}

const LANGS = ["SAS", "Python", "R", "VBA"];

export function UploadTab() {
  const { runId, setRunId, setTab, lineageLevel, setLineageLevel } = useUI();
  const [view, setView] = useState<IngestView | null>(null);
  const [paste, setPaste] = useState("");
  const [estimate, setEstimate] = useState<Estimate | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [progress, setProgress] = useState<SSEEvent[]>([]);
  const [phase, setPhase] = useState<Phase>("idle");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [showLog, setShowLog] = useState(false);
  const analyzing = phase === "analyzing";
  // Phase 4D bug fix: fetch RunState whenever runId is set, not just after a
  // local analyze completes. Otherwise tab-switching unmounts the component,
  // resets `phase` to "idle" on remount, and the Results card disappears
  // even though the server still has the data.
  const { data: runState } = useRunState(runId);
  const queryClient = useQueryClient();
  const [dataHandling, setDataHandling] = useState<"local" | "cloud">("cloud");
  const [config, setConfig] = useState<RunConfig | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    // Load the config-enforced security-mode ceiling once (NFR-2, D6).
    void api.config().then((cfg) => {
      setConfig(cfg);
      setDataHandling(cfg.security_mode);
    });
  }, []);

  async function ensureRun(): Promise<string> {
    if (runId) return runId;
    const { run_id } = await api.createRun();
    setRunId(run_id);
    return run_id;
  }

  async function onFiles(e: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    if (!files.length) return;
    const id = await ensureRun();
    setView(await api.ingestFiles(id, files));
    setEstimate(null);
  }

  async function onPaste() {
    if (!paste.trim()) return;
    const id = await ensureRun();
    setView(await api.ingestPaste(id, paste, "pasted.txt"));
    setPaste("");
    setEstimate(null);
  }

  async function onSetLanguage(index: number, language: string) {
    if (!runId) return;
    setView(await api.patchModels(runId, [{ op: "set_language", index, language }]));
  }

  async function onMerge() {
    if (!runId || selected.size < 2) return;
    setView(await api.patchModels(runId, [{ op: "merge", indices: [...selected] }]));
    setSelected(new Set());
  }

  async function onEstimate() {
    if (!runId) return;
    setEstimate(await api.estimate(runId));
  }

  async function onSetSecurity(mode: "local" | "cloud") {
    setDataHandling(mode);
    if (!runId) return;
    try {
      await api.setSecurityMode(runId, mode);
    } catch {
      // server-side validation reverts the chip if the mode isn't in allowed_security_modes.
    }
  }

  async function onAnalyze() {
    if (!runId) return;
    setProgress([]);
    setErrorMsg(null);
    setPhase("analyzing");
    await api.analyze(runId);
    const stop = subscribeEvents(runId, (e) => {
      setProgress((p) => [...p, e]);
      if (e.type === "run_completed") {
        stop();
        setPhase("completed");
        // Refresh the Recent runs panel so the just-finished run appears at top.
        void queryClient.invalidateQueries({ queryKey: keys.runsList() });
      } else if (e.type === "run_failed") {
        stop();
        setPhase("failed");
        setErrorMsg(e.error);
        void queryClient.invalidateQueries({ queryKey: keys.runsList() });
      }
    });
  }

  const models = view?.models ?? [];

  // Derive a live snapshot from the SSE stream for the progress bar.
  const liveProgress = useMemo(() => {
    let total = models.length || 0;
    let completed = 0;
    let currentLabel: string | null = null;
    let currentStatus: string | null = null;
    for (const e of progress) {
      if (e.type === "run_started") {
        total = e.total;
      } else if (e.type === "model") {
        total = e.total;
        completed = e.completed;
        if (e.status === "started") {
          currentLabel = e.label;
          currentStatus = "started";
        } else {
          currentLabel = e.label;
          currentStatus = e.status;
        }
      }
    }
    return { total, completed, currentLabel, currentStatus };
  }, [progress, models.length]);

  return (
    <div className="grid grid-cols-3 gap-4">
      <div className="col-span-2 flex flex-col gap-4">
        <RecentRunsPanel />
        <Card>
          <div
            className="flex flex-col items-center gap-2 rounded border border-dashed border-border bg-elev py-8 text-center"
            data-testid="dropzone"
          >
            <p className="text-sm text-dim">Drop scripts or a zipped project here</p>
            <p className="mono text-xs text-muted">.sas .py .R .bas/.vba .sql .docx .pdf .zip</p>
            <input
              ref={fileInput}
              type="file"
              multiple
              onChange={onFiles}
              className="hidden"
              data-testid="file-input"
              accept=".sas,.py,.r,.bas,.vba,.sql,.txt,.docx,.pdf,.zip"
            />
            <Button variant="secondary" onClick={() => fileInput.current?.click()}>
              Browse files
            </Button>
          </div>
          <div className="mt-3 flex gap-2">
            <textarea
              value={paste}
              onChange={(e) => setPaste(e.target.value)}
              placeholder="…or paste code"
              data-testid="paste-area"
              className="mono h-16 flex-1 rounded border border-border bg-elev p-2 text-xs text-text"
            />
            <Button variant="secondary" onClick={onPaste}>
              Add paste
            </Button>
          </div>
        </Card>

        {models.length > 0 && (
          <Card>
            <div className="mb-2 flex items-center justify-between">
              <span className="text-sm text-dim" data-testid="file-model-count">
                {view!.files} files → {models.length} models
              </span>
              <Button variant="secondary" onClick={onMerge} disabled={selected.size < 2}>
                Merge selected
              </Button>
            </div>
            <table className="w-full text-left text-sm">
              <thead className="text-xs text-muted">
                <tr>
                  <th className="w-6" />
                  <th>File(s)</th>
                  <th>Lang</th>
                  <th>Detected</th>
                </tr>
              </thead>
              <tbody data-testid="model-rows">
                {models.map((m) => (
                  <tr key={m.index} className="border-t border-border-soft">
                    <td>
                      <input
                        type="checkbox"
                        checked={selected.has(m.index)}
                        onChange={(e) =>
                          setSelected((s) => {
                            const n = new Set(s);
                            e.target.checked ? n.add(m.index) : n.delete(m.index);
                            return n;
                          })
                        }
                      />
                    </td>
                    <td className="mono text-xs text-text">
                      {m.files.map((f) => f.filename).join(", ")}
                    </td>
                    <td>
                      <select
                        value={m.language}
                        data-testid={`lang-${m.index}`}
                        onChange={(e) => onSetLanguage(m.index, e.target.value)}
                        className="rounded border border-border bg-elev px-1 py-0.5 text-xs text-accent"
                      >
                        {LANGS.map((l) => (
                          <option key={l} value={l}>
                            {l}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="text-xs text-muted">{m.files[0]?.evidence}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        )}

        {(phase === "analyzing" || phase === "failed") && (
          <Card data-testid="progress-card">
            <div className="mb-2 flex items-center justify-between">
              <div className="text-sm font-semibold text-text">
                {phase === "failed" ? "Analysis failed" : "Analyzing project"}
              </div>
              <PhaseSteps current={phase === "failed" ? "failed" : "analyzing"} />
            </div>
            <ProgressBar
              value={liveProgress.completed}
              max={Math.max(liveProgress.total, 1)}
              label={
                phase === "failed"
                  ? "halted"
                  : liveProgress.currentLabel
                    ? `Analyzing model ${Math.min(liveProgress.completed + 1, liveProgress.total)} of ${liveProgress.total} — ${liveProgress.currentLabel}`
                    : "Starting…"
              }
              tone={phase === "failed" ? "red" : "accent"}
            />
            {errorMsg && (
              <div className="mt-2 rounded border border-red/40 bg-red-soft px-2 py-1 text-xs text-red" data-testid="run-error">
                {errorMsg}
              </div>
            )}
            <button
              onClick={() => setShowLog((v) => !v)}
              className="mt-2 text-xs text-accent hover:underline"
              data-testid="progress-log-toggle"
            >
              {showLog ? "Hide event log" : "Show event log"}
            </button>
            {showLog && (
              <ul className="mt-1 max-h-48 overflow-auto text-xs text-muted" data-testid="progress-log">
                {progress.map((e, i) => (
                  <li key={i} className="mono">
                    {e.type === "model"
                      ? `${e.label}: ${e.status} (${e.completed}/${e.total})`
                      : e.type}
                  </li>
                ))}
              </ul>
            )}
          </Card>
        )}

        {/* Phase 4D bug fix: show the Results card whenever runState is available
            and we're not actively analyzing — covers the just-completed case
            AND the tab-switch-and-back case. */}
        {!analyzing && runState && (
          <Card data-testid="results-card">
            <div className="mb-2 flex items-center justify-between">
              <div className="text-sm font-semibold text-text">
                {phase === "completed" ? "Run complete" : "Run summary"}
              </div>
              <PhaseSteps current="done" />
            </div>

            <div className="mb-3 grid grid-cols-4 gap-2" data-testid="results-metrics">
              <Metric label="Models" value={runState.models.length} />
              <Metric label="Tables" value={runState.tables.length} />
              <Metric label="Edges" value={runState.table_edges.length} />
              <Metric label="DQ rules" value={runState.dq_rules.length} />
            </div>
            <div className="mb-3 flex items-center gap-2 text-xs text-muted">
              <span className="mono rounded border border-border bg-elev px-2 py-1 text-dim" data-testid="results-cost">
                {runState.run.tokens.toLocaleString()} tok · ${runState.run.est_cost.toFixed(4)}
              </span>
              {runState.issues.length > 0 && (
                <span className="text-amber" data-testid="results-issues">
                  {runState.issues.length} issue(s) recorded
                </span>
              )}
            </div>

            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Per-model status</div>
            <ul className="mb-3 flex flex-col gap-1 text-xs" data-testid="results-models">
              {runState.models.map((m) => (
                <li key={m.model_id} className="flex items-center gap-2 border-t border-border-soft py-1">
                  <ConfidenceDot confidence={m.confidence} />
                  <span className="mono truncate text-text">{m.label}</span>
                  <StatusBadge status={m.status} />
                  <span className="ml-auto mono text-muted">
                    {(m.telemetry.tokens_in + m.telemetry.tokens_out).toLocaleString()} tok ·{" "}
                    ${m.telemetry.est_cost.toFixed(4)}
                  </span>
                </li>
              ))}
            </ul>

            <div className="flex flex-wrap gap-2">
              <Button onClick={() => setTab("Review")} testid="cta-review">View Document →</Button>
              <Button variant="secondary" onClick={() => setTab("Lineage")} testid="cta-lineage">View Lineage →</Button>
              <Button variant="secondary" onClick={() => setTab("Data Quality")} testid="cta-dq">View DQ Rules →</Button>
            </div>
          </Card>
        )}
      </div>

      <Card className="flex flex-col gap-3">
        <div className="text-sm font-semibold text-text">Analysis settings</div>

        <label className="flex flex-col gap-1 text-xs text-muted">
          LLM provider / model
          <div className="mono rounded border border-border bg-elev px-2 py-1 text-dim">
            Claude (config-driven)
          </div>
        </label>

        <div className="flex flex-col gap-1 text-xs text-muted" data-testid="security-mode">
          Data handling
          <div className="flex gap-1">
            {(["local", "cloud"] as const).map((d) => {
              const disabled =
                config != null && !config.allowed_security_modes.includes(d);
              return (
                <FilterChip
                  key={d}
                  label={d === "local" ? "Local · no-retention" : "Cloud"}
                  active={dataHandling === d}
                  onClick={() => !disabled && onSetSecurity(d)}
                  disabled={disabled}
                  testid={`security-${d}`}
                />
              );
            })}
          </div>
          {config != null && !config.allowed_security_modes.includes("cloud") && (
            <span className="text-[10px] text-amber" data-testid="security-locked">
              Cloud disabled by config policy (NFR-2).
            </span>
          )}
        </div>

        <div className="flex flex-col gap-1 text-xs text-muted">
          Lineage detail
          <div className="flex gap-1">
            {(["table", "column"] as const).map((l) => (
              <FilterChip
                key={l}
                label={l === "table" ? "Table" : "Column"}
                active={lineageLevel === l}
                onClick={() => setLineageLevel(l)}
              />
            ))}
          </div>
        </div>

        <hr className="border-border-soft" />

        <Button onClick={onAnalyze} disabled={!models.length || analyzing} testid="analyze">
          {analyzing ? "Analyzing…" : `Analyze ${models.length} models`}
        </Button>
        <button
          onClick={onEstimate}
          disabled={!models.length}
          className="text-left text-xs text-accent hover:underline disabled:opacity-40"
          data-testid="estimate"
        >
          {estimate
            ? `est. ~${(estimate.tokens / 1000).toFixed(0)}k tokens · ~$${estimate.est_cost.toFixed(2)}`
            : "estimate cost (no LLM call)"}
        </button>
      </Card>
    </div>
  );
}
