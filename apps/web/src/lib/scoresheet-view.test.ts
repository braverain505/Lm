import type { MyAssignment, ScoreCard } from "@clearis/shared";
import { describe, expect, it } from "vitest";

import {
  assignedClasses,
  assignedSubjects,
  defaultTermId,
  isUnmarked,
  markText,
  sheetProgress,
} from "./scoresheet-view";

const uuid = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;

const component = (id: number, name: string) => ({
  id: uuid(id),
  name,
  max_score: 20,
  weight: 50,
});

/** One class × subject grid; override the parts a test cares about. */
const card = (over: Partial<ScoreCard> = {}): ScoreCard => ({
  arm: { id: uuid(1), full_name: "Primary 3A" },
  subject: { id: uuid(2), name: "Mathematics" },
  term: { id: uuid(3), name: "First Term" },
  components: [component(10, "1st CA"), component(11, "2nd CA")],
  students: [
    {
      enrollment_id: uuid(20),
      student_id: uuid(30),
      admission_no: "ECWA-2026-0001",
      full_name: "Ada One",
      scores: { [uuid(10)]: 12, [uuid(11)]: 14 },
      total: 65,
      grade_letter: "B",
      status: "draft",
    },
  ],
  ...over,
});

const assignment = (armId: number, armName: string, subjectId: number): MyAssignment => ({
  arm_id: uuid(armId),
  arm_name: armName,
  subject_id: uuid(subjectId),
  subject_name: "Maths",
  assignment_id: uuid(subjectId + 100),
});

describe("markText — what an unmarked cell is worth", () => {
  it("prints a mark as it was saved", () => {
    expect(markText(17)).toBe("17");
    expect(markText(0)).toBe("0");
  });

  it("is empty for a cell with no mark, including a score of nothing recorded", () => {
    expect(markText(null)).toBe("");
    expect(markText(undefined)).toBe("");
  });
});

describe("sheetProgress — how much of a grid the teacher has entered", () => {
  it("counts a pupil complete when every component carries a mark", () => {
    const progress = sheetProgress(card());
    expect(progress).toEqual({ pupils: 1, scored: 1, complete: 1 });
  });

  it("counts a part-marked pupil as scored but not complete", () => {
    const progress = sheetProgress(
      card({
        students: [
          {
            ...card().students[0],
            scores: { [uuid(10)]: 12, [uuid(11)]: null },
          },
        ],
      }),
    );
    expect(progress).toEqual({ pupils: 1, scored: 1, complete: 0 });
  });

  it("separates an untouched pupil from a part-marked one", () => {
    const base = card().students[0];
    const progress = sheetProgress(
      card({
        students: [
          { ...base, enrollment_id: uuid(21), scores: { [uuid(10)]: 12, [uuid(11)]: null } },
          { ...base, enrollment_id: uuid(22), scores: { [uuid(10)]: null, [uuid(11)]: null } },
        ],
      }),
    );
    expect(progress).toEqual({ pupils: 2, scored: 1, complete: 0 });
  });

  it("treats a zero as a mark that was entered, not as an empty cell", () => {
    const progress = sheetProgress(
      card({
        students: [{ ...card().students[0], scores: { [uuid(10)]: 0, [uuid(11)]: 0 } }],
      }),
    );
    expect(progress).toEqual({ pupils: 1, scored: 1, complete: 1 });
    expect(isUnmarked(progress)).toBe(false);
  });

  it("claims nothing is complete when the school has set up no components", () => {
    // Otherwise a class with no assessment structure would read as finished.
    const progress = sheetProgress(card({ components: [] }));
    expect(progress).toEqual({ pupils: 1, scored: 0, complete: 0 });
    expect(isUnmarked(progress)).toBe(true);
  });

  it("reads an empty class as untouched", () => {
    expect(isUnmarked(sheetProgress(card({ students: [] })))).toBe(true);
  });
});

describe("assignedClasses — the classes the teacher may open", () => {
  it("lists each class once, however many subjects are taught there", () => {
    const classes = assignedClasses([
      assignment(1, "Primary 3A", 2),
      assignment(1, "Primary 3A", 3),
      assignment(4, "Primary 5", 5),
    ]);
    expect(classes).toEqual([
      { arm_id: uuid(1), arm_name: "Primary 3A" },
      { arm_id: uuid(4), arm_name: "Primary 5" },
    ]);
  });

  it("offers nothing to a teacher with no assignments", () => {
    expect(assignedClasses([])).toEqual([]);
  });
});

describe("assignedSubjects — the subjects behind one class", () => {
  const assignments = [assignment(1, "Primary 3A", 2), assignment(1, "Primary 3A", 3), assignment(4, "Primary 5", 5)];

  it("keeps only the chosen class's subjects", () => {
    const subjects = assignedSubjects(assignments, uuid(1));
    expect(subjects.map((s) => s.subject_id)).toEqual([uuid(2), uuid(3)]);
  });

  it("returns nothing before a class is chosen", () => {
    expect(assignedSubjects(assignments, null)).toEqual([]);
  });
});

describe("defaultTermId — which term opens first", () => {
  it("prefers the term open for entry", () => {
    expect(
      defaultTermId([
        { id: "a", status: "planned" },
        { id: "b", status: "open" },
        { id: "c", status: "closed" },
      ]),
    ).toBe("b");
  });

  it("falls back to the current term when none is open", () => {
    expect(defaultTermId([{ id: "a", status: "closed" }, { id: "b", status: "closed", is_current: true }])).toBe("b");
  });

  it("falls back to the first term when nothing is marked", () => {
    expect(defaultTermId([{ id: "a" }, { id: "b" }])).toBe("a");
  });

  it("returns an empty choice for a session with no terms", () => {
    expect(defaultTermId([])).toBe("");
  });
});
