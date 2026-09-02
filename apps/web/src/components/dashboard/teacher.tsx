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
import { motion } from "framer-motion";
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

const ease = [0.25, 0.46, 0.45, 0.94] as const;

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
      {/* Greeting */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease }}
      >
        <h2 className="text-[26px] font-bold tracking-tight text-foreground">
          {greeting}, {user?.full_name?.split(" ")[0] ?? "there"}.
        </h2>
        <p className="mt-1.5 text-[14px] text-muted-foreground/70">
          Here&apos;s what&apos;s happening across your classes today.
        </p>
        {term && (
          <p className="mt-1 text-[13px] font-medium text-muted-foreground/50">{term.name}</p>
        )}
      </motion.div>

      {/* Quick actions */}
      {toolShortcuts.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.06, ease }}
        >
          <p className="mb-2.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/50">Quick actions</p>
          <div className="flex flex-wrap gap-2">
            {toolShortcuts.map((shortcut) => (
              <Link
                key={shortcut.label}
                href={shortcut.href}
                className="group inline-flex items-center gap-2 rounded-lg border border-border/40 bg-card px-3.5 py-2 text-[12px] font-medium text-foreground/80 shadow-xs transition-all duration-200 hover:border-border/60 hover:shadow-card hover:text-foreground hover:-translate-y-[1px]"
              >
                <shortcut.icon className="h-3.5 w-3.5 text-muted-foreground/40 transition-colors duration-200 group-hover:text-primary/60" />
                {shortcut.label}
              </Link>
            ))}
          </div>
        </motion.div>
      )}

      {/* Key metrics */}
      <div className="grid gap-4 sm:grid-cols-3">
        <motion.div
          className="rounded-xl border border-border/40 bg-card px-5 py-4 shadow-xs transition-[border-color,box-shadow] duration-200 hover:border-border/60 hover:shadow-card"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.08, ease }}
        >
          <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground/50">My subjects</p>
          <div className="mt-1.5 flex items-baseline gap-2">
            <span className="text-[24px] font-bold tracking-tight">{busy ? <Skeleton className="inline-block h-7 w-10 rounded-md" /> : assignments.length}</span>
            <span className="text-[12px] text-muted-foreground/50">{byArm.length} class{byArm.length === 1 ? "" : "es"}</span>
          </div>
        </motion.div>
        <motion.div
          className="rounded-xl border border-border/40 bg-card px-5 py-4 shadow-xs transition-[border-color,box-shadow] duration-200 hover:border-border/60 hover:shadow-card"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.12, ease }}
        >
          <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground/50">Scores entered</p>
          <div className="mt-1.5 flex items-baseline gap-2">
            <span className={cn("text-[24px] font-bold tracking-tight", totals.entered > 0 ? "text-success" : "text-muted-foreground")}>
              {busy ? <Skeleton className="inline-block h-7 w-10 rounded-md" /> : `${totals.entered}/${totals.students}`}
            </span>
          </div>
          {totals.students > 0 && !busy && (
            <div className="mt-2.5">
              <Progress value={(totals.entered / totals.students) * 100} size="sm" className="h-1" indicatorClassName={totals.entered >= totals.students ? "bg-success" : "bg-primary"} />
            </div>
          )}
        </motion.div>
        <motion.div
          className="rounded-xl border border-border/40 bg-card px-5 py-4 shadow-xs transition-[border-color,box-shadow] duration-200 hover:border-border/60 hover:shadow-card"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.16, ease }}
        >
          <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground/50">Pending submissions</p>
          <div className="mt-1.5 flex items-baseline gap-2">
            <span className={cn("text-[24px] font-bold tracking-tight", totals.pending > 0 ? "text-warning" : "text-success")}>
              {busy ? <Skeleton className="inline-block h-7 w-10 rounded-md" /> : totals.pending}
            </span>
          </div>
          <p className="mt-2.5 text-[11px] text-muted-foreground/45">
            {totals.submitted > 0 ? `${totals.submitted} already submitted` : "Nothing submitted yet"}
          </p>
        </motion.div>
      </div>

      {/* Main content — 2 column */}
      <div className="grid gap-6 xl:grid-cols-3">
        {/* Left — Responsibilities */}
        <div className="xl:col-span-2">
          <h3 className="mb-3 text-[14px] font-semibold tracking-tight text-foreground/90">Your responsibilities</h3>
          <div className="rounded-xl border border-border/40 bg-card shadow-xs transition-[border-color,box-shadow] duration-200 hover:border-border/60 hover:shadow-card">
            {busy ? (
              <div className="p-5 space-y-3">
                <Skeleton className="h-12 w-full rounded-lg" />
                <Skeleton className="h-12 w-full rounded-lg" />
                <Skeleton className="h-12 w-full rounded-lg" />
              </div>
            ) : myRows.length === 0 ? (
              <div className="flex flex-col items-center justify-center px-6 py-12 text-center">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-muted/40">
                  <GraduationCap className="h-5 w-5 text-muted-foreground/30" />
                </div>
                <p className="mt-3 text-[13px] font-medium text-foreground/60">No classes assigned yet</p>
                <p className="mt-1.5 text-[12px] text-muted-foreground/50">Your assigned classes and subjects will appear here.</p>
              </div>
            ) : (
              <div className="divide-y divide-border/20">
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
                      className="group flex items-center gap-4 px-5 py-3.5 transition-colors duration-200 hover:bg-muted/20"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <p className="text-[13px] font-medium text-foreground">{r.subject_name}</p>
                          <span className="text-[12px] text-muted-foreground/40">· {r.arm_name}</span>
                        </div>
                        <div className="mt-2 flex items-center gap-3">
                          <Progress value={pct} size="sm" className="h-1 flex-1" indicatorClassName={done ? "bg-success" : "bg-primary"} />
                          <span className="shrink-0 text-[11px] text-muted-foreground/45">
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
            <div className="rounded-xl border border-border/40 bg-card shadow-xs transition-[border-color,box-shadow] duration-200 hover:border-border/60 hover:shadow-card">
              {byArm.length === 0 ? (
                <p className="px-5 py-5 text-[13px] text-muted-foreground/60">No classes assigned yet.</p>
              ) : (
                <div className="divide-y divide-border/20">
                  {byArm.map((arm) => (
                    <div key={arm.arm_name} className="flex items-center justify-between px-5 py-3.5">
                      <div className="min-w-0">
                        <p className="text-[13px] font-medium text-foreground">{arm.arm_name}</p>
                        <p className="truncate text-[11px] text-muted-foreground/45">{arm.subjects.join(" · ")}</p>
                      </div>
                      <span className="flex h-6 min-w-6 items-center justify-center rounded-lg bg-muted/40 px-1.5 text-[11px] font-semibold text-muted-foreground/60">
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
              <div className="rounded-xl border border-border/40 bg-card shadow-xs divide-y divide-border/20 transition-[border-color,box-shadow] duration-200 hover:border-border/60 hover:shadow-card">
                <Link href="/lesson-plans" className="group flex items-center gap-3 px-5 py-3.5 transition-colors duration-200 hover:bg-muted/20">
                  <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-muted/40 transition-colors duration-200 group-hover:bg-primary/10">
                    <NotebookPen className="h-4 w-4 text-muted-foreground/40 transition-colors duration-200 group-hover:text-primary/70" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-[13px] font-medium text-foreground">Generate a lesson plan</p>
                    <p className="truncate text-[11px] text-muted-foreground/45">AI drafts objectives & procedure</p>
                  </div>
                  <ArrowUpRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground/20 transition-colors duration-200 group-hover:text-primary/60" />
                </Link>
                <Link href="/question-banks" className="group flex items-center gap-3 px-5 py-3.5 transition-colors duration-200 hover:bg-muted/20">
                  <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-muted/40 transition-colors duration-200 group-hover:bg-primary/10">
                    <Sparkles className="h-4 w-4 text-muted-foreground/40 transition-colors duration-200 group-hover:text-primary/70" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-[13px] font-medium text-foreground">Create questions</p>
                    <p className="truncate text-[11px] text-muted-foreground/45">Strand questions with answers</p>
                  </div>
                  <ArrowUpRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground/20 transition-colors duration-200 group-hover:text-primary/60" />
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
