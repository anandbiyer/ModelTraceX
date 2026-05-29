/**
 * Review tab (SDD §13.4.2): project-summary + model list (confidence/status) on
 * the left; the model document rendered **live from RunState** in Spec Part A
 * section order on the right (never free text, FR-4.2). Empty sections render
 * "Not identified from code"; per-model DOCX download (FR-4.3).
 */
import { useEffect } from "react";

import { api } from "../api/client";
import { Button, Card, ConfidenceDot, ProvenancePill, RoleTag, StatusBadge } from "../components/primitives";
import { useRunState } from "../lib/queries";
import { useUI } from "../store/ui";
import type { ModelDoc, RunState, Table } from "../types";

const NOT_IDENTIFIED = "Not identified from code";

function tablesFor(state: RunState, modelId: string, output: boolean): Table[] {
  return state.tables.filter((t) =>
    (output ? t.produced_by : t.consumed_by).includes(modelId),
  );
}

function Section({
  n,
  title,
  children,
}: {
  n: number;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mb-4">
      <h3 className="mb-1 font-bold text-text">
        {n} · {title}
      </h3>
      <div className="text-sm text-dim">{children}</div>
    </section>
  );
}

function TableList({ tables }: { tables: Table[] }) {
  if (!tables.length) return <span className="text-muted">{NOT_IDENTIFIED}</span>;
  return (
    <table className="w-full text-left text-xs">
      <thead className="text-muted">
        <tr>
          <th>Table</th>
          <th>Role</th>
          <th>System</th>
          <th>Columns</th>
        </tr>
      </thead>
      <tbody>
        {tables.map((t) => (
          <tr key={t.table_id} className="border-t border-border-soft">
            <td className="mono text-text">{t.name}</td>
            <td>
              <RoleTag role={t.role} />
            </td>
            <td className="text-muted">{t.source_system ?? "—"}</td>
            <td className="mono text-muted">
              {t.columns.map((c) => c.name).join(", ") || NOT_IDENTIFIED}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Document({ model, state }: { model: ModelDoc; state: RunState }) {
  return (
    <Card className="flex-1">
      <div className="mb-3 flex items-center justify-between border-b border-border-soft pb-2">
        <div className="flex items-center gap-2">
          <span className="mono font-semibold text-text">{model.label}</span>
          <span className="text-xs text-muted">
            {model.language} · {model.source_files.join(", ")}
          </span>
          <StatusBadge status={model.status} />
        </div>
        <a href={api.exportUrl(state.run.run_id, "docx")} data-testid="download-docx">
          <Button variant="secondary">↓ DOCX</Button>
        </a>
      </div>

      <Section n={1} title="Executive summary">
        {model.executive_summary || model.purpose || NOT_IDENTIFIED}
        <div className="mt-1 text-xs text-muted">
          <ProvenancePill source="E" /> LLM-extracted · <ConfidenceDot confidence={model.confidence} />
          {" "}
          confidence {model.confidence.toLowerCase()}
        </div>
      </Section>

      <Section n={2} title="Assumptions">
        {model.assumptions.length ? (
          <ul className="list-disc pl-4">
            {model.assumptions.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
        ) : (
          NOT_IDENTIFIED
        )}
      </Section>

      <Section n={4} title="Data inputs">
        <TableList tables={tablesFor(state, model.model_id, false)} />
      </Section>

      <Section n={5} title="Methodology">
        {model.methodology_steps.length ? (
          <ol className="list-decimal pl-4">
            {model.methodology_steps.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ol>
        ) : (
          NOT_IDENTIFIED
        )}
      </Section>

      <Section n={7} title="Calculation logic">
        {model.calculations.length ? (
          <table className="w-full text-left text-xs">
            <tbody>
              {model.calculations.map((c, i) => (
                <tr key={i} className="border-t border-border-soft">
                  <td className="mono text-text">{c.target}</td>
                  <td className="mono text-dim">{c.expression}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          NOT_IDENTIFIED
        )}
      </Section>

      <Section n={8} title="Data outputs">
        <TableList tables={tablesFor(state, model.model_id, true)} />
      </Section>

      <Section n={10} title="Data quality considerations">
        <span className="text-muted">See the Data Quality tab for the rule register.</span>
      </Section>

      <Section n={11} title="Limitations">
        {model.limitations.length ? (
          <ul className="list-disc pl-4">
            {model.limitations.map((l, i) => (
              <li key={i}>{l}</li>
            ))}
          </ul>
        ) : (
          NOT_IDENTIFIED
        )}
      </Section>
    </Card>
  );
}

export function ReviewTab() {
  const { runId, selectedModel, selectModel } = useUI();
  const { data: state, isLoading } = useRunState(runId);

  useEffect(() => {
    if (state && !selectedModel && state.models.length) selectModel(state.models[0].model_id);
  }, [state, selectedModel, selectModel]);

  if (!runId) return <Empty text="Upload and analyze a project first." />;
  if (isLoading || !state) return <Empty text="Loading…" />;

  const model = state.models.find((m) => m.model_id === selectedModel) ?? state.models[0];

  return (
    <div className="flex gap-4">
      <Card className="w-56 shrink-0">
        <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Project</div>
        <a href={api.exportUrl(runId, "docx")} className="text-xs text-accent hover:underline">
          Project summary ↓
        </a>
        <div
          className="mt-3 rounded border border-border-soft bg-elev p-2 text-[11px] text-dim"
          data-testid="run-summary-telemetry"
        >
          <div className="font-semibold uppercase tracking-wide text-muted">Run telemetry</div>
          <div className="mono mt-1">
            {state.run.tokens.toLocaleString()} tok · ${state.run.est_cost.toFixed(4)}
          </div>
        </div>
        <div className="mb-1 mt-3 text-xs font-semibold uppercase tracking-wide text-muted">
          Models
        </div>
        <ul className="flex flex-col gap-1" data-testid="model-list">
          {state.models.map((m) => (
            <li key={m.model_id}>
              <button
                onClick={() => selectModel(m.model_id)}
                className={
                  "flex w-full items-center gap-1 rounded px-2 py-1 text-left text-sm " +
                  (m.model_id === model?.model_id ? "bg-elev text-text" : "text-dim hover:text-text")
                }
              >
                <ConfidenceDot confidence={m.confidence} />
                <span className="mono truncate">{m.label}</span>
                <span className="ml-auto">
                  <StatusBadge status={m.status} />
                </span>
              </button>
              <div className="mono pl-5 text-[10px] text-muted" data-testid="model-telemetry">
                {m.telemetry.tokens_in + m.telemetry.tokens_out} tok · ${m.telemetry.est_cost.toFixed(4)}
              </div>
            </li>
          ))}
        </ul>
      </Card>

      {model && <Document model={model} state={state} />}
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return <div className="p-8 text-center text-sm text-muted">{text}</div>;
}
