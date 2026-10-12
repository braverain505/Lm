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
 * Class broadsheet: one row per student, one column per subject, average last.
 *
 * Subjects come from the first card, so a class with an uneven set of published
 * subjects still produces one consistent grid.
 */
export function broadsheetRows(cards: ReportCard[]): Cell[][] {
  const subjects = cards[0]?.subjects ?? [];
  const header: Cell[] = [
    "Student",
    "Admission no",
    ...subjects.map((subject) => subject.subject_name),
    "Average",
  ];

  const rows = cards.map((card): Cell[] => [
    card.student.full_name,
    card.student.admission_no,
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
