import { fireEvent, render, screen } from "@testing-library/react";

import { ConfidenceDot, FilterChip, ProvenancePill, StatusBadge } from "./primitives";

describe("ProvenancePill", () => {
  it("renders the E/H letter", () => {
    render(<ProvenancePill source="H" />);
    const pill = screen.getByTestId("provenance-pill");
    expect(pill).toHaveAttribute("data-source", "H");
    expect(pill.textContent).toContain("H");
  });

  it("renders I as E plus a low-confidence dot (decision D7)", () => {
    render(<ProvenancePill source="I" />);
    expect(screen.getByTestId("provenance-pill")).toHaveAttribute("data-source", "I");
    expect(screen.getByTestId("confidence-dot")).toHaveAttribute("data-confidence", "Low");
  });

  it("marks U as edited", () => {
    render(<ProvenancePill source="U" />);
    expect(screen.getByTestId("provenance-pill").textContent).toContain("U");
  });
});

describe("ConfidenceDot", () => {
  it("encodes the confidence level", () => {
    render(<ConfidenceDot confidence="Medium" />);
    expect(screen.getByTestId("confidence-dot")).toHaveAttribute("data-confidence", "Medium");
  });
});

describe("StatusBadge", () => {
  it("shows an explicit Failed label", () => {
    render(<StatusBadge status="Failed" />);
    expect(screen.getByText("Failed")).toBeInTheDocument();
  });

  it("renders nothing for an Analyzed model", () => {
    const { container } = render(<StatusBadge status="Analyzed" />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("FilterChip", () => {
  it("reflects active state and fires onClick", () => {
    const onClick = vi.fn();
    const { rerender } = render(<FilterChip label="Low-confidence only" active={false} onClick={onClick} />);
    const btn = screen.getByRole("button", { name: "Low-confidence only" });
    expect(btn).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(btn);
    expect(onClick).toHaveBeenCalledOnce();
    rerender(<FilterChip label="Low-confidence only" active onClick={onClick} />);
    expect(screen.getByRole("button", { name: "Low-confidence only" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });
});
