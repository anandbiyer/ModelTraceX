/**
 * REST + SSE client for the ModelTraceX API (SDD §13.1).
 *
 * In dev the Vite proxy forwards `/runs/*` + `/config` to the FastAPI backend
 * (same origin from the browser's POV). In production the frontend (Vercel) and
 * backend (Render/Fly/…) live on different origins, so we prefix every request
 * with ``VITE_API_BASE_URL`` (configured per Vercel environment). An empty BASE
 * keeps dev working unchanged.
 */
import type {
  ChatApplyResult,
  ChatMutation,
  ChatPlan,
  ColumnSubgraph,
  Estimate,
  IngestView,
  OverrideResult,
  RunConfig,
  RunCreated,
  RunState,
  RunSummary,
  SSEEvent,
  TableGraph,
} from "../types";

const BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

/** Resolve a backend path to a fully-qualified URL when BASE is set, else relative. */
function u(path: string): string {
  return BASE + path;
}

async function json<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    const detail = await resp.text();
    throw new Error(`${resp.status} ${resp.statusText}: ${detail}`);
  }
  return resp.json() as Promise<T>;
}

export const api = {
  /** Public-safe runtime config (security_mode bounds, retain_source, etc.). */
  config: () => fetch(u("/config")).then(json<RunConfig>),

  /** Set the per-run security_mode (D6); bounded by allowed_security_modes. */
  setSecurityMode: (id: string, security_mode: "cloud" | "local") =>
    fetch(u(`/runs/${id}/security`), {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ security_mode }),
    }).then(json<{ run_id: string; security_mode: string }>),

  /** Recent runs (Phase 4D run-history feed). */
  listRuns: (limit = 50) => fetch(u(`/runs?limit=${limit}`)).then(json<RunSummary[]>),

  createRun: () => fetch(u("/runs"), { method: "POST" }).then(json<RunCreated>),

  getRun: (id: string) =>
    fetch(u(`/runs/${id}`)).then(json<{ run_id: string; status: string; models: number }>),

  ingestFiles: (id: string, files: File[]) => {
    const form = new FormData();
    for (const f of files) form.append("files", f, f.name);
    return fetch(u(`/runs/${id}/ingest`), { method: "POST", body: form }).then(json<IngestView>);
  },

  ingestPaste: (id: string, content: string, filename: string) => {
    const form = new FormData();
    form.append("paste", content);
    form.append("paste_filename", filename);
    return fetch(u(`/runs/${id}/ingest`), { method: "POST", body: form }).then(json<IngestView>);
  },

  patchModels: (id: string, operations: unknown[]) =>
    fetch(u(`/runs/${id}/models`), {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ operations }),
    }).then(json<IngestView>),

  estimate: (id: string) =>
    fetch(u(`/runs/${id}/estimate`), { method: "POST" }).then(json<Estimate>),

  analyze: (id: string) =>
    fetch(u(`/runs/${id}/analyze`), { method: "POST" }).then(
      json<{ run_id: string; status: string }>,
    ),

  state: (id: string) => fetch(u(`/runs/${id}/state`)).then(json<RunState>),

  lineage: (id: string) => fetch(u(`/runs/${id}/lineage`)).then(json<TableGraph>),

  columnSubgraph: (id: string, tableId: string) =>
    fetch(u(`/runs/${id}/lineage?level=column&table=${encodeURIComponent(tableId)}`)).then(
      json<ColumnSubgraph>,
    ),

  override: (id: string, body: { target: string; field: string; new: unknown; by?: string }) =>
    fetch(u(`/runs/${id}/overrides`), {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    }).then(json<OverrideResult>),

  /** Exports are href-based (anchor downloads), so resolve to a full URL too. */
  exportUrl: (id: string, kind: string) => u(`/runs/${id}/exports/${kind}`),

  chat: (id: string, message: string) =>
    fetch(u(`/runs/${id}/chat`), {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ message }),
    }).then(json<ChatPlan>),

  chatApply: (id: string, mutations: ChatMutation[]) =>
    fetch(u(`/runs/${id}/chat/apply`), {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        mutations: mutations.map((m) => ({ op: m.op, args: m.args })),
      }),
    }).then(json<ChatApplyResult>),
};

/** Subscribe to the run's SSE channel; returns an unsubscribe fn (FR-8.3). */
export function subscribeEvents(id: string, onEvent: (e: SSEEvent) => void): () => void {
  const es = new EventSource(u(`/runs/${id}/events`));
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
