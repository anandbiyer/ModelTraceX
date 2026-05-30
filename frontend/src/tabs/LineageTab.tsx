/**
 * Lineage tab (SDD §13.4.3): swim-lanes Sources → Intermediate → Outputs
 * (cyan/purple/green role lanes) rendered from the React-Flow-shaped graph JSON;
 * node cards carry provenance + confidence; the reusable Inspector handles both
 * node *and* edge selection with accept/reject/edit (resolving open question a).
 * Tables expand in place to column level (lazy, open question b); the footer
 * shows "⚠ N edges pending review" from review_status (R9/D1).
 */
import { useState } from "react";

import { api } from "../api/client";
import { Inspector } from "../components/Inspector";
import { LineageCanvas } from "../components/LineageCanvas";
import { ModelFilter } from "../components/ModelFilter";
import { Button, Card, ConfidenceDot, FilterChip, ProvenancePill, RoleTag } from "../components/primitives";
import { useColumnSubgraph, useLineage, useOverride, useRunState } from "../lib/queries";
import { useUI } from "../store/ui";
import type { GraphEdge, GraphNode, TableGraph, TableRole } from "../types";

const TRANSFORMS = ["filter", "join", "aggregate", "derive", "rename", "cast", "passthrough", "union"];
const ROLES = ["Source", "Intermediate", "Output"];
const EXPORTS = ["svg", "pdf", "mermaid", "drawio", "openlineage", "csv"];

export function LineageTab() {
  const {
    runId,
    selection,
    select,
    lowConfidenceOnly,
    toggleLowConfidence,
    modelFilter,
    setModelFilter,
  } = useUI();
  const { data: graph, isLoading } = useLineage(runId);
  const { data: state } = useRunState(runId);
  const override = useOverride(runId ?? "");
  const [search, setSearch] = useState("");

  if (!runId) return <div className="p-8 text-center text-sm text-muted">Analyze a project first.</div>;
  if (isLoading || !graph) return <div className="p-8 text-center text-sm text-muted">Loading…</div>;

  const lc = (c: string) => c === "Low";
  // Phase 4D model filter: keep a table if the selected model produces or
  // consumes it; keep an edge if it was authored by that model.
  const inModel = (n: GraphNode) =>
    !modelFilter ||
    n.data.produced_by.includes(modelFilter) ||
    n.data.consumed_by.includes(modelFilter);
  const nodes = graph.nodes.filter(
    (n) =>
      inModel(n) &&
      (!lowConfidenceOnly || lc(n.data.confidence)) &&
      (!search || n.data.name.toLowerCase().includes(search.toLowerCase())),
  );
  const visibleIds = new Set(nodes.map((n) => n.id));
  const edges = graph.edges.filter(
    (e) =>
      visibleIds.has(e.source) &&
      visibleIds.has(e.target) &&
      (!modelFilter || e.data.model_id === modelFilter),
  );

  function doOverride(target: string, field: string, value: string) {
    override.mutate({ target, field, new: value });
  }

  const nodesByLane = (role: TableRole) => nodes.filter((n) => n.data.role === role);
  const laneCounts: Record<TableRole, number> = {
    Source: nodesByLane("Source").length,
    Intermediate: nodesByLane("Intermediate").length,
    Output: nodesByLane("Output").length,
  };

  return (
    <div className="flex gap-4">
      <div className="flex min-w-0 flex-1 flex-col gap-3">
        <div
          className="flex flex-wrap items-center gap-3 rounded border border-border bg-elev px-3 py-2 text-xs"
          data-testid="lineage-summary"
        >
          <span className="font-semibold uppercase tracking-wide text-muted">Project lineage</span>
          <span className="text-accent">
            <span className="font-bold">{laneCounts.Source}</span> sources
          </span>
          <span className="text-purple">
            <span className="font-bold">{laneCounts.Intermediate}</span> intermediate
          </span>
          <span className="text-green">
            <span className="font-bold">{laneCounts.Output}</span> outputs
          </span>
          <span className="text-dim">· {edges.length} edges</span>
          <span
            className={`ml-auto ${graph.counts.pending_review ? "text-amber" : "text-dim"}`}
            data-testid="lineage-pending-chip"
          >
            ⚠ {graph.counts.pending_review} pending review
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {state && (
            <ModelFilter
              models={state.models}
              value={modelFilter}
              onChange={setModelFilter}
            />
          )}
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="find table/column"
            data-testid="lineage-search"
            className="rounded border border-border bg-elev px-2 py-1 text-xs text-text"
          />
          <FilterChip label="Low-confidence only" active={lowConfidenceOnly} onClick={toggleLowConfidence} />
          <div className="ml-auto flex items-center gap-1">
            <ProvenancePill source="H" />
            <ProvenancePill source="E" />
            <ExportMenu runId={runId} />
          </div>
        </div>

        {state ? (
          <LineageCanvas
            state={state}
            nodes={nodes}
            edges={edges}
            selectedEdgeId={selection?.kind === "edge" ? selection.id : null}
            onSelectNode={(id) => select({ kind: "node", id })}
            onSelectEdge={(id) => select({ kind: "edge", id })}
            renderNodeHeader={(n) => (
              <div className="flex items-center gap-1">
                <span className="mono truncate text-xs text-text">{n.data.name}</span>
                <span className="ml-auto flex items-center">
                  <ProvenancePill source={n.data.provenance} />
                  <ConfidenceDot confidence={n.data.confidence} />
                </span>
              </div>
            )}
          />
        ) : (
          <Card className="text-xs text-muted">Loading RunState…</Card>
        )}

        {/* Edge legend — the two-color scheme drawn on the SVG overlay. */}
        <div
          className="flex items-center gap-4 text-[10px] text-muted"
          data-testid="lineage-legend"
        >
          <span className="flex items-center gap-1">
            <svg width="20" height="6">
              <path d="M0,3 L20,3" stroke="var(--color-dim, #5E6B86)" strokeWidth={1.4} />
            </svg>
            mechanical (derive · passthrough · rename · cast)
          </span>
          <span className="flex items-center gap-1">
            <svg width="20" height="6">
              <path d="M0,3 L20,3" stroke="var(--color-red, #F87171)" strokeWidth={1.4} />
            </svg>
            compositional (join · aggregate · filter · union)
          </span>
          <span className="flex items-center gap-1">
            <svg width="20" height="6">
              <path
                d="M0,3 L20,3"
                stroke="var(--color-dim, #5E6B86)"
                strokeWidth={1}
                strokeDasharray="4 3"
              />
            </svg>
            table-level fallback (no column edge)
          </span>
        </div>
      </div>

      {selection?.kind === "node" && (
        <NodeInspector
          runId={runId}
          node={graph.nodes.find((n) => n.id === selection.id)!}
          busy={override.isPending}
          onOverride={(field, value) => doOverride(selection.id, field, value)}
        />
      )}
      {selection?.kind === "edge" && (
        <EdgeInspector
          edge={graph.edges.find((e) => e.id === selection.id)!}
          graph={graph}
          busy={override.isPending}
          onOverride={(field, value) => doOverride(selection.id, field, value)}
        />
      )}
    </div>
  );
}

function NodeInspector({
  runId,
  node,
  busy,
  onOverride,
}: {
  runId: string;
  node: GraphNode;
  busy: boolean;
  onOverride: (field: string, value: string) => void;
}) {
  const { data: sub } = useColumnSubgraph(runId, node.id);
  return (
    <Inspector
      title={node.data.name}
      subtitle={`${node.data.role} table`}
      provenance={node.data.provenance}
      confidence={node.data.confidence}
      reviewStatus={node.data.review_status}
      editable={[{ field: "role", label: "Role", value: node.data.role, options: ROLES }]}
      onOverride={onOverride}
      busy={busy}
      rows={[
        { label: "Role", value: <RoleTag role={node.data.role} /> },
        { label: "Source system", value: node.data.source_system ?? "—" },
        { label: "Columns", value: sub ? sub.columns.map((c) => c.data.name).join(", ") || "—" : "…" },
      ]}
    />
  );
}

function EdgeInspector({
  edge,
  graph,
  busy,
  onOverride,
}: {
  edge: GraphEdge;
  graph: TableGraph;
  busy: boolean;
  onOverride: (field: string, value: string) => void;
}) {
  const name = (id: string) => graph.nodes.find((n) => n.id === id)?.data.name ?? id;
  return (
    <Inspector
      title={`${name(edge.source)} → ${name(edge.target)}`}
      subtitle="table edge"
      provenance={edge.data.provenance}
      confidence={edge.data.confidence}
      reviewStatus={edge.data.review_status}
      editable={[
        {
          field: "transformation_type",
          label: "Transformation",
          value: edge.data.transformation_type,
          options: TRANSFORMS,
        },
      ]}
      onOverride={onOverride}
      busy={busy}
      rows={[
        { label: "Transformation", value: edge.label },
        { label: "Model", value: edge.data.model_id.slice(0, 10) },
        { label: "Notes", value: edge.data.notes || "—" },
      ]}
    />
  );
}

function ExportMenu({ runId }: { runId: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative">
      <Button variant="secondary" onClick={() => setOpen((v) => !v)} testid="export-menu">
        ↓ Export
      </Button>
      {open && (
        <div className="absolute right-0 z-10 mt-1 flex flex-col rounded border border-border bg-panel p-1 text-xs">
          {EXPORTS.map((k) => (
            <a
              key={k}
              href={api.exportUrl(runId, k)}
              className="rounded px-2 py-1 text-dim hover:bg-elev hover:text-text"
            >
              {k.toUpperCase()}
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
