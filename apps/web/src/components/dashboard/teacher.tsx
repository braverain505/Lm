"use client";

import {
  ArrowUpRight,
  Bot,
  CalendarCheck,
  ClipboardCheck,
  Clock,
  FileText,
  GraduationCap,
  LayoutGrid,
  ListChecks,
  NotebookPen,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import { useMemo } from "react";

import { ActivityPanel } from "@/components/dashboard/widgets";
import { WidgetCard } from "@/components/dashboard/shared";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/providers/auth-provider";
import { useSessionTerm } from "@/providers/session-context";
import {
  useDashboardSummary,
  useMyAssignments,
  useReadiness,
} from "@/hooks/use-api";
import { cn } from "@/lib/utils";
import type { ReadyRow } from "@schoolos/shared";

export function TeacherDashboard() {
  const { user, activeSchool } = useAuth();
  const { term } = useSessionTerm();
  const { data: assignments = [], isLoading: assignmentsLoading } = useMyAssignments();
  const { data: summary, isLoading: summaryLoading, isError, refetch } = useDashboardSummary(term?.id ?? undefined);
  const { data: readiness = [], isLoading: readinessLoading } = useReadiness(term?.id ?? null);

  const role = activeSchool?.role?.code ?? "";
  const permissions = activeSchool?.permissions ?? [];
  const isHomeroomTeacher = role === "homeroom_teacher";
  const hasPermission = (perm: string) => permissions.includes(perm);

  const assigned = useMemo(() => new Set(assignments.map((a) => `${a.arm_id}|${a.subject_id}`)), [assignments]);

  const myRows: ReadyRow[] = useMemo(
    () => readiness.filter((r) => assigned.has(`${r.arm_id}|${r.subject_id}`)),
    [readiness, assigned],
  );

  const totals = useMemo(
    () =>
      myRows.reduce(
        (acc, r) => ({ entered: acc.entered + r.entered, submitted: acc.submitted + r.submitted, pending: acc.pending + r.pending, students: acc.students + r.student_count }),
        { entered: 0, submitted: 0, pending: 0, students: 0 },
      ),
    [myRows],
  );

  const byArm = useMemo(() => {
    const map = new Map<string, { arm_name: string; subjects: string[] }>();
    assignments.forEach((a) => {
      const cur = map.get(a.arm_id) ?? { arm_name: a.arm_name, subjects: [] };
      cur.subjects.push(a.subject_name);
      map.set(a.arm_id, cur);
    });
    return [...map.values()];
  }, [assignments]);

  const busy = summaryLoading || assignmentsLoading || readinessLoading;

  const toolShortcuts = [
    { label: "Score entry", desc: "Open a score grid", href: "/results/score", icon: ClipboardCheck, always: true },
    { label: "Attendance", desc: "Mark today's register", href: "/attendance", icon: CalendarCheck, permission: "attendance.mark" },
    { label: "Timetable", desc: "Weekly schedule", href: "/timetable", icon: LayoutGrid, permission: "timetable.view" },
    { label: "Lesson plans", desc: "Generate with AI", href: "/lesson-plans", icon: NotebookPen, permission: "results.comment" },
    { label: "Comments", desc: "Add comments for homeroom class", href: "/results", icon: FileText, permission: "results.comment", condition: isHomeroomTeacher },
  ].filter(
    (shortcut) =>
      shortcut.always ||
      (shortcut.permission && hasPermission(shortcut.permission) &&
        (!shortcut.condition || shortcut.condition))
  );

  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";

  return (
    <div className="space-y-8">
      {/* Greeting — clean, no card */}
      <div>
        <h2 className="text-[22px] font-bold tracking-tight text-foreground">
          {greeting}, {user?.full_name?.split(" ")[0] ?? "there"}.
        </h2>
        <p className="mt-1 text-[14px] text-muted-foreground">
          Here&apos;s what&apos;s happening across your classes today.
        </p>
        {term && (
          <p className="mt-1 text-[13px] font-medium text-muted-foreground/70">{term.name}</p>
        )}
      </div>

      {/* Quick actions — compact inline */}
      {toolShortcuts.length > 0 && (
        <div>
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/50">Quick actions</p>
          <div className="flex flex-wrap gap-2">
            {toolShortcuts.map((shortcut) => (
              <Link
                key={shortcut.label}
                href={shortcut.href}
                className="inline-flex items-center gap-2 rounded-lg border border-border/40 bg-card px-3 py-2 text-[12px] font-medium text-foreground/80 shadow-xs transition-all hover:border-border/60 hover:shadow-sm hover:text-foreground"
              >
                <shortcut.icon className="h-3.5 w-3.5 text-muted-foreground/50" />
                {shortcut.label}
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Key metrics — clean inline */}
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="rounded-xl border border-border/40 bg-card px-4 py-3.5 shadow-xs">
          <p className="text-[11px] font-medium text-muted-foreground/60">My subjects</p>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="text-[24px] font-bold tracking-tight">{busy ? <Skeleton className="inline-block h-6 w-10" /> : assignments.length}</span>
            <span className="text-[12px] text-muted-foreground/50">{byArm.length} class{byArm.length === 1 ? "" : "es"}</span>
          </div>
        </div>
        <div className="rounded-xl border border-border/40 bg-card px-4 py-3.5 shadow-xs">
          <p className="text-[11px] font-medium text-muted-foreground/60">Scores entered</p>
          <div className="mt-1 flex items-baseline gap-2">
            <span className={cn("text-[24px] font-bold tracking-tight", totals.entered > 0 ? "text-success" : "text-muted-foreground")}>
              {busy ? <Skeleton className="inline-block h-6 w-10" /> : `${totals.entered}/${totals.students}`}
            </span>
          </div>
          {totals.students > 0 && !busy && (
            <div className="mt-2">
              <Progress value={(totals.entered / totals.students) * 100} size="sm" className="h-1" indicatorClassName={totals.entered >= totals.students ? "bg-success" : "bg-primary"} />
            </div>
          )}
        </div>
        <div className="rounded-xl border border-border/40 bg-card px-4 py-3.5 shadow-xs">
          <p className="text-[11px] font-medium text-muted-foreground/60">Pending submissions</p>
          <div className="mt-1 flex items-baseline gap-2">
            <span className={cn("text-[24px] font-bold tracking-tight", totals.pending > 0 ? "text-warning" : "text-success")}>
              {busy ? <Skeleton className="inline-block h-6 w-10" /> : totals.pending}
            </span>
          </div>
          <p className="mt-2 text-[11px] text-muted-foreground/50">
            {totals.submitted > 0 ? `${totals.submitted} already submitted` : "Nothing submitted yet"}
          </p>
        </div>
      </div>

      {/* Main content — 2 column */}
      <div className="grid gap-6 xl:grid-cols-3">
        {/* Left — Responsibilities */}
        <div className="xl:col-span-2">
          <h3 className="mb-3 text-[14px] font-semibold tracking-tight text-foreground/90">Your responsibilities</h3>
          <div className="rounded-xl border border-border/40 bg-card shadow-xs">
            {busy ? (
              <div className="p-4 space-y-3">
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
              </div>
            ) : myRows.length === 0 ? (
              <div className="flex flex-col items-center justify-center px-6 py-10 text-center">
                <p className="text-[13px] font-medium text-foreground/60">No classes assigned yet</p>
                <p className="mt-1 text-[12px] text-muted-foreground/50">Your assigned classes and subjects will appear here.</p>
              </div>
            ) : (
              <div className="divide-y divide-border/30">
                {myRows.map((r) => {
                  const pct = r.student_count ? Math.round((r.entered / r.student_count) * 100) : 0;
                  const done = r.pending === 0 && r.student_count > 0;
                  const status = r.submitted > 0 && r.submitted >= r.student_count
                    ? { label: "Submitted", variant: "success" as const }
                    : done
                      ? { label: "Ready", variant: "info" as const }
                      : r.entered > 0
                        ? { label: "In progress", variant: "warning" as const }
                        : { label: "Not started", variant: "muted" as const };
                  return (
                    <Link
                      key={`${r.arm_id}-${r.subject_id}`}
                      href={`/results/score?arm_id=${r.arm_id}&subject_id=${r.subject_id}&term_id=${term?.id ?? ""}`}
                      className="group flex items-center gap-4 px-4 py-3 transition-colors hover:bg-muted/30"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <p className="text-[13px] font-medium text-foreground">{r.subject_name}</p>
                          <span className="text-[12px] text-muted-foreground/50">· {r.arm_name}</span>
                        </div>
                        <div className="mt-1.5 flex items-center gap-3">
                          <Progress value={pct} size="sm" className="h-1 flex-1" indicatorClassName={done ? "bg-success" : "bg-primary"} />
                          <span className="shrink-0 text-[11px] text-muted-foreground/50">
                            {r.entered}/{r.student_count}
                          </span>
                        </div>
                      </div>
                      <Badge variant={status.variant}>{status.label}</Badge>
                    </Link>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Right — My classes + AI */}
        <div className="space-y-6">
          <div>
            <h3 className="mb-3 text-[14px] font-semibold tracking-tight text-foreground/90">My classes</h3>
            <div className="rounded-xl border border-border/40 bg-card shadow-xs">
              {byArm.length === 0 ? (
                <p className="px-4 py-4 text-[13px] text-muted-foreground/60">No classes assigned yet.</p>
              ) : (
                <div className="divide-y divide-border/30">
                  {byArm.map((arm) => (
                    <div key={arm.arm_name} className="flex items-center justify-between px-4 py-3">
                      <div className="min-w-0">
                        <p className="text-[13px] font-medium text-foreground">{arm.arm_name}</p>
                        <p className="truncate text-[11px] text-muted-foreground/50">{arm.subjects.join(" · ")}</p>
                      </div>
                      <span className="flex h-6 min-w-6 items-center justify-center rounded-md bg-muted/50 px-1.5 text-[11px] font-semibold text-muted-foreground">
                        {arm.subjects.length}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {hasPermission("ai.copilot") && (
            <div>
              <h3 className="mb-3 text-[14px] font-semibold tracking-tight text-foreground/90">AI tools</h3>
              <div className="rounded-xl border border-border/40 bg-card shadow-xs divide-y divide-border/30">
                <Link href="/lesson-plans" className="group flex items-center gap-3 px-4 py-3 transition-colors hover:bg-muted/30">
                  <NotebookPen className="h-4 w-4 text-muted-foreground/40" />
                  <div className="min-w-0 flex-1">
                    <p className="text-[13px] font-medium text-foreground">Generate a lesson plan</p>
                    <p className="truncate text-[11px] text-muted-foreground/50">AI drafts objectives & procedure</p>
                  </div>
                  <ArrowUpRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground/20 group-hover:text-primary" />
                </Link>
                <Link href="/question-banks" className="group flex items-center gap-3 px-4 py-3 transition-colors hover:bg-muted/30">
                  <Sparkles className="h-4 w-4 text-muted-foreground/40" />
                  <div className="min-w-0 flex-1">
                    <p className="text-[13px] font-medium text-foreground">Create questions</p>
                    <p className="truncate text-[11px] text-muted-foreground/50">Strand questions with answers</p>
                  </div>
                  <ArrowUpRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground/20 group-hover:text-primary" />
                </Link>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Bottom — Activity */}
      <div>
        <ActivityPanel items={summary?.activity} loading={summaryLoading} error={isError} onRetry={refetch} />
      </div>
    </div>
  );
}
