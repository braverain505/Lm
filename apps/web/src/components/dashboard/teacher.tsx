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

  // Filter the readiness matrix to only the teacher's own assignments — the
  // backend scopes every query to the school; this surfaces only their work.
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

  // Build tool shortcuts based on permissions
  const toolShortcuts = [
    { label: "Score entry", desc: "Open a score grid", href: "/results/score", icon: ClipboardCheck, tone: "bg-primary/10 text-primary", always: true },
    { label: "Attendance", desc: "Mark today's register", href: "/attendance", icon: CalendarCheck, tone: "bg-emerald-500/10 text-emerald-700", permission: "attendance.mark" },
    { label: "Timetable", desc: "Weekly schedule", href: "/timetable", icon: LayoutGrid, tone: "bg-amber-500/14 text-amber-700", permission: "timetable.view" },
    { label: "Lesson plans", desc: "Generate with AI", href: "/lesson-plans", icon: NotebookPen, tone: "bg-rose-500/10 text-rose-700", permission: "results.comment" },
    { label: "Comment functionality", desc: "Add comments for homeroom class", href: "/results", icon: FileText, tone: "bg-teal-500/10 text-teal-700", permission: "results.comment", condition: isHomeroomTeacher },
  ].filter(
    (shortcut) =>
      shortcut.always ||
      (shortcut.permission && hasPermission(shortcut.permission) &&
        (!shortcut.condition || shortcut.condition))
  );

  return (
    <div className="space-y-6">
      {/* Greeting */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight sm:text-2xl">
            {new Date().getHours() < 12 ? "Good morning" : new Date().getHours() < 17 ? "Good afternoon" : "Good evening"},{" "}
            {user?.full_name?.split(" ")[0] ?? "there"}
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">Here&apos;s what you need to do today.</p>
        </div>
        {term && (
          <Badge variant="outline" className="text-[13px]">
            {term.name}
          </Badge>
        )}
      </div>

      {/* Tool shortcuts */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {toolShortcuts.map((shortcut) => (
          <Link key={shortcut.label} href={shortcut.href} className="stat-card group flex items-center gap-3">
            <span className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-[10px]", shortcut.tone)}>
              <shortcut.icon className="h-5 w-5" />
            </span>
            <span className="min-w-0">
              <span className="block text-[14px] font-semibold leading-tight">{shortcut.label}</span>
              <span className="block truncate text-xs text-muted-foreground">{shortcut.desc}</span>
            </span>
            <ArrowUpRight className="ml-auto h-4 w-4 shrink-0 text-muted-foreground/30 transition-colors group-hover:text-primary" />
          </Link>
        ))}
      </div>

      {/* Overview strip */}
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="stat-card">
          <p className="text-[13px] text-muted-foreground">My subjects</p>
          <p className="mt-1 text-2xl font-bold tracking-tight">{assignments.length}</p>
          <p className="mt-1 text-xs text-muted-foreground">{byArm.length} class{byArm.length === 1 ? "" : "es"}</p>
        </div>
        <div className="stat-card">
          <p className="text-[13px] text-muted-foreground">Scores entered</p>
          <p className={cn("mt-1 text-2xl font-bold tracking-tight", totals.entered > 0 ? "text-success" : "text-muted-foreground")}>
            {busy ? <Skeleton className="h-7 w-10" /> : `${totals.entered}/${totals.students}`}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            {totals.students} students
          </p>
        </div>
        <div className="stat-card">
          <p className="text-[13px] text-muted-foreground">Pending submissions</p>
          <p className={cn("mt-1 text-2xl font-bold tracking-tight", totals.pending > 0 ? "text-warning" : "text-success")}>
            {busy ? <Skeleton className="h-7 w-10" /> : totals.pending}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            {totals.submitted > 0 ? `${totals.submitted} already submitted` : "Nothing submitted yet"}
          </p>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        {/* My responsibilities */}
        <WidgetCard
          title="My responsibilities"
          icon={<ListChecks className="h-4 w-4 text-primary" />}
          subtitle="Score entry status for your classes"
          loading={busy}
          error={isError}
          onRetry={refetch}
          empty={!busy && myRows.length === 0}
          emptyHint="Your assigned classes and subjects will appear here."
          className="xl:col-span-2"
          bodyClassName="pt-4"
        >
          <ul className="space-y-2.5">
            {myRows.map((r) => {
              const pct = r.student_count ? Math.round((r.entered / r.student_count) * 100) : 0;
              const done = r.pending === 0 && r.student_count > 0;
              const status = r.submitted > 0 && r.submitted >= r.student_count
                ? { label: "Submitted", tone: "success" as const }
                : done
                  ? { label: "Ready to submit", tone: "info" as const }
                  : r.entered > 0
                    ? { label: "In progress", tone: "warning" as const }
                    : { label: "Not started", tone: "muted" as const };
              return (
                <li key={`${r.arm_id}-${r.subject_id}`}>
                  <Link
                    href={`/results/score?arm_id=${r.arm_id}&subject_id=${r.subject_id}&term_id=${term?.id ?? ""}`}
                    className="group block rounded-xl border p-4 transition-all hover:border-primary/25 hover:bg-accent/40"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-[13px] font-semibold">
                        {r.subject_name}
                        <span className="font-normal text-muted-foreground"> — {r.arm_name}</span>
                      </p>
                      <Badge variant={status.tone}>{status.label}</Badge>
                    </div>
                    <div className="mt-2.5 flex items-center gap-3">
                      <Progress
                        value={pct}
                        size="sm"
                        className="flex-1"
                        indicatorClassName={done ? "bg-success" : "bg-primary"}
                      />
                      <span className="shrink-0 text-[11px] font-medium text-muted-foreground">
                        {r.entered}/{r.student_count} entered
                      </span>
                    </div>
                    <p className="mt-2 text-[11px] text-muted-foreground">
                      {r.pending > 0 ? `${r.pending} students still need scores` : `${r.submitted} submitted for review`}
                    </p>
                  </Link>
                </li>
              );
            })}
          </ul>
        </WidgetCard>

        {/* Right column: AI + my classes */}
        <div className="space-y-4">
          {/* AI teaching tools - show only if user has AI copilot permission or lesson plans permission */}
          {hasPermission("ai.copilot") && (
            <WidgetCard
              title={
                <span className="flex items-center gap-2">
                  Lumo AI <Bot className="h-4 w-4 text-violet-500" />
                </span>
              }
              icon={null}
              subtitle="Your AI teaching tools"
              bodyClassName="pt-4"
            >
              <div className="space-y-2">
                <Link href="/lesson-plans" className="group flex items-center gap-3 rounded-xl border px-3.5 py-3 transition-all hover:border-primary/25 hover:bg-accent/50">
                  <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-500/10 text-violet-600 dark:text-violet-300">
                    <NotebookPen className="h-4 w-4" />
                  </span>
                  <div className="min-w-0">
                    <p className="text-[13px] font-semibold">Generate a lesson plan</p>
                    <p className="truncate text-[11px] text-muted-foreground">AI drafts objectives, procedure & homework</p>
                  </div>
                </Link>
                <Link href="/question-banks" className="group flex items-center gap-3 rounded-xl border px-3.5 py-3 transition-all hover:border-primary/25 hover:bg-accent/50">
                  <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-fuchsia-500/10 text-fuchsia-600 dark:text-fuchsia-300">
                    <Sparkles className="h-4 w-4" />
                  </span>
                  <div className="min-w-0">
                    <p className="text-[13px] font-semibold">Create questions</p>
                    <p className="truncate text-[11px] text-muted-foreground">Strand questions with answers & rationale</p>
                  </div>
                </Link>
              </div>
            </WidgetCard>
          )}

          <WidgetCard
            title="My classes"
            icon={<GraduationCap className="h-4 w-4 text-primary" />}
            subtitle="Classes you teach this session"
            loading={assignmentsLoading}
            bodyClassName="pt-4"
          >
            {byArm.length === 0 ? (
              <p className="text-sm text-muted-foreground">No classes assigned yet.</p>
            ) : (
              <ul className="space-y-2">
                {byArm.map((arm) => (
                  <li key={arm.arm_name} className="flex items-center justify-between rounded-lg border px-3.5 py-3">
                    <div className="min-w-0">
                      <p className="text-[13px] font-semibold">{arm.arm_name}</p>
                      <p className="truncate text-xs text-muted-foreground">{arm.subjects.join(" · ")}</p>
                    </div>
                    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">
                      {arm.subjects.length}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </WidgetCard>
        </div>
      </div>

      {/* Recent activity + today's attendance + Quick entry */}
      <div className="grid gap-4 xl:grid-cols-3">
        <ActivityPanel items={summary?.activity} loading={summaryLoading} error={isError} onRetry={refetch} />
        <WidgetCard
          title="Today's attendance"
          icon={<CalendarCheck className="h-4 w-4 text-primary" />}
          subtitle="School-wide register today"
          loading={summaryLoading}
          error={isError}
          onRetry={refetch}
          bodyClassName="pt-4"
        >
          {summary?.attendance?.today?.total ? (
            <div className="grid grid-cols-3 gap-3">
              {[
                { label: "Present", value: summary.attendance.today.present, color: "text-success" },
                { label: "Absent", value: summary.attendance.today.absent, color: "text-destructive" },
                { label: "Late", value: summary.attendance.today.late, color: "text-warning" },
              ].map((s) => (
                <div key={s.label} className="rounded-xl border bg-muted/30 p-4 text-center">
                  <p className={cn("text-2xl font-bold tracking-tight", s.color)}>{s.value}</p>
                  <p className="mt-1 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">{s.label}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="flex items-center gap-2 text-sm text-muted-foreground">
              <Clock className="h-4 w-4" /> No attendance recorded today yet.
            </p>
          )}
        </WidgetCard>
        {/* Quick entry - show only if user has permission to enter scores */}
        {hasPermission("results.enter") && (
          <WidgetCard
            title="Quick entry"
            icon={<ClipboardCheck className="h-4 w-4 text-primary" />}
            subtitle="Open a score grid"
            loading={assignmentsLoading}
            bodyClassName="pt-4"
          >
            {assignments.length === 0 ? (
              <p className="text-sm text-muted-foreground">No assignments yet.</p>
            ) : (
              <ul className="space-y-1">
                {assignments.map((a) => (
                  <li key={a.assignment_id}>
                    <Link
                      href={`/results/score?arm_id=${a.arm_id}&subject_id=${a.subject_id}&term_id=${term?.id ?? ""}`}
                      className="group flex items-center justify-between rounded-lg px-3 py-2.5 text-[13px] transition-colors hover:bg-accent"
                    >
                      <span className="truncate">
                        <span className="font-medium">{a.arm_name}</span>
                        <span className="text-muted-foreground"> · {a.subject_name}</span>
                      </span>
                      <ArrowUpRight className="h-4 w-4 shrink-0 text-muted-foreground/40 group-hover:text-primary" />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </WidgetCard>
        )}
      </div>
    </div>
  );
}