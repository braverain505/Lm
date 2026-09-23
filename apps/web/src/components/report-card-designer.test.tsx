import type { ReportLayout } from "@clearis/shared";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { DEFAULT_LAYOUT, cloneLayout } from "@/lib/report-layout";

import { ReportCardDesigner } from "./report-card-designer";

/**
 * The designer is fully controlled: `layout` in, `onChange` out. These tests
 * drive it through a small stateful harness (exactly how the page uses it) so
 * they assert the *resulting* document, not just that a callback fired.
 */
function Harness({
  initial,
  onChange,
  onHint,
}: {
  initial?: ReportLayout;
  onChange?: (layout: ReportLayout) => void;
  onHint?: (message: string) => void;
}) {
  const [layout, setLayout] = useState(initial ?? cloneLayout(DEFAULT_LAYOUT));
  return (
    <ReportCardDesigner
      layout={layout}
      onChange={(next) => {
        onChange?.(next);
        setLayout(next);
      }}
      onDuplicateWidgetHint={onHint}
    />
  );
}

function renderDesigner(initial?: ReportLayout) {
  const onChange = vi.fn();
  const onHint = vi.fn();
  render(<Harness initial={initial} onChange={onChange} onHint={onHint} />);
  return { onChange, onHint, user: userEvent.setup() };
}

/** The canvas rows are the only elements with an ARIA button role that are DIVs. */
function canvasRows(): HTMLElement[] {
  return screen.getAllByRole("button").filter((n) => n.tagName === "DIV") as HTMLElement[];
}

function canvasRow(label: string): HTMLElement {
  const row = canvasRows().find((r) => r.textContent?.includes(label));
  if (!row) throw new Error(`No canvas row containing "${label}"`);
  return row;
}

function lastLayout(onChange: ReturnType<typeof vi.fn>): ReportLayout {
  const call = onChange.mock.calls.at(-1);
  if (!call) throw new Error("onChange was never called");
  return call[0] as ReportLayout;
}

describe("ReportCardDesigner — rendering", () => {
  it("draws the saved card's blocks in order", () => {
    renderDesigner();
    const rows = canvasRows();
    expect(rows).toHaveLength(DEFAULT_LAYOUT.widgets.length);
    expect(rows[0].textContent).toContain("Card header");
    expect(rows[rows.length - 1].textContent).toContain("Comments");
  });

  it("prompts for a block before showing any settings", () => {
    renderDesigner();
    expect(screen.getByText(/Pick a block on the card/i)).toBeInTheDocument();
  });

  it("invites the first block when the card is empty", () => {
    renderDesigner({ version: 1, theme: "classic", widgets: [] });
    expect(screen.getByText(/The card is empty/i)).toBeInTheDocument();
    expect(canvasRows()).toHaveLength(0);
  });

  it("offers every block in the palette, grouped", () => {
    renderDesigner();
    expect(screen.getByText("Blocks")).toBeInTheDocument();
    expect(screen.getByText(/Drag onto the card/i)).toBeInTheDocument();
    // A representative block from each group.
    for (const label of ["Card header", "Student details", "Grading key", "Comments", "Spacer"]) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    }
  });

  it("adds a block by clicking it in the palette", async () => {
    const { user, onChange } = renderDesigner();
    const before = canvasRows().length;
    await user.click(screen.getByTitle("Blank vertical space, to push blocks apart."));
    const layout = lastLayout(onChange);
    expect(layout.widgets).toHaveLength(before + 1);
    expect(layout.widgets.at(-1)?.type).toBe("spacer");
  });

  it("ignores a click on a block the card already has", async () => {
    const { user, onChange } = renderDesigner();
    await user.click(screen.getByTitle("Card header is already on this card"));
    expect(onChange).not.toHaveBeenCalled();
  });

  it("greys out a unique block that is already on the card", () => {
    renderDesigner();
    // A disabled palette entry re-purposes its tooltip to say why it can't be added.
    const headerPalette = screen.getByTitle("Card header is already on this card");
    expect(headerPalette).toBeDisabled();
    // A repeatable block that is not on the card stays available.
    expect(screen.getByTitle("Blank vertical space, to push blocks apart.")).toBeEnabled();
  });
});

describe("ReportCardDesigner — selecting and editing a block", () => {
  it("shows the block's settings once it is selected", async () => {
    const { user } = renderDesigner();
    await user.click(canvasRow("Grading key"));
    // The inspector now lists the block's own fields.
    expect(screen.getByText("Settings")).toBeInTheDocument();
    expect(screen.getByLabelText("Heading")).toHaveValue("Grading Key");
  });

  it("writes an edited setting through to the layout", async () => {
    const { user, onChange } = renderDesigner();
    await user.click(canvasRow("Card header"));
    const title = screen.getByLabelText("Title");
    await user.clear(title);
    await user.type(title, "End of Term Report");
    const layout = lastLayout(onChange);
    const header = layout.widgets.find((w) => w.type === "header")!;
    expect(header.props?.title).toBe("End of Term Report");
    // Untouched settings survive the edit.
    expect(header.props?.show_photo).toBe(true);
  });

  it("toggles a boolean setting", async () => {
    const { user, onChange } = renderDesigner();
    await user.click(canvasRow("Card header"));
    await user.click(screen.getByLabelText("Student photo"));
    const header = lastLayout(onChange).widgets.find((w) => w.type === "header")!;
    expect(header.props?.show_photo).toBe(false);
  });

  it("pairs a block half-width from the inspector", async () => {
    const { user, onChange } = renderDesigner();
    await user.click(canvasRow("Grading key"));
    await user.selectOptions(screen.getByLabelText("Width"), "half");
    const key = lastLayout(onChange).widgets.find((w) => w.type === "grading_key")!;
    expect(key.props?.width).toBe("half");
  });
});

describe("ReportCardDesigner — reordering, hiding, removing", () => {
  it("disables Move up on the first block and Move down on the last", () => {
    renderDesigner();
    const rows = canvasRows();
    expect(within(rows[0]).getByLabelText("Move up")).toBeDisabled();
    expect(within(rows[0]).getByLabelText("Move down")).toBeEnabled();
    expect(within(rows[rows.length - 1]).getByLabelText("Move down")).toBeDisabled();
  });

  it("moves a block down", async () => {
    const { user, onChange } = renderDesigner();
    await user.click(within(canvasRows()[0]).getByLabelText("Move down"));
    const layout = lastLayout(onChange);
    expect(layout.widgets[0].type).toBe("student_info");
    expect(layout.widgets[1].type).toBe("header");
  });

  it("moves a block up", async () => {
    const { user, onChange } = renderDesigner();
    await user.click(within(canvasRows()[3]).getByLabelText("Move up"));
    const layout = lastLayout(onChange);
    expect(layout.widgets[2].type).toBe("psychomotor_domain");
    expect(layout.widgets[3].type).toBe("cognitive_domain");
  });

  it("hides a block without deleting it", async () => {
    const { user, onChange } = renderDesigner();
    await user.click(within(canvasRow("Card header")).getByLabelText("Hide from the card"));
    const header = lastLayout(onChange).widgets.find((w) => w.type === "header")!;
    expect(header.hidden).toBe(true);
    // The row stays on the card and now offers to show it again.
    expect(within(canvasRow("Card header")).getByLabelText("Show on the card")).toBeInTheDocument();
  });

  it("removes a block and clears the selection", async () => {
    const { user, onChange } = renderDesigner();
    const before = canvasRows().length;
    await user.click(within(canvasRow("Card header")).getByLabelText("Remove"));
    const layout = lastLayout(onChange);
    expect(layout.widgets.map((w) => w.type)).not.toContain("header");
    expect(layout.widgets).toHaveLength(before - 1);
    expect(canvasRows()).toHaveLength(before - 1);
  });
});

describe("ReportCardDesigner — duplicating", () => {
  it("inserts a copy directly after a repeatable block", async () => {
    const { user, onChange } = renderDesigner();
    const before = canvasRows().length;
    await user.click(within(canvasRow("Grading key")).getByLabelText("Duplicate"));
    const layout = lastLayout(onChange);
    expect(layout.widgets).toHaveLength(before + 1);
    const index = layout.widgets.findIndex((w) => w.type === "grading_key");
    expect(layout.widgets[index + 1].type).toBe("grading_key");
    expect(layout.widgets[index + 1].id).not.toBe(layout.widgets[index].id);
  });

  it("refuses to duplicate a unique block and explains why", async () => {
    const { user, onChange, onHint } = renderDesigner();
    await user.click(within(canvasRow("Card header")).getByLabelText("Duplicate"));
    expect(onHint).toHaveBeenCalledTimes(1);
    expect(onHint.mock.calls[0][0]).toMatch(/only have one card header/i);
    // The card itself is left alone.
    expect(onChange).not.toHaveBeenCalled();
  });
});

describe("ReportCardDesigner — theme and preview", () => {
  it("writes the chosen theme into the layout", async () => {
    const { user, onChange } = renderDesigner();
    await user.click(screen.getByRole("button", { name: "Use the Modern theme" }));
    expect(lastLayout(onChange).theme).toBe("modern");
  });

  it("swaps the canvas for the sample card in preview", async () => {
    const { user } = renderDesigner();
    await user.click(screen.getByRole("button", { name: /Preview/ }));
    expect(screen.getByText(/Sample data — a real card shows/i)).toBeInTheDocument();
    // Back to designing.
    await user.click(screen.getByRole("button", { name: /Design/ }));
    expect(screen.getByText("Blocks")).toBeInTheDocument();
  });
});
