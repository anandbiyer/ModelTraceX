/**
 * Server-state hooks via TanStack Query (SDD §13.4.7). Keyed by run_id + entity;
 * the override mutation invalidates the affected projections so Review/Lineage/DQ
 * stay consistent with the canonical RunState after an accept/reject/edit.
 */
import { QueryClient, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../api/client";

export const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
});

export const keys = {
  state: (id: string) => ["state", id] as const,
  lineage: (id: string) => ["lineage", id] as const,
  columns: (id: string, tableId: string) => ["columns", id, tableId] as const,
};

export function useRunState(runId: string | null, enabled = true) {
  return useQuery({
    queryKey: keys.state(runId ?? ""),
    queryFn: () => api.state(runId!),
    enabled: !!runId && enabled,
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
