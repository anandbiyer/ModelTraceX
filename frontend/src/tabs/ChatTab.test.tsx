/**
 * ChatTab vitest — covers the SDD §13.4.5 contract: a typed mutation plan is
 * surfaced as a diff + action buttons; `triggers_llm` controls the "Apply &
 * re-run" vs "Apply without re-run" pair; `requires_confirmation` disables the
 * no-rerun path; applying calls the chat/apply endpoint.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { ChatTab } from "./ChatTab";
import { useUI } from "../store/ui";

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  // Pretend a run has been analyzed so the tab proceeds past the empty state.
  useUI.setState({ runId: "run_test" });
  globalThis.fetch = fetchMock as unknown as typeof fetch;
});

function jsonResp(body: unknown): Response {
  return {
    ok: true,
    status: 200,
    statusText: "OK",
    json: () => Promise.resolve(body),
  } as unknown as Response;
}

function withQuery(node: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{node}</QueryClientProvider>;
}

describe("ChatTab", () => {
  it("renders a mutation diff with re-run + no-rerun buttons for an LLM-bearing op", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResp({
        rationale: "Two staging tables match.",
        mutations: [
          {
            op: "set_lineage_detail",
            args: { model_ids: ["m1"], detail: "column" },
            requires_confirmation: false,
            triggers_llm: true,
            invalidates: ["analysis", "stitch", "dq", "export"],
          },
        ],
      }),
    );

    render(withQuery(<ChatTab />));
    fireEvent.change(screen.getByTestId("chat-input"), {
      target: { value: "raise scoring to column level" },
    });
    fireEvent.click(screen.getByTestId("chat-send"));

    await waitFor(() => expect(screen.getByTestId("chat-rationale")).toBeTruthy());
    expect(screen.getByTestId("diff-block")).toBeTruthy();
    expect(screen.getByTestId("apply-rerun").textContent).toMatch(/Apply & re-run/);
    expect(screen.getByTestId("apply-norerun")).toBeTruthy();
  });

  it("projection-only op hides the no-rerun button (single action)", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResp({
        rationale: "",
        mutations: [
          {
            op: "set_table_role",
            args: { table_id: "t1", role: "Intermediate" },
            requires_confirmation: false,
            triggers_llm: false,
            invalidates: ["stitch", "dq", "export"],
          },
        ],
      }),
    );
    render(withQuery(<ChatTab />));
    fireEvent.change(screen.getByTestId("chat-input"), {
      target: { value: "treat stg_* as intermediate" },
    });
    fireEvent.click(screen.getByTestId("chat-send"));

    await waitFor(() => expect(screen.getByTestId("apply-rerun")).toBeTruthy());
    expect(screen.queryByTestId("apply-norerun")).toBeNull();
    expect(screen.getByTestId("apply-rerun").textContent).toMatch(/no LLM/);
  });

  it("requires_confirmation disables the no-rerun shortcut", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResp({
        rationale: "",
        mutations: [
          {
            op: "merge_models",
            args: { model_ids: ["m1", "m2"], label: "scoring" },
            requires_confirmation: true,
            triggers_llm: true,
            invalidates: ["analysis", "stitch", "dq", "export"],
          },
        ],
      }),
    );
    render(withQuery(<ChatTab />));
    fireEvent.change(screen.getByTestId("chat-input"), { target: { value: "merge m1 and m2" } });
    fireEvent.click(screen.getByTestId("chat-send"));

    await waitFor(() => expect(screen.getByTestId("apply-rerun")).toBeTruthy());
    expect((screen.getByTestId("apply-norerun") as HTMLButtonElement).disabled).toBe(true);
  });

  it("Send POSTs to /chat/apply when a mutation is applied", async () => {
    fetchMock
      .mockResolvedValueOnce(
        jsonResp({
          rationale: "",
          mutations: [
            {
              op: "set_table_role",
              args: { table_id: "t1", role: "Intermediate" },
              requires_confirmation: false,
              triggers_llm: false,
              invalidates: ["stitch", "dq", "export"],
            },
          ],
        }),
      )
      .mockResolvedValueOnce(
        jsonResp({
          ok: true,
          reanalyzed: [],
          llm_used: false,
          counts: { tables: 1, table_edges: 0, dq_rules: 0, pending_review: 0 },
        }),
      );
    render(withQuery(<ChatTab />));
    fireEvent.change(screen.getByTestId("chat-input"), { target: { value: "reclassify" } });
    fireEvent.click(screen.getByTestId("chat-send"));
    await waitFor(() => expect(screen.getByTestId("apply-rerun")).toBeTruthy());

    fireEvent.click(screen.getByTestId("apply-rerun"));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    const call = fetchMock.mock.calls[1];
    expect(call[0]).toBe("/runs/run_test/chat/apply");
    expect(JSON.parse(call[1].body)).toEqual({
      mutations: [{ op: "set_table_role", args: { table_id: "t1", role: "Intermediate" } }],
    });
  });
});
