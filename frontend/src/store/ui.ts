/**
 * UI / session state via Zustand (SDD §13.4.7): the active run, the active tab,
 * the current selection (drives the inspector), filter chips, and which tables
 * are expanded to column level. Server data lives in TanStack Query, not here.
 */
import { create } from "zustand";

export type Tab = "Upload" | "Review" | "Lineage" | "Data Quality" | "Chat";

export type Selection =
  | { kind: "node"; id: string }
  | { kind: "edge"; id: string }
  | { kind: "rule"; id: string }
  | null;

interface UIState {
  runId: string | null;
  tab: Tab;
  selectedModel: string | null;
  selection: Selection;
  lineageLevel: "table" | "column";
  expandedTables: Set<string>;
  lowConfidenceOnly: boolean;
  dimensionFilter: string | null;
  highSeverityOnly: boolean;

  setRunId: (id: string | null) => void;
  setTab: (t: Tab) => void;
  selectModel: (id: string | null) => void;
  select: (s: Selection) => void;
  setLineageLevel: (l: "table" | "column") => void;
  toggleExpanded: (tableId: string) => void;
  toggleLowConfidence: () => void;
  setDimensionFilter: (d: string | null) => void;
  toggleHighSeverity: () => void;
}

export const useUI = create<UIState>((set) => ({
  runId: null,
  tab: "Upload",
  selectedModel: null,
  selection: null,
  lineageLevel: "table",
  expandedTables: new Set(),
  lowConfidenceOnly: false,
  dimensionFilter: null,
  highSeverityOnly: false,

  setRunId: (id) => set({ runId: id }),
  setTab: (tab) => set({ tab }),
  selectModel: (selectedModel) => set({ selectedModel }),
  select: (selection) => set({ selection }),
  setLineageLevel: (lineageLevel) => set({ lineageLevel }),
  toggleExpanded: (tableId) =>
    set((s) => {
      const next = new Set(s.expandedTables);
      if (next.has(tableId)) next.delete(tableId);
      else next.add(tableId);
      return { expandedTables: next };
    }),
  toggleLowConfidence: () => set((s) => ({ lowConfidenceOnly: !s.lowConfidenceOnly })),
  setDimensionFilter: (dimensionFilter) => set({ dimensionFilter }),
  toggleHighSeverity: () => set((s) => ({ highSeverityOnly: !s.highSeverityOnly })),
}));
