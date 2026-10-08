import type { WorkbenchRow } from "@clearis/shared";
import { describe, expect, it } from "vitest";

import { cellStage, isEntered, needsAction, nextStep, summarise } from "./workbench";

const uuid = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;

/** A fully-entered cell in draft, overridden per test. */
const row = (over: Partial<WorkbenchRow> = {}): WorkbenchRow => ({
  arm_id: uuid(1),
  term_id: uuid(2),
  arm_name: "JSS 1A",
  subject_id: uuid(3),
  subject_name: "Mathematics",
  enrolled: 5,
  entered: 5,
  draft: 5,
  submitted: 0,
  verified: 0,
  approved: 0,
  rejected: 0,
  published: 0,
  ...over,
});

describe("isEntered — what 'Process ready results' may act on", () => {
  it("counts a fully-entered draft cell", () => {
    expect(isEntered(row())).toBe(true);
  });

  it("counts a fully-entered SUBMITTED cell so the button is not grey after teachers submit", () => {
    expect(isEntered(row({ draft: 0, submitted: 5 }))).toBe(true);
  });

  it("counts verified and approved cells", () => {
    expect(isEntered(row({ draft: 0, verified: 5 }))).toBe(true);
    expect(isEntered(row({ draft: 0, approved: 5 }))).toBe(true);
  });

  it("excludes a cell that is only partly entered", () => {
    expect(isEntered(row({ entered: 4 }))).toBe(false);
  });

  it("excludes a cell with no enrolled students", () => {
    expect(isEntered(row({ enrolled: 0, entered: 0, draft: 0 }))).toBe(false);
  });

  it("excludes a fully-published cell", () => {
    expect(isEntered(row({ draft: 0, published: 5 }))).toBe(false);
  });
});

describe("pipeline stage helpers", () => {
  it("puts a cell in the earliest actionable stage", () => {
    expect(cellStage(row({ draft: 0, submitted: 2, verified: 3 }))).toBe("submitted");
    expect(cellStage(row({ draft: 0, verified: 3, approved: 1 }))).toBe("verified");
    expect(cellStage(row({ draft: 0, approved: 1 }))).toBe("approved");
    expect(cellStage(row({ draft: 2 }))).toBe("draft");
    expect(cellStage(row({ draft: 0, published: 5 }))).toBe("published");
  });

  it("reports the one next action", () => {
    expect(nextStep(row({ draft: 0, submitted: 5 }))?.action).toBe("verify");
    expect(nextStep(row({ draft: 0, verified: 5 }))?.action).toBe("approve");
    expect(nextStep(row({ draft: 0, approved: 5 }))?.action).toBe("publish");
    expect(nextStep(row())).toBeNull();
  });

  it("flags cells waiting on a reviewer", () => {
    expect(needsAction(row({ draft: 0, submitted: 5 }))).toBe(true);
    expect(needsAction(row())).toBe(false);
  });

  it("summarises action across a set of cells", () => {
    const totals = summarise([
      row(),
      row({ draft: 0, submitted: 5 }),
      row({ draft: 0, published: 5, subject_id: uuid(4) }),
    ]);
    expect(totals.action).toBe(1);
    expect(totals.stages.submitted).toBe(1);
    expect(totals.stages.published).toBe(1);
  });
});
