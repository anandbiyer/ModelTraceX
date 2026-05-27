import { fireEvent, render, screen } from "@testing-library/react";

import { Inspector } from "./Inspector";

const editable = [{ field: "role", label: "Role", value: "Source", options: ["Source", "Output"] }];

describe("Inspector", () => {
  it("accept/reject post a review_status override (NFR-5)", () => {
    const onOverride = vi.fn();
    render(
      <Inspector
        title="raw.customer"
        rows={[]}
        provenance="E"
        confidence="High"
        reviewStatus="Proposed"
        editable={editable}
        onOverride={onOverride}
      />,
    );
    fireEvent.click(screen.getByTestId("accept"));
    expect(onOverride).toHaveBeenCalledWith("review_status", "Accepted");
    fireEvent.click(screen.getByTestId("reject"));
    expect(onOverride).toHaveBeenCalledWith("review_status", "Rejected");
  });

  it("edit reveals the field and posts its new value", () => {
    const onOverride = vi.fn();
    render(<Inspector title="t" rows={[]} editable={editable} onOverride={onOverride} />);
    expect(screen.queryByTestId("edit-role")).toBeNull();
    fireEvent.click(screen.getByTestId("edit"));
    fireEvent.change(screen.getByTestId("edit-role"), { target: { value: "Output" } });
    expect(onOverride).toHaveBeenCalledWith("role", "Output");
  });

  it("uses the statusField override key for DQ rules", () => {
    const onOverride = vi.fn();
    render(<Inspector title="rule" rows={[]} statusField="status" onOverride={onOverride} />);
    fireEvent.click(screen.getByTestId("accept"));
    expect(onOverride).toHaveBeenCalledWith("status", "Accepted");
  });

  it("renders provenance + confidence for the selected entity", () => {
    render(<Inspector title="t" rows={[{ label: "Role", value: "Source" }]} provenance="H" confidence="Low" onOverride={vi.fn()} />);
    expect(screen.getByTestId("provenance-pill")).toHaveAttribute("data-source", "H");
    expect(screen.getByTestId("confidence-dot")).toHaveAttribute("data-confidence", "Low");
  });
});
