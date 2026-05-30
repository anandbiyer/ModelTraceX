/**
 * LineageCanvas vitest — locks the Phase 1 redesign:
 *
 *  1. Every column from every table renders as a row (no expand toggle).
 *  2. The SVG overlay draws one `<path>` per ColumnEdge.
 *  3. Clicking a path fires `onSelectEdge`; clicking a card fires
 *     `onSelectNode`.
 *
 * jsdom returns zeroed `getBoundingClientRect`s, so we don't assert
 * coordinate accuracy — only structural identity (count + ids).
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";

import { LineageCanvas } from "./LineageCanvas";
import type { GraphNode, RunState } from "../types";

// jsdom doesn't ship ResizeObserver. Provide a noop so the effect doesn't blow up.
class NoopResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
(globalThis as unknown as { ResizeObserver: typeof NoopResizeObserver }).ResizeObserver =
  NoopResizeObserver;

function makeNode(
  id: string,
  name: string,
  role: "Source" | "Intermediate" | "Output",
): GraphNode {
  return {
    id,
    type: "table",
    lane: role,
    lane_index: 0,
    data: {
      name,
      role,
      source_system: null,
      grain: null,
      column_count: 0,
      produced_by: [],
      consumed_by: [],
      provenance: "H",
      confidence: "High",
      review_status: "Proposed",
    },
  };
}

function makeState(): RunState {
  return {
    run: {
      run_id: "r",
      timestamp: "2026-01-01",
      tool_version: "v",
      llm_provider: "fake",
      llm_model: "fake",
      tokens: 0,
      est_cost: 0,
      security_mode: "cloud",
    },
    models: [],
    tables: [
      {
        table_id: "t1",
        name: "raw.events",
        role: "Source",
        source_system: null,
        grain: null,
        produced_by: [],
        consumed_by: ["m"],
        columns: [
          {
            name: "amount",
            inferred_type: null,
            role: "Attribute",
            used_in: [],
            source: "H",
            confidence: "High",
            review_status: "Proposed",
          },
          {
            name: "cust_id",
            inferred_type: null,
            role: "Attribute",
            used_in: [],
            source: "H",
            confidence: "High",
            review_status: "Proposed",
          },
        ],
        source: "H",
        confidence: "High",
        review_status: "Proposed",
      },
      {
        table_id: "t2",
        name: "mart.scores",
        role: "Output",
        source_system: null,
        grain: null,
        produced_by: ["m"],
        consumed_by: [],
        columns: [
          {
            name: "total",
            inferred_type: null,
            role: "Attribute",
            used_in: [],
            source: "E",
            confidence: "High",
            review_status: "Proposed",
          },
        ],
        source: "E",
        confidence: "High",
        review_status: "Proposed",
      },
    ],
    table_edges: [],
    column_edges: [
      {
        edge_id: "ce1",
        source_element: "raw.events.amount",
        target_element: "mart.scores.total",
        model_id: "m",
        transformation_type: "aggregate",
        expression: "sum(amount)",
        join_keys: [],
        source: "E",
        confidence: "High",
        review_status: "Proposed",
      },
    ],
    dq_rules: [],
    source_systems: [],
    issues: [],
  };
}

describe("LineageCanvas", () => {
  it("renders every column from every table as a row (no expand needed)", () => {
    render(
      <LineageCanvas
        state={makeState()}
        nodes={[makeNode("t1", "raw.events", "Source"), makeNode("t2", "mart.scores", "Output")]}
        edges={[]}
        selectedEdgeId={null}
        onSelectNode={() => {}}
        onSelectEdge={() => {}}
        renderNodeHeader={(n) => <span>{n.data.name}</span>}
      />,
    );
    // Both source columns + the output column visible without any click.
    expect(screen.getByTestId("col-raw.events.amount")).toBeTruthy();
    expect(screen.getByTestId("col-raw.events.cust_id")).toBeTruthy();
    expect(screen.getByTestId("col-mart.scores.total")).toBeTruthy();
  });

  it("draws one SVG path per ColumnEdge", () => {
    render(
      <LineageCanvas
        state={makeState()}
        nodes={[makeNode("t1", "raw.events", "Source"), makeNode("t2", "mart.scores", "Output")]}
        edges={[]}
        selectedEdgeId={null}
        onSelectNode={() => {}}
        onSelectEdge={() => {}}
        renderNodeHeader={(n) => <span>{n.data.name}</span>}
      />,
    );
    // SVG overlay exists; the single column-edge draws one <path>.
    expect(screen.getByTestId("lineage-edges-svg")).toBeTruthy();
    expect(screen.getByTestId("edge-path-ce1")).toBeTruthy();
  });

  it("clicking a path fires onSelectEdge with the edge id", () => {
    const onEdge = vi.fn();
    render(
      <LineageCanvas
        state={makeState()}
        nodes={[makeNode("t1", "raw.events", "Source"), makeNode("t2", "mart.scores", "Output")]}
        edges={[]}
        selectedEdgeId={null}
        onSelectNode={() => {}}
        onSelectEdge={onEdge}
        renderNodeHeader={(n) => <span>{n.data.name}</span>}
      />,
    );
    fireEvent.click(screen.getByTestId("edge-path-ce1"));
    expect(onEdge).toHaveBeenCalledWith("ce1");
  });

  it("clicking a table card fires onSelectNode with the table id", () => {
    const onNode = vi.fn();
    render(
      <LineageCanvas
        state={makeState()}
        nodes={[makeNode("t1", "raw.events", "Source"), makeNode("t2", "mart.scores", "Output")]}
        edges={[]}
        selectedEdgeId={null}
        onSelectNode={onNode}
        onSelectEdge={() => {}}
        renderNodeHeader={(n) => <span>{n.data.name}</span>}
      />,
    );
    fireEvent.click(screen.getByTestId("node-t1"));
    expect(onNode).toHaveBeenCalledWith("t1");
  });
});
