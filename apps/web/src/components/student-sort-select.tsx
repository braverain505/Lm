"use client";

import { ArrowDownAZ } from "lucide-react";

import { STUDENT_SORTS, type StudentSort } from "@/hooks/use-student-sort";

/**
 * The order pupils are listed in, next to whatever else the page is filtering by.
 *
 * It is one small control because the choice is small and recurring: a register
 * is read by surname in one school and by first name in the next, and a teacher
 * checking a mark wants the same order the class sits in.
 */
export function StudentSortSelect({
  value,
  onChange,
  className,
}: {
  value: StudentSort;
  onChange: (value: StudentSort) => void;
  className?: string;
}) {
  return (
    <label
      className={
        className ??
        "flex items-center gap-2 rounded-xl border border-border/80 bg-background/70 px-3 py-2 text-[12px] font-medium text-muted-foreground"
      }
      title="The order pupils are listed in"
    >
      <ArrowDownAZ className="h-3.5 w-3.5" />
      <span className="sr-only">Sort pupils by</span>
      <select
        className="border-0 bg-transparent p-0 text-[12px] font-semibold text-foreground outline-none focus:ring-0"
        value={value}
        onChange={(event) => onChange(event.target.value as StudentSort)}
      >
        {STUDENT_SORTS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}