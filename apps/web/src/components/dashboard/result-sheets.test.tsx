import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ResultSheetsPanel } from "./result-sheets";

/**
 * The panel is the admin dashboard's way in to the two result sheets, so what
 * matters is that both entries are present and point at the pages that actually
 * exist — not at a near-miss URL that would 404.
 */
describe("ResultSheetsPanel", () => {
  it("offers the class broadsheet and the cumulative sheet", () => {
    render(<ResultSheetsPanel />);

    expect(screen.getByRole("link", { name: /class broadsheet/i })).toHaveAttribute(
      "href",
      "/reports/broadsheet",
    );
    expect(screen.getByRole("link", { name: /cumulative results/i })).toHaveAttribute(
      "href",
      "/reports/cumulative",
    );
  });

  it("explains what each sheet is for, so the choice is not a guess", () => {
    render(<ResultSheetsPanel />);

    expect(screen.getByText(/every subject side by side/i)).toBeInTheDocument();
    expect(screen.getByText(/subject averages across a whole session/i)).toBeInTheDocument();
  });
});
