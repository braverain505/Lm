import { describe, expect, it } from "vitest";

import { slug } from "./csv";
import { broadsheetRows, cumulativeRows, scoresheetRows } from "./exports";

/**
 * These assertions describe the file a school actually opens: the column order,
 * where the summary lands, and — most importantly — that a missing mark is a
 * blank cell rather than a zero, which would drag an average down in Excel.
 */

describe("broadsheetRows", () => {
  const card = (overrides: Record<string, unknown>) =>
    ({
      student: { full_name: "Amaka Okafor", admission_no: "BFA/2024/018" },
      subjects: [
        { subject_id: "m", subject_name: "Mathematics", total: 93 },
        { subject_id: "e", subject_name: "English Language", total: 74 },
      ],
      summary: { average: 83.5 },
      ...overrides,
    }) as never;

  it("writes a header of student, admission number, each subject, then average", () => {
    expect(broadsheetRows([card({})])[0]).toEqual([
      "Student",
      "Admission no",
      "Mathematics",
      "English Language",
      "Average",
    ]);
  });

  it("keeps one row per student with the marks aligned to the subject columns", () => {
    const rows = broadsheetRows([card({})]);
    expect(rows).toHaveLength(2);
    expect(rows[1]).toEqual(["Amaka Okafor", "BFA/2024/018", 93, 74, 83.5]);
  });

  it("leaves a subject the student has no published mark for blank, not zero", () => {
    const rows = broadsheetRows([
      card({ subjects: [{ subject_id: "m", subject_name: "Mathematics", total: null }] }),
    ]);
    expect(rows[1][2]).toBe("");
  });

  it("returns only a header when there is nothing published", () => {
    expect(broadsheetRows([])).toEqual([
      ["Student", "Admission no", "Average"],
    ]);
  });
});

describe("cumulativeRows", () => {
  const data = {
    subjects: [
      {
        subject_name: "Mathematics",
        average: 81,
        terms: [
          { term_name: "First Term", total: 78 },
          { term_name: "Second Term", total: 84 },
        ],
      },
      {
        subject_name: "Basic Science",
        average: null,
        terms: [
          { term_name: "First Term", total: 66 },
          { term_name: "Second Term", total: null },
        ],
      },
    ],
  };

  it("writes terms across the header with the session average last", () => {
    expect(cumulativeRows(data)[0]).toEqual([
      "Subject",
      "First Term",
      "Second Term",
      "Average",
    ]);
  });

  it("keeps each subject's terms in order and blanks an unrecorded term", () => {
    const rows = cumulativeRows(data);
    expect(rows[1]).toEqual(["Mathematics", 78, 84, 81]);
    expect(rows[2]).toEqual(["Basic Science", 66, "", ""]);
  });
});

describe("scoresheetRows", () => {
  const card = {
    components: [
      { id: "ca1", name: "CA 1", max_score: 20 },
      { id: "exam", name: "Exam", max_score: 60 },
    ],
    students: [
      { enrollment_id: "e1", full_name: "Amaka Okafor", admission_no: "BFA/2024/018" },
      { enrollment_id: "e2", full_name: "Tobi Balogun", admission_no: "BFA/2024/033" },
    ],
  };

  const cells: Record<string, string> = { "e1:ca1": "18", "e1:exam": "58" };
  const cell = (enrollmentId: string, componentId: string) =>
    cells[`${enrollmentId}:${componentId}`] ?? "";
  const total = (enrollmentId: string) => (enrollmentId === "e1" ? 76 : 0);
  const grade = (enrollmentId: string) => (enrollmentId === "e1" ? "A" : "F");

  it("labels each component column with its maximum score", () => {
    const header = scoresheetRows(card, cell, total, grade)[0];
    expect(header).toEqual([
      "Student",
      "Admission no",
      "CA 1 (/20)",
      "Exam (/60)",
      "Total",
      "Grade",
    ]);
  });

  it("carries the admission number and each mark through for every student", () => {
    const rows = scoresheetRows(card, cell, total, grade);
    expect(rows[1]).toEqual(["Amaka Okafor", "BFA/2024/018", "18", "58", 76, "A"]);
  });

  it("leaves a mark with no entry blank so the sheet does not understate a total", () => {
    const rows = scoresheetRows(card, cell, total, grade);
    expect(rows[2]).toEqual(["Tobi Balogun", "BFA/2024/033", "", "", 0, "F"]);
  });

  it("applies the caller's own component labelling", () => {
    const header = scoresheetRows(card, cell, total, grade, (name) => `${name}!`)[0];
    expect(header[2]).toBe("CA 1! (/20)");
  });

  it("omits a grade the caller cannot determine instead of inventing one", () => {
    const rows = scoresheetRows(card, cell, total, () => null);
    expect(rows[1][5]).toBe("");
  });
});

describe("slug", () => {
  it("turns school-supplied names into a safe filename fragment", () => {
    expect(slug("JSS 2B")).toBe("jss-2b");
    expect(slug("First Term · 2025/2026")).toBe("first-term-2025-2026");
    expect(slug("Basic Science")).toBe("basic-science");
  });

  it("never returns an empty fragment", () => {
    expect(slug("///")).toBe("export");
  });
});
