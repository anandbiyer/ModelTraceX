/**
 * REST + SSE client for the ModelTraceX API (SDD §13.1). Paths are relative so
 * the Vite dev proxy (and a same-origin deploy) forward `/runs/*` to FastAPI.
 */
import type {
  ChatApplyResult,
  ChatMutation,
  ChatPlan,
  ColumnSubgraph,
  Estimate,
  IngestView,
  OverrideResult,
  RunCreated,
  RunConfig,
  RunState,
  SSEEvent,
  TableGraph,
} from "../types";

async function json<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    const detail = await resp.text();
    throw new Error(`${resp.status} ${resp.statusText}: ${detail}`);
  }
  return resp.json() as Promise<T>;
}

export const api = {
  /** Public-safe runtime config (security_mode bounds, retain_source, etc.). */
  config: () => fetch("/config").then(json<RunConfig>),

  /** Set the per-run security_mode (D6); bounded by allowed_security_modes. */
  setSecurityMode: (id: string, security_mode: "cloud" | "local") =>
    fetch(`/runs/${id}/security`, {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ security_mode }),
    }).then(json<{ run_id: string; security_mode: string }>),

  createRun: () => fetch("/runs", { method: "POST" }).then(json<RunCreated>),

  getRun: (id: string) =>
    fetch(`/runs/${id}`).then(json<{ run_id: string; status: string; models: number }>),

  ingestFiles: (id: string, files: File[]) => {
    const form = new FormData();
    for (const f of files) form.append("files", f, f.name);
    return fetch(`/runs/${id}/ingest`, { method: "POST", body: form }).then(json<IngestView>);
  },

  ingestPaste: (id: string, content: string, filename: string) => {
    const form = new FormData();
    form.append("paste", content);
    form.append("paste_filename", filename);
    return fetch(`/runs/${id}/ingest`, { method: "POST", body: form }).then(json<IngestView>);
  },

  patchModels: (id: string, operations: unknown[]) =>
    fetch(`/runs/${id}/models`, {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ operations }),
    }).then(json<IngestView>),

  estimate: (id: string) =>
    fetch(`/runs/${id}/estimate`, { method: "POST" }).then(json<Estimate>),

  analyze: (id: string) =>
    fetch(`/runs/${id}/analyze`, { method: "POST" }).then(
      json<{ run_id: string; status: string }>,
    ),

  state: (id: string) => fetch(`/runs/${id}/state`).then(json<RunState>),

  lineage: (id: string) => fetch(`/runs/${id}/lineage`).then(json<TableGraph>),

  columnSubgraph: (id: string, tableId: string) =>
    fetch(`/runs/${id}/lineage?level=column&table=${encodeURIComponent(tableId)}`).then(
      json<ColumnSubgraph>,
    ),

  override: (id: string, body: { target: string; field: string; new: unknown; by?: string }) =>
    fetch(`/runs/${id}/overrides`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    }).then(json<OverrideResult>),

  exportUrl: (id: string, kind: string) => `/runs/${id}/exports/${kind}`,

  chat: (id: string, message: string) =>
    fetch(`/runs/${id}/chat`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ message }),
    }).then(json<ChatPlan>),

  chatApply: (id: string, mutations: ChatMutation[]) =>
    fetch(`/runs/${id}/chat/apply`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        mutations: mutations.map((m) => ({ op: m.op, args: m.args })),
      }),
    }).then(json<ChatApplyResult>),
};

/** Subscribe to the run's SSE channel; returns an unsubscribe fn (FR-8.3). */
export function subscribeEvents(id: string, onEvent: (e: SSEEvent) => void): () => void {
  const es = new EventSource(`/runs/${id}/events`);
  const handler = (ev: MessageEvent) => {
    try {
      onEvent(JSON.parse(ev.data) as SSEEvent);
    } catch {
      /* ignore keep-alive comments / malformed frames */
    }
  };
  // The server names each event by its `type`; listen to the known names + default.
  for (const name of ["run_started", "model", "run_completed", "run_failed", "message"]) {
    es.addEventListener(name, handler as EventListener);
  }
  es.onerror = () => es.close();
  return () => es.close();
}
