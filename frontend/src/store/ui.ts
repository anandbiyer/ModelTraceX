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
  modelFilter: string | null; // Lineage + DQ per-model filter (Phase 4D)
  selection: Selection;
  lineageLevel: "table" | "column";
  expandedTables: Set<string>;
  lowConfidenceOnly: boolean;
  dimensionFilter: string | null;
  highSeverityOnly: boolean;
  sharedOnly: boolean; // DQ tab: rules touching ≥ 2 models (refined Part C)

  setRunId: (id: string | null) => void;
  setTab: (t: Tab) => void;
  selectModel: (id: string | null) => void;
  setModelFilter: (id: string | null) => void;
  select: (s: Selection) => void;
  setLineageLevel: (l: "table" | "column") => void;
  toggleExpanded: (tableId: string) => void;
  toggleLowConfidence: () => void;
  setDimensionFilter: (d: string | null) => void;
  toggleHighSeverity: () => void;
  toggleSharedOnly: () => void;
}

export const useUI = create<UIState>((set) => ({
  runId: null,
  tab: "Upload",
  selectedModel: null,
  modelFilter: null,
  selection: null,
  lineageLevel: "table",
  expandedTables: new Set(),
  lowConfidenceOnly: false,
  dimensionFilter: null,
  // Default to High severity only — refined Part C generates many baseline
  // (Medium-severity) rules, so the DQ tab opens focused on the important set.
  // Users can toggle the chip off to see everything.
  highSeverityOnly: true,
  sharedOnly: false,

  setRunId: (id) => set({ runId: id }),
  setTab: (tab) => set({ tab }),
  selectModel: (selectedModel) => set({ selectedModel }),
  setModelFilter: (modelFilter) => set({ modelFilter }),
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
  toggleSharedOnly: () => set((s) => ({ sharedOnly: !s.sharedOnly })),
}));
