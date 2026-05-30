/**
 * Lineage canvas with drawn column-to-column connectors (Phase 4D LineageTab P1).
 *
 * Renders the three role lanes (Source / Intermediate / Output) with table
 * cards whose columns are visible *as rows* by default. An absolutely-
 * positioned SVG layer sits over the lanes and draws one cubic Bezier per
 * ``ColumnEdge`` from the right edge of the source column row to the left
 * edge of the target column row. Connector positions recompute on mount and
 * whenever the lane container's size changes (``ResizeObserver``), so a
 * window resize keeps the lines anchored to the real DOM.
 *
 * The component does NOT own the data — it accepts the table graph (lanes +
 * cards) + column edges as props and surfaces selection callbacks for both
 * card and edge clicks. Selection is owned by the parent (LineageTab + Zustand).
 */
import { type ReactNode, useEffect, useLayoutEffect, useRef, useState } from "react";

import type {
  ColumnControlStatus,
  GraphEdge,
  GraphNode,
  RunState,
  TableRole,
} from "../types";

/** Status-pill styling — matches the data-governance palette of the reference. */
const CONTROL_STATUS_PILL: Record<ColumnControlStatus, string> = {
  Controlled: "border-green/40 bg-green-soft text-green",
  Sourced: "border-accent/40 bg-accent-soft text-accent",
  Dissented: "border-amber/40 bg-amber-soft text-amber",
  "Not Controlled": "border-red/40 bg-red-soft text-red",
  "Not Sourced": "border-red/40 bg-red-soft text-red",
};

const CONTROL_STATUS_EDGE_STROKE: Partial<Record<ColumnControlStatus, string>> = {
  Controlled: "var(--color-green, #4ADE80)",
  Sourced: "var(--color-accent, #22D3EE)",
  Dissented: "var(--color-amber, #FBBF24)",
  "Not Controlled": "var(--color-red, #F87171)",
  "Not Sourced": "var(--color-red, #F87171)",
};

const LANES: { role: TableRole; title: string; headerClass: string; emptyHint: string }[] = [
  {
    role: "Source",
    title: "Sources",
    headerClass: "bg-accent-soft text-accent border-accent/40",
    emptyHint: "No source tables identified.",
  },
  {
    role: "Intermediate",
    title: "Intermediate",
    headerClass: "bg-purple-soft text-purple border-purple/40",
    emptyHint: "No intermediate tables.",
  },
  {
    role: "Output",
    title: "Outputs",
    headerClass: "bg-green-soft text-green border-green/40",
    emptyHint: "No output tables.",
  },
];

/** Heuristic mapping from transformation_type to the two-color edge scheme. */
function edgeColor(transformation_type: string): { stroke: string; cls: string } {
  // Compositional flows (joins, aggregates, filters, unions) read as the
  // "interesting" red; mechanical flows (derive/passthrough/rename/cast)
  // are the muted dim path. Matches the reference image's two-tone palette.
  const compositional = new Set(["aggregate", "join", "filter", "union"]);
  return compositional.has(transformation_type)
    ? { stroke: "var(--color-red, #F87171)", cls: "stroke-red" }
    : { stroke: "var(--color-dim, #5E6B86)", cls: "stroke-dim" };
}

interface LineageCanvasProps {
  state: RunState;
  nodes: GraphNode[];
  edges: GraphEdge[]; // table edges (for fallback connectors)
  selectedEdgeId: string | null;
  onSelectNode: (nodeId: string) => void;
  onSelectEdge: (edgeId: string) => void;
  renderNodeHeader: (node: GraphNode) => ReactNode;
}

interface Endpoint {
  /** Coordinates in the SVG layer's own coordinate space. */
  x: number;
  y: number;
}

function tableOf(element: string): string {
  return element.includes(".") ? element.substring(0, element.lastIndexOf(".")) : element;
}

export function LineageCanvas(props: LineageCanvasProps) {
  const { state, nodes, edges, selectedEdgeId, onSelectNode, onSelectEdge, renderNodeHeader } =
    props;
  const containerRef = useRef<HTMLDivElement | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);
  // Map keyed by `<table.name>.<column.name>` → row DOM node. Refreshed every
  // render so columns added/removed by filters get re-tracked.
  const rowRefs = useRef<Map<string, HTMLElement>>(new Map());
  const cardRefs = useRef<Map<string, HTMLElement>>(new Map());
  const [tick, setTick] = useState(0);

  // Re-measure on resize so window-width changes re-route the lines.
  useEffect(() => {
    const el = containerRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => setTick((t) => t + 1));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Bump tick after every render so the SVG layer measures the freshly
  // committed DOM (column rows may have moved).
  useLayoutEffect(() => {
    setTick((t) => t + 1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodes.length, edges.length, state.column_edges.length]);

  const tableNameByNodeId = new Map(nodes.map((n) => [n.id, n.data.name]));

  function endpointFor(element: string, side: "left" | "right"): Endpoint | null {
    const row = rowRefs.current.get(element);
    const svg = svgRef.current;
    if (!row || !svg) return null;
    const rRect = row.getBoundingClientRect();
    const sRect = svg.getBoundingClientRect();
    return {
      x: (side === "right" ? rRect.right : rRect.left) - sRect.left,
      y: rRect.top + rRect.height / 2 - sRect.top,
    };
  }

  function cardEndpoint(tableId: string, side: "left" | "right"): Endpoint | null {
    const card = cardRefs.current.get(tableId);
    const svg = svgRef.current;
    if (!card || !svg) return null;
    const cRect = card.getBoundingClientRect();
    const sRect = svg.getBoundingClientRect();
    return {
      x: (side === "right" ? cRect.right : cRect.left) - sRect.left,
      y: cRect.top + cRect.height / 2 - sRect.top,
    };
  }

  // Build the list of paths to render. Column-level edges first; table-level
  // edges only when no column edge exists for that table pair.
  const paths: {
    id: string;
    d: string;
    color: ReturnType<typeof edgeColor>;
    title: string;
    fromColumns: boolean;
  }[] = [];
  // `tick` is read so the layout effect re-runs measurement after refs settle.
  void tick;

  // Look up the target column's control_status so the edge can carry its color
  // (Phase 4D-P2: control-state edge coloring overrides the transformation-type
  // heuristic when status is known).
  const controlStatusByElement = new Map<string, ColumnControlStatus | null>();
  for (const table of state.tables) {
    for (const col of table.columns) {
      controlStatusByElement.set(`${table.name}.${col.name}`, col.control_status);
    }
  }

  const tablePairsWithColumnEdge = new Set<string>();
  for (const ce of state.column_edges) {
    const src = endpointFor(ce.source_element, "right");
    const tgt = endpointFor(ce.target_element, "left");
    if (!src || !tgt) continue;
    tablePairsWithColumnEdge.add(`${tableOf(ce.source_element)}|${tableOf(ce.target_element)}`);
    const dx = Math.max(40, (tgt.x - src.x) / 2);
    const cs = controlStatusByElement.get(ce.target_element);
    const csStroke = cs ? CONTROL_STATUS_EDGE_STROKE[cs] : undefined;
    const color = csStroke
      ? { stroke: csStroke, cls: "" }
      : edgeColor(ce.transformation_type);
    paths.push({
      id: ce.edge_id,
      d: `M ${src.x},${src.y} C ${src.x + dx},${src.y} ${tgt.x - dx},${tgt.y} ${tgt.x},${tgt.y}`,
      color,
      title: `${ce.source_element} → ${ce.target_element} (${ce.transformation_type})${cs ? ` · ${cs}` : ""}`,
      fromColumns: true,
    });
  }
  for (const te of edges) {
    const srcName = tableNameByNodeId.get(te.source);
    const tgtName = tableNameByNodeId.get(te.target);
    if (srcName && tgtName) {
      const key = `${srcName}|${tgtName}`;
      if (tablePairsWithColumnEdge.has(key)) continue;
    }
    const src = cardEndpoint(te.source, "right");
    const tgt = cardEndpoint(te.target, "left");
    if (!src || !tgt) continue;
    const dx = Math.max(40, (tgt.x - src.x) / 2);
    paths.push({
      id: te.id,
      d: `M ${src.x},${src.y} C ${src.x + dx},${src.y} ${tgt.x - dx},${tgt.y} ${tgt.x},${tgt.y}`,
      color: { stroke: "var(--color-dim, #5E6B86)", cls: "stroke-dim" },
      title: `${srcName ?? te.source} → ${tgtName ?? te.target} (${te.data.transformation_type})`,
      fromColumns: false,
    });
  }

  function setRow(el: HTMLElement | null, key: string) {
    if (el) rowRefs.current.set(key, el);
    else rowRefs.current.delete(key);
  }
  function setCard(el: HTMLElement | null, tableId: string) {
    if (el) cardRefs.current.set(tableId, el);
    else cardRefs.current.delete(tableId);
  }

  return (
    <div ref={containerRef} className="relative" data-testid="lineage-canvas">
      <div className="grid grid-cols-3 gap-3">
        {LANES.map((lane) => {
          const laneNodes = nodes.filter((n) => n.data.role === lane.role);
          return (
            <div
              key={lane.role}
              className="flex min-h-[280px] flex-col rounded border border-border bg-panel"
              data-testid={`lane-${lane.role}`}
            >
              <div
                className={`flex items-center justify-between rounded-t border-b px-2.5 py-1.5 text-[11px] font-bold uppercase tracking-wide ${lane.headerClass}`}
              >
                <span>{lane.title}</span>
                <span className="rounded bg-bg/40 px-1.5 py-0.5 text-[10px]">
                  {laneNodes.length}
                </span>
              </div>
              <div className="flex flex-1 flex-col gap-2 p-2">
                {laneNodes.length === 0 ? (
                  <div
                    className="flex flex-1 items-center justify-center px-2 text-center text-[11px] italic text-muted"
                    data-testid={`lane-empty-${lane.role}`}
                  >
                    {lane.emptyHint}
                  </div>
                ) : (
                  // Phase 4D-P2: group tables by source_system within the lane.
                  // Tables without a source_system land under the "(unsystemed)"
                  // bucket so they're still visible. Group order is alphabetical
                  // (deterministic across re-renders).
                  Array.from(
                    laneNodes.reduce((acc, n) => {
                      const sys = n.data.source_system ?? "(unsystemed)";
                      if (!acc.has(sys)) acc.set(sys, []);
                      acc.get(sys)!.push(n);
                      return acc;
                    }, new Map<string, GraphNode[]>()),
                  )
                    .sort(([a], [b]) => a.localeCompare(b))
                    .map(([systemName, systemNodes]) => (
                      <div
                        key={systemName}
                        className="flex flex-col gap-1.5"
                        data-testid={`system-group-${lane.role}-${systemName}`}
                      >
                        <div className="px-1 text-[9px] font-semibold uppercase tracking-wider text-muted">
                          {systemName}{" "}
                          <span className="text-dim">({systemNodes.length})</span>
                        </div>
                        {systemNodes.map((n) => {
                          const tableName = n.data.name;
                          const table = state.tables.find((t) => t.table_id === n.id);
                          return (
                            <div
                              key={n.id}
                              ref={(el) => setCard(el, n.id)}
                              onClick={() => onSelectNode(n.id)}
                              className="cursor-pointer rounded border border-border bg-elev"
                              data-testid={`node-${n.id}`}
                            >
                              <div className="border-b border-border-soft px-2 py-1">
                                {renderNodeHeader(n)}
                              </div>
                              {table && table.columns.length > 0 ? (
                                <ul className="flex flex-col py-1" data-testid={`columns-${n.id}`}>
                                  {table.columns.map((c) => {
                                    const key = `${tableName}.${c.name}`;
                                    const cs = c.control_status;
                                    return (
                                      <li
                                        key={c.name}
                                        ref={(el) => setRow(el, key)}
                                        className="mono flex items-center justify-between gap-2 px-2 py-[3px] text-[10.5px] text-text"
                                        data-testid={`col-${key}`}
                                      >
                                        <span className="truncate">{c.name}</span>
                                        <span className="flex items-center gap-1">
                                          {cs && (
                                            <span
                                              className={
                                                "rounded border px-1 py-0 text-[8px] font-semibold uppercase " +
                                                CONTROL_STATUS_PILL[cs]
                                              }
                                              title={`Control status: ${cs}`}
                                              data-testid={`control-status-${key}`}
                                              data-control-status={cs}
                                            >
                                              {cs}
                                            </span>
                                          )}
                                          <span
                                            className={
                                              "inline-block h-1.5 w-1.5 rounded-full " +
                                              (c.confidence === "High"
                                                ? "bg-green"
                                                : c.confidence === "Medium"
                                                  ? "bg-amber"
                                                  : "bg-red")
                                            }
                                            title={`confidence ${c.confidence.toLowerCase()}`}
                                          />
                                        </span>
                                      </li>
                                    );
                                  })}
                                </ul>
                              ) : (
                                <div className="px-2 py-1 text-[10px] italic text-muted">
                                  no columns
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    ))
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* SVG overlay — drawn last so paths sit above the cards. Pointer events
          are restricted to the paths themselves so card clicks still work. */}
      <svg
        ref={svgRef}
        className="pointer-events-none absolute inset-0 h-full w-full"
        data-testid="lineage-edges-svg"
      >
        {paths.map((p) => {
          const isSelected = p.id === selectedEdgeId;
          return (
            <path
              key={p.id}
              d={p.d}
              fill="none"
              stroke={isSelected ? "var(--color-accent, #22D3EE)" : p.color.stroke}
              strokeWidth={isSelected ? 2.4 : p.fromColumns ? 1.4 : 1}
              strokeOpacity={isSelected ? 1 : p.fromColumns ? 0.9 : 0.55}
              strokeDasharray={p.fromColumns ? undefined : "4 3"}
              className="pointer-events-auto cursor-pointer"
              data-testid={`edge-path-${p.id}`}
              onClick={(e) => {
                e.stopPropagation();
                onSelectEdge(p.id);
              }}
            >
              <title>{p.title}</title>
            </path>
          );
        })}
      </svg>
    </div>
  );
}
