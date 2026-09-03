"use client";

import {
  ArrowUpRight,
  CalendarCheck,
  ClipboardCheck,
  FileText,
  GraduationCap,
  LayoutGrid,
  NotebookPen,
  Sparkles,
} from "lucide-react";
import { motion } from "framer-motion";
import Link from "next/link";
import { useMemo } from "react";

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
  useDashboardSummary(term?.id ?? undefined);
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

  const busy = assignmentsLoading || readinessLoading;

  const toolShortcuts = [
    { label: "Score entry", desc: "Open a score grid", href: "/results/score", icon: ClipboardCheck, always: true, bgColor: "bg-blue-50", iconColor: "text-blue-600", hoverBg: "hover:bg-blue-100" },
    { label: "Attendance", desc: "Mark today's register", href: "/attendance", icon: CalendarCheck, permission: "attendance.mark", bgColor: "bg-emerald-50", iconColor: "text-emerald-600", hoverBg: "hover:bg-emerald-100" },
    { label: "Timetable", desc: "Weekly schedule", href: "/timetable", icon: LayoutGrid, permission: "timetable.view", bgColor: "bg-purple-50", iconColor: "text-purple-600", hoverBg: "hover:bg-purple-100" },
    { label: "Lesson plans", desc: "Generate with AI", href: "/lesson-plans", icon: NotebookPen, permission: "results.comment", bgColor: "bg-amber-50", iconColor: "text-amber-600", hoverBg: "hover:bg-amber-100" },
    { label: "Comments", desc: "Add comments for homeroom class", href: "/results", icon: FileText, permission: "results.comment", condition: isHomeroomTeacher, bgColor: "bg-rose-50", iconColor: "text-rose-600", hoverBg: "hover:bg-rose-100" },
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
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.06, ease }}
          className="rounded-2xl border border-border/60 bg-card p-6 shadow-xs hover:shadow-card transition-all duration-200"
        >
          <h3 className="text-[14px] font-semibold tracking-tight text-foreground">Quick actions</h3>
          <p className="mt-1 text-[12px] text-muted-foreground/60">Frequently used tools</p>

          <div className="mt-6 grid gap-6 grid-cols-2 sm:grid-cols-3 md:grid-cols-3 lg:grid-cols-5">
            {toolShortcuts.map((shortcut, idx) => (
              <Link
                key={shortcut.label}
                href={shortcut.href}
                className="group flex flex-col items-center gap-3 transition-all duration-200"
              >
                <div className={cn("flex items-center justify-center h-16 w-16 rounded-2xl transition-colors duration-200", shortcut.bgColor, shortcut.hoverBg)}>
                  <shortcut.icon className={cn("h-8 w-8 transition-colors duration-200", shortcut.iconColor)} strokeWidth={1.5} />
                </div>
                <p className="text-[12px] font-medium text-foreground text-center">{shortcut.label}</p>
              </Link>
            ))}
          </div>
        </motion.div>
      )}

      {/* Main content — 2 column */}
      <div className="grid gap-6 md:grid-cols-1 lg:grid-cols-1 xl:grid-cols-3">
        {/* Left — Responsibilities */}
        <div className="xl:col-span-2">
          <h3 className="mb-3 text-[14px] font-semibold tracking-tight text-foreground">Your responsibilities</h3>
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.24, ease }}
            className="rounded-2xl border border-border/60 bg-card shadow-xs hover:shadow-card transition-all duration-200 overflow-hidden"
          >
            {busy ? (
              <div className="p-6 space-y-3">
                <Skeleton className="h-16 w-full rounded-lg" />
                <Skeleton className="h-16 w-full rounded-lg" />
                <Skeleton className="h-16 w-full rounded-lg" />
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
              <div className="space-y-2 p-6">
                {myRows.map((r) => {
                  const pct = r.student_count ? Math.round((r.entered / r.student_count) * 100) : 0;
                  const done = r.pending === 0 && r.student_count > 0;
                  const status = r.submitted > 0 && r.submitted >= r.student_count
                    ? { label: "Submitted", variant: "success" as const, bgColor: "bg-success/10", borderColor: "border-success/30" }
                    : done
                      ? { label: "Ready", variant: "info" as const, bgColor: "bg-info/10", borderColor: "border-info/30" }
                      : r.entered > 0
                        ? { label: "In progress", variant: "warning" as const, bgColor: "bg-warning/10", borderColor: "border-warning/30" }
                        : { label: "Not started", variant: "muted" as const, bgColor: "bg-muted/20", borderColor: "border-border/40" };
                  return (
                    <Link
                      key={`${r.arm_id}-${r.subject_id}`}
                      href={`/results/score?arm_id=${r.arm_id}&subject_id=${r.subject_id}&term_id=${term?.id ?? ""}`}
                      className={cn("group flex flex-col gap-3 rounded-lg border p-4 transition-all duration-200", status.bgColor, status.borderColor, "hover:shadow-md hover:-translate-y-0.5")}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <p className="text-[13px] font-semibold text-foreground">{r.subject_name}</p>
                          <p className="text-[12px] text-muted-foreground/60">{r.arm_name}</p>
                        </div>
                        <Badge variant={status.variant} className="shrink-0">{status.label}</Badge>
                      </div>
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-[11px] font-medium text-muted-foreground">Progress</span>
                          <span className="text-[11px] font-semibold text-foreground">{pct}% ({r.entered}/{r.student_count})</span>
                        </div>
                        <Progress value={pct} size="sm" className="h-2" indicatorClassName={done ? "bg-success" : pct > 0 ? "bg-primary" : "bg-muted-foreground/20"} />
                      </div>
                    </Link>
                  );
                })}
              </div>
            )}
          </motion.div>
        </div>

        {/* Right — My classes + AI */}
        <div className="space-y-6">
          <div>
            <h3 className="mb-3 text-[14px] font-semibold tracking-tight text-foreground">My classes</h3>
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.28, ease }}
              className="rounded-2xl border border-border/60 bg-card shadow-xs hover:shadow-card transition-all duration-200"
            >
              {byArm.length === 0 ? (
                <p className="px-6 py-6 text-[13px] text-muted-foreground/60">No classes assigned yet.</p>
              ) : (
                <div className="divide-y divide-border/20">
                  {byArm.map((arm) => (
                    <div key={arm.arm_name} className="flex items-center justify-between px-6 py-3.5 hover:bg-muted/20 transition-colors duration-200">
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
            </motion.div>
          </div>

          {hasPermission("ai.copilot") && (
            <div>
              <h3 className="mb-3 text-[14px] font-semibold tracking-tight text-foreground">AI tools</h3>
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: 0.32, ease }}
                className="rounded-2xl border border-border/60 bg-card shadow-xs hover:shadow-card divide-y divide-border/20 transition-all duration-200"
              >
                <Link href="/lesson-plans" className="group flex items-center gap-3 px-6 py-3.5 transition-colors duration-200 hover:bg-muted/20">
                  <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-muted/40 transition-colors duration-200 group-hover:bg-primary/10">
                    <NotebookPen className="h-4 w-4 text-muted-foreground/40 transition-colors duration-200 group-hover:text-primary/70" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-[13px] font-medium text-foreground">Generate a lesson plan</p>
                    <p className="truncate text-[11px] text-muted-foreground/45">AI drafts objectives & procedure</p>
                  </div>
                  <ArrowUpRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground/20 transition-colors duration-200 group-hover:text-primary/60" />
                </Link>
                <Link href="/question-banks" className="group flex items-center gap-3 px-6 py-3.5 transition-colors duration-200 hover:bg-muted/20">
                  <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-muted/40 transition-colors duration-200 group-hover:bg-primary/10">
                    <Sparkles className="h-4 w-4 text-muted-foreground/40 transition-colors duration-200 group-hover:text-primary/70" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-[13px] font-medium text-foreground">Create questions</p>
                    <p className="truncate text-[11px] text-muted-foreground/45">Strand questions with answers</p>
                  </div>
                  <ArrowUpRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground/20 transition-colors duration-200 group-hover:text-primary/60" />
                </Link>
              </motion.div>
            </div>
          )}
        </div>
      </div>


    </div>
  );
}
