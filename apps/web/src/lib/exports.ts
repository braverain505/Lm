import type { ReportCard } from "@clearis/shared";

/**
 * Row builders for the spreadsheet exports.
 *
 * The pages used to assemble these rows inline, which meant the only way to
 * check the columns a school actually receives was to click Download in a
 * browser. Keeping the shape here — pure data in, rows out — lets the exact
 * grid be tested, and keeps the three pages consistent about the things that
 * matter: a leading identity column, a trailing summary column, and a blank
 * cell (never a zero) wherever a mark is genuinely missing.
 */

export type Cell = string | number;

/** A missing value has to read as blank, or a spreadsheet will summarise it as 0. */
function value(input: number | null | undefined): Cell {
  return input ?? "";
}

/**
 * The subject columns of a broadsheet: every subject any card on the sheet was
 * published in, in a stable order.
 *
 * The union, not the first card's list. Over a single class the two are the
 * same, but a class-group sheet (all of SS 1) spans classes that sit different
 * subjects — taking the first card's list would silently drop Physics because
 * the alphabetically first class happens to be an Arts class.
 */
export function broadsheetSubjects(
  cards: ReportCard[],
): { subject_id: string; subject_name: string }[] {
  const byId = new Map<string, string>();
  for (const card of cards) {
    for (const subject of card.subjects) {
      if (!byId.has(subject.subject_id)) byId.set(subject.subject_id, subject.subject_name);
    }
  }
  return [...byId.entries()]
    .map(([subject_id, subject_name]) => ({ subject_id, subject_name }))
    .sort((a, b) => a.subject_name.localeCompare(b.subject_name));
}

/**
 * Class broadsheet: one row per student, one column per subject, average last.
 *
 * A pupil who does not offer a subject leaves that cell blank rather than
 * zero — on a class-group sheet that blank is the information, showing which
 * class sits what.
 */
export function broadsheetRows(cards: ReportCard[]): Cell[][] {
  const subjects = broadsheetSubjects(cards);
  const header: Cell[] = [
    "Student",
    "Admission no",
    "Class",
    "Position",
    ...subjects.map((subject) => subject.subject_name),
    "Average",
  ];

  const rows = cards.map((card): Cell[] => [
    card.student.full_name,
    card.student.admission_no,
    card.class_arm.full_name,
    value(card.summary.class_rank),
    ...subjects.map((subject) => {
      const current = card.subjects.find((item) => item.subject_id === subject.subject_id);
      return value(current?.total);
    }),
    value(card.summary.average),
  ]);

  return [header, ...rows];
}

export interface CumulativeSheet {
  subjects: {
    subject_name: string;
    average: number | null;
    terms: { term_name: string; total: number | null }[];
  }[];
}

/**
 * Cumulative sheet: one row per subject, one column per term, session average
 * last — a whole year readable across the row.
 */
export function cumulativeRows(data: CumulativeSheet): Cell[][] {
  const terms = data.subjects[0]?.terms ?? [];
  const header: Cell[] = ["Subject", ...terms.map((term) => term.term_name), "Average"];

  const rows = data.subjects.map((subject): Cell[] => [
    subject.subject_name,
    ...subject.terms.map((term) => value(term.total)),
    value(subject.average),
  ]);

  return [header, ...rows];
}

export interface ScoreSheet {
  components: { id: string; name: string; max_score: number }[];
  students: { enrollment_id: string; full_name: string; admission_no: string }[];
}

/**
 * A teacher's scoresheet: one row per student, one column per assessment
 * component, with the running total and grade on the end.
 *
 * The three resolvers are passed in rather than recomputed here on purpose: the
 * page's versions already fold in unsaved edits, so the file a teacher downloads
 * is the grid they are looking at, not what was last saved.
 */
export function scoresheetRows(
  card: ScoreSheet,
  cell: (enrollmentId: string, componentId: string) => string,
  total: (enrollmentId: string) => number | null,
  grade: (enrollmentId: string) => string | null,
  label: (name: string) => string = (name) => name,
): Cell[][] {
  const header: Cell[] = [
    "Student",
    "Admission no",
    // The maximum rides in the header, so the sheet explains its own scale.
    ...card.components.map((component) => `${label(component.name)} (/${component.max_score})`),
    "Total",
    "Grade",
  ];

  const rows = card.students.map((row): Cell[] => [
    row.full_name,
    row.admission_no,
    ...card.components.map((component) => cell(row.enrollment_id, component.id)),
    value(total(row.enrollment_id)),
    grade(row.enrollment_id) ?? "",
  ]);

  return [header, ...rows];
}
