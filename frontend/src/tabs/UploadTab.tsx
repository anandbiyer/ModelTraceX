/**
 * Upload tab (SDD §13.4.1): dropzone / multi-file / paste, the file→model table
 * with the language badge as the override control (D5) and row-merge (FR-2.4),
 * the analysis-settings panel with a pre-flight token/cost estimate (D4/NFR-6),
 * and Analyze — which starts the orchestrator and streams per-model progress.
 */
import { type ChangeEvent, useRef, useState } from "react";

import { api, subscribeEvents } from "../api/client";
import { Button, Card, FilterChip } from "../components/primitives";
import { useUI } from "../store/ui";
import type { Estimate, IngestView, SSEEvent } from "../types";

const LANGS = ["SAS", "Python", "R", "VBA"];

export function UploadTab() {
  const { runId, setRunId, setTab, lineageLevel, setLineageLevel } = useUI();
  const [view, setView] = useState<IngestView | null>(null);
  const [paste, setPaste] = useState("");
  const [estimate, setEstimate] = useState<Estimate | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [progress, setProgress] = useState<SSEEvent[]>([]);
  const [analyzing, setAnalyzing] = useState(false);
  const [dataHandling, setDataHandling] = useState<"Local" | "Cloud">("Cloud");
  const fileInput = useRef<HTMLInputElement>(null);

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

  async function onAnalyze() {
    if (!runId) return;
    setProgress([]);
    setAnalyzing(true);
    await api.analyze(runId);
    const stop = subscribeEvents(runId, (e) => {
      setProgress((p) => [...p, e]);
      if (e.type === "run_completed") {
        stop();
        setAnalyzing(false);
        setTab("Review");
      } else if (e.type === "run_failed") {
        stop();
        setAnalyzing(false);
      }
    });
  }

  const models = view?.models ?? [];

  return (
    <div className="grid grid-cols-3 gap-4">
      <div className="col-span-2 flex flex-col gap-4">
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

        {progress.length > 0 && (
          <Card>
            <div className="mb-1 text-sm text-dim">Progress</div>
            <ul className="text-xs text-muted" data-testid="progress-log">
              {progress.map((e, i) => (
                <li key={i} className="mono">
                  {e.type === "model"
                    ? `${e.label}: ${e.status} (${e.completed}/${e.total})`
                    : e.type}
                </li>
              ))}
            </ul>
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

        <div className="flex flex-col gap-1 text-xs text-muted">
          Data handling
          <div className="flex gap-1">
            {(["Local", "Cloud"] as const).map((d) => (
              <FilterChip
                key={d}
                label={d}
                active={dataHandling === d}
                onClick={() => setDataHandling(d)}
              />
            ))}
          </div>
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
