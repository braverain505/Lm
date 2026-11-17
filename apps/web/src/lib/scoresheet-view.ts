import type { MyAssignment, ScoreCard } from "@clearis/shared";

/**
 * Reading helpers for the teacher's own scoresheet.
 *
 * "View Scoresheet" answers one question — what marks have I entered, for this
 * class? — so the arithmetic that answers it lives here, away from the page, and
 * is pinned by tests. Everything is derived from what the API already stored;
 * nothing is recomputed from a live draft, because the point is to show the
 * teacher what is actually saved, not what a screen thinks it should be.
 */

/**
 * A mark as text, and empty when nothing was entered — the form a spreadsheet
 * wants. The page prints a dash in that case (`markText(value) || "—"`), so an
 * unmarked cell reads as "nothing here" on screen and as genuinely blank in a
 * download, rather than as the word that means nothing.
 */
export function markText(value: number | null | undefined): string {
  return value === null || value === undefined ? "" : String(value);
}

export interface SheetProgress {
  pupils: number;
  /** Pupils with at least one component marked. */
  scored: number;
  /** Pupils with every component marked. */
  complete: number;
}

/**
 * How much of one class × subject grid is filled in.
 *
 * A grid with no components has nothing to be complete about, so every pupil
 * counts as neither scored nor complete — the page says the school has not set
 * up its assessment structure, rather than claiming the class is finished.
 */
export function sheetProgress(card: ScoreCard): SheetProgress {
  const components = card.components.length;
  let scored = 0;
  let complete = 0;
  for (const row of card.students) {
    const marks = card.components.filter((component) => {
      const value = row.scores[component.id];
      return value !== null && value !== undefined;
    }).length;
    if (marks > 0) scored += 1;
    if (components > 0 && marks === components) complete += 1;
  }
  return { pupils: card.students.length, scored, complete };
}

/** Whether the teacher has entered anything at all for this grid. */
export function isUnmarked(progress: SheetProgress): boolean {
  return progress.scored === 0;
}

export interface AssignedClass {
  arm_id: string;
  arm_name: string;
}

/**
 * The classes a teacher is assigned to, in the order the API lists them.
 *
 * The classes come from the teacher's own subject assignments rather than the
 * school's arm list: the API only serves a grid to the teacher assigned to it,
 * so offering a class the teacher does not teach would only produce a refusal.
 * One entry per class even when several subjects are taught there.
 */
export function assignedClasses(assignments: MyAssignment[]): AssignedClass[] {
  const seen = new Set<string>();
  const classes: AssignedClass[] = [];
  for (const assignment of assignments) {
    if (seen.has(assignment.arm_id)) continue;
    seen.add(assignment.arm_id);
    classes.push({ arm_id: assignment.arm_id, arm_name: assignment.arm_name });
  }
  return classes;
}

/** The subjects the teacher is assigned within one class. */
export function assignedSubjects(
  assignments: MyAssignment[],
  armId: string | null,
): MyAssignment[] {
  if (!armId) return [];
  return assignments.filter((assignment) => assignment.arm_id === armId);
}

/**
 * The term a teacher most likely wants first: the one open for entry, else the
 * session's current term, else the first listed.
 */
export function defaultTermId<T extends { id: string; status?: string; is_current?: boolean }>(
  terms: T[],
): string {
  const open = terms.find((term) => term.status === "open");
  if (open) return open.id;
  const current = terms.find((term) => term.is_current);
  if (current) return current.id;
  return terms[0]?.id ?? "";
}
