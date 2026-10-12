"use client";

import { ArrowRight, Table2, TrendingUp } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import Link from "next/link";

import { WidgetCard } from "@/components/dashboard/shared";

/**
 * The two reading views of published results.
 *
 * Broadsheets existed as pages but nothing linked to them, so the only way in
 * was to know the URL. Both are the exam office's desk — the same
 * ``results.report_card`` permission the API enforces on each endpoint — so the
 * caller decides whether to render this, and the panel stays presentational.
 */
const SHEETS: {
  href: string;
  label: string;
  description: string;
  detail: string;
  icon: LucideIcon;
}[] = [
  {
    href: "/reports/broadsheet",
    label: "Class broadsheet",
    description: "Every subject side by side, for one class and term.",
    detail: "One row per student, with each subject's total and the class average.",
    icon: Table2,
  },
  {
    href: "/reports/cumulative",
    label: "Cumulative results",
    description: "A student's subject averages across a whole session.",
    detail: "Each term's total on one row, ending in the session average.",
    icon: TrendingUp,
  },
];

export function ResultSheetsPanel() {
  return (
    <WidgetCard
      title="Result sheets"
      icon={<Table2 className="h-4 w-4 text-muted-foreground/75" />}
      subtitle="Published results, one class at a time or one student across the session"
      bodyClassName="pt-3"
    >
      <div className="grid gap-3 sm:grid-cols-2">
        {SHEETS.map(({ href, label, description, detail, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className="group flex items-start gap-3.5 rounded-lg border border-border/60 px-4 py-3.5 transition-all duration-200 hover:-translate-y-[1px] hover:border-primary/35 hover:bg-accent/60"
          >
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/12 text-primary transition-colors group-hover:bg-primary/20">
              <Icon className="h-5 w-5" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="flex items-center gap-1.5 text-[13px] font-semibold tracking-tight text-foreground">
                {label}
                <ArrowRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground/60 transition-transform duration-200 group-hover:translate-x-0.5" />
              </span>
              <span className="mt-0.5 block text-[12px] leading-relaxed text-muted-foreground">
                {description}
              </span>
              <span className="mt-1 block text-[11px] leading-relaxed text-muted-foreground/75">
                {detail}
              </span>
            </span>
          </Link>
        ))}
      </div>
      <p className="mt-3 text-[11px] text-muted-foreground/75">
        Both open ready to print, and download as a spreadsheet.
      </p>
    </WidgetCard>
  );
}
