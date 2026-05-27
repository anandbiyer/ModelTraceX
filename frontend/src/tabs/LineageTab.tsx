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
import { Button, Card, ConfidenceDot, FilterChip, ProvenancePill, RoleTag } from "../components/primitives";
import { useColumnSubgraph, useLineage, useOverride } from "../lib/queries";
import { useUI } from "../store/ui";
import type { GraphEdge, GraphNode, TableGraph, TableRole } from "../types";

const LANES: { role: TableRole; title: string }[] = [
  { role: "Source", title: "Sources" },
  { role: "Intermediate", title: "Intermediate" },
  { role: "Output", title: "Outputs" },
];
const TRANSFORMS = ["filter", "join", "aggregate", "derive", "rename", "cast", "passthrough", "union"];
const ROLES = ["Source", "Intermediate", "Output"];
const EXPORTS = ["svg", "pdf", "mermaid", "csv"];

export function LineageTab() {
  const { runId, selection, select, lowConfidenceOnly, toggleLowConfidence, expandedTables, toggleExpanded } =
    useUI();
  const { data: graph, isLoading } = useLineage(runId);
  const override = useOverride(runId ?? "");
  const [search, setSearch] = useState("");

  if (!runId) return <div className="p-8 text-center text-sm text-muted">Analyze a project first.</div>;
  if (isLoading || !graph) return <div className="p-8 text-center text-sm text-muted">Loading…</div>;

  const lc = (c: string) => c === "Low";
  const nodes = graph.nodes.filter(
    (n) =>
      (!lowConfidenceOnly || lc(n.data.confidence)) &&
      (!search || n.data.name.toLowerCase().includes(search.toLowerCase())),
  );
  const visibleIds = new Set(nodes.map((n) => n.id));
  const edges = graph.edges.filter(
    (e) => visibleIds.has(e.source) && visibleIds.has(e.target),
  );

  function doOverride(target: string, field: string, value: string) {
    override.mutate({ target, field, new: value });
  }

  return (
    <div className="flex gap-4">
      <div className="flex min-w-0 flex-1 flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-muted">Scope: whole project</span>
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

        <Card className="min-h-[360px]">
          <div className="grid grid-cols-3 gap-3" data-testid="lineage-canvas">
            {LANES.map((lane) => (
              <div key={lane.role}>
                <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">
                  {lane.title}
                </div>
                <div className="flex flex-col gap-2">
                  {nodes
                    .filter((n) => n.data.role === lane.role)
                    .map((n) => (
                      <NodeCard
                        key={n.id}
                        node={n}
                        runId={runId}
                        selected={selection?.kind === "node" && selection.id === n.id}
                        expanded={expandedTables.has(n.id)}
                        onSelect={() => select({ kind: "node", id: n.id })}
                        onToggle={() => toggleExpanded(n.id)}
                      />
                    ))}
                </div>
              </div>
            ))}
          </div>

          <div className="mt-4 border-t border-border-soft pt-2">
            <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">Edges</div>
            <ul className="flex flex-col gap-1" data-testid="edge-list">
              {edges.map((e) => (
                <EdgeRow
                  key={e.id}
                  edge={e}
                  graph={graph}
                  selected={selection?.kind === "edge" && selection.id === e.id}
                  onSelect={() => select({ kind: "edge", id: e.id })}
                />
              ))}
            </ul>
          </div>

          <div className="mt-3 text-xs text-muted" data-testid="lineage-footer">
            {graph.counts.tables} tables · {graph.counts.column_edges} column edges ·{" "}
            <span className={graph.counts.pending_review ? "text-amber" : ""}>
              ⚠ {graph.counts.pending_review} pending review
            </span>
          </div>
        </Card>
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

function NodeCard({
  node,
  runId,
  selected,
  expanded,
  onSelect,
  onToggle,
}: {
  node: GraphNode;
  runId: string;
  selected: boolean;
  expanded: boolean;
  onSelect: () => void;
  onToggle: () => void;
}) {
  const { data: sub } = useColumnSubgraph(runId, expanded ? node.id : null);
  return (
    <div
      data-testid={`node-${node.id}`}
      onClick={onSelect}
      className={
        "cursor-pointer rounded border bg-elev p-2 " +
        (selected ? "border-accent" : "border-border")
      }
    >
      <div className="flex items-center gap-1">
        <button
          data-testid={`expand-${node.id}`}
          onClick={(e) => {
            e.stopPropagation();
            onToggle();
          }}
          className="text-muted hover:text-text"
        >
          {expanded ? "▾" : "▸"}
        </button>
        <span className="mono truncate text-xs text-text">{node.data.name}</span>
        <span className="ml-auto flex items-center">
          <ProvenancePill source={node.data.provenance} />
          <ConfidenceDot confidence={node.data.confidence} />
        </span>
      </div>
      {expanded && sub && (
        <ul className="mt-1 border-t border-border-soft pt-1 text-[11px]" data-testid={`columns-${node.id}`}>
          {sub.columns.map((c) => (
            <li key={c.id} className="mono text-muted">
              {c.data.name}
            </li>
          ))}
          {!sub.columns.length && <li className="text-muted">no columns</li>}
        </ul>
      )}
    </div>
  );
}

function EdgeRow({
  edge,
  graph,
  selected,
  onSelect,
}: {
  edge: GraphEdge;
  graph: TableGraph;
  selected: boolean;
  onSelect: () => void;
}) {
  const name = (id: string) => graph.nodes.find((n) => n.id === id)?.data.name ?? id;
  return (
    <li>
      <button
        data-testid={`edge-${edge.id}`}
        onClick={onSelect}
        className={
          "flex w-full items-center gap-2 rounded px-2 py-1 text-left text-xs " +
          (selected ? "bg-elev text-text" : "text-dim hover:text-text")
        }
      >
        <span className="mono truncate">
          {name(edge.source)} → {name(edge.target)}
        </span>
        <span className="rounded bg-accent-soft px-1 text-accent">{edge.label}</span>
        <span className="ml-auto flex items-center">
          <ProvenancePill source={edge.data.provenance} />
          {edge.data.review_status !== "Proposed" && (
            <span className="ml-1 text-[10px] text-green">{edge.data.review_status}</span>
          )}
        </span>
      </button>
    </li>
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
