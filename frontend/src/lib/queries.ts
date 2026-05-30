/**
 * Server-state hooks via TanStack Query (SDD §13.4.7). Keyed by run_id + entity;
 * the override mutation invalidates the affected projections so Review/Lineage/DQ
 * stay consistent with the canonical RunState after an accept/reject/edit.
 */
import { QueryClient, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../api/client";
import type { ChatMutation } from "../types";

export const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
});

export const keys = {
  state: (id: string) => ["state", id] as const,
  lineage: (id: string) => ["lineage", id] as const,
  columns: (id: string, tableId: string) => ["columns", id, tableId] as const,
  runsList: () => ["runs", "list"] as const,
};

export function useRunState(runId: string | null, enabled = true) {
  return useQuery({
    queryKey: keys.state(runId ?? ""),
    queryFn: () => api.state(runId!),
    enabled: !!runId && enabled,
  });
}

/** Recent-runs feed for the Upload-tab history panel (Phase 4D P4D-8). */
export function useRunsList() {
  return useQuery({
    queryKey: keys.runsList(),
    queryFn: () => api.listRuns(50),
    // Slightly stale-while-revalidate: keep the list snappy on tab re-mount,
    // refresh in the background.
    staleTime: 15_000,
  });
}

export function useLineage(runId: string | null, enabled = true) {
  return useQuery({
    queryKey: keys.lineage(runId ?? ""),
    queryFn: () => api.lineage(runId!),
    enabled: !!runId && enabled,
  });
}

export function useColumnSubgraph(runId: string | null, tableId: string | null) {
  return useQuery({
    queryKey: keys.columns(runId ?? "", tableId ?? ""),
    queryFn: () => api.columnSubgraph(runId!, tableId!),
    enabled: !!runId && !!tableId,
  });
}

export function useOverride(runId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { target: string; field: string; new: unknown; by?: string }) =>
      api.override(runId, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keys.state(runId) });
      void qc.invalidateQueries({ queryKey: keys.lineage(runId) });
      void qc.invalidateQueries({ queryKey: ["columns", runId] });
    },
  });
}

export function useChat(runId: string) {
  return useMutation({
    mutationFn: (message: string) => api.chat(runId, message),
  });
}

export function useChatApply(runId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (mutations: ChatMutation[]) => api.chatApply(runId, mutations),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keys.state(runId) });
      void qc.invalidateQueries({ queryKey: keys.lineage(runId) });
      void qc.invalidateQueries({ queryKey: ["columns", runId] });
    },
  });
}
