"use client";

import { useCallback, useEffect, useState } from "react";

/**
 * The order a school wants its pupils listed in.
 *
 * Rosters used to arrive in whatever order the database felt like — the score
 * grid was ordered by the enrolment's UUID — and school registers are read by
 * name, so every roster and grid now follows one chosen key. The choice is stored
 * on the device: it is a reading preference, not a school setting, and two
 * teachers may legitimately want different orders.
 */
export const STUDENT_SORTS = [
  { value: "surname", label: "Surname (A–Z)" },
  { value: "first_name", label: "First name (A–Z)" },
  { value: "admission", label: "Admission number" },
] as const;

export type StudentSort = (typeof STUDENT_SORTS)[number]["value"];

const STORAGE_KEY = "clearis.student-sort";
const DEFAULT_SORT: StudentSort = "surname";

export function useStudentSort(): [StudentSort, (value: StudentSort) => void] {
  const [sort, setSort] = useState<StudentSort>(DEFAULT_SORT);

  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved && STUDENT_SORTS.some((option) => option.value === saved)) {
        setSort(saved as StudentSort);
      }
    } catch {
      /* a private window can refuse storage; the default order still works */
    }
  }, []);

  const update = useCallback((value: StudentSort) => {
    setSort(value);
    try {
      localStorage.setItem(STORAGE_KEY, value);
    } catch {
      /* ignore */
    }
  }, []);

  return [sort, update];
}