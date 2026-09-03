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
  CheckCircle2,
  Clock,
  BookOpen,
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
  const { isLoading: summaryLoading } = useDashboardSummary(term?.id ?? undefined);
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
  const progressPct = totals.students > 0 ? Math.round((totals.entered / totals.students) * 100) : 0;

  const toolShortcuts = [
    { label: "Score entry", desc: "Open a score grid", href: "/results/score", icon: ClipboardCheck, always: true, color: "text-blue-600", bg: "bg-blue-50" },
    { label: "Attendance", desc: "Mark register", href: "/attendance", icon: CalendarCheck, permission: "attendance.mark", color: "text-emerald-600", bg: "bg-emerald-50" },
    { label: "Timetable", desc: "Weekly schedule", href: "/timetable", icon: LayoutGrid, permission: "timetable.view", color: "text-violet-600", bg: "bg-violet-50" },
    { label: "Lesson plans", desc: "Generate with AI", href: "/lesson-plans", icon: NotebookPen, permission: "results.comment", color: "text-amber-500", bg: "bg-amber-50" },
    { label: "Comments", desc: "Homeroom remarks", href: "/results", icon: FileText, permission: "results.comment", condition: isHomeroomTeacher, color: "text-rose-500", bg: "bg-rose-50" },
  ].filter(
    (s) => s.always || (s.permission && hasPermission(s.permission) && (!s.condition || s.condition)),
  );

  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";

  return (
    <div className="space-y-8">
      {/* ── Greeting ─────────────────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease }}
      >
        <h1 className="text-[28px] font-bold tracking-tight text-foreground">
          {greeting}, {user?.full_name?.split(" ")[0] ?? "there"} 👋
        </h1>
        <p className="mt-1.5 text-[14px] text-muted-foreground/60">
          Here&apos;s what&apos;s happening across your classes today.
        </p>
        {term && (
          <p className="mt-1 inline-flex items-center gap-1.5 rounded-full bg-primary/5 px-3 py-1 text-[12px] font-medium text-primary/70">
            <span className="h-1.5 w-1.5 rounded-full bg-primary/60" />
            {term.name}
          </p>
        )}
      </motion.div>

      {/* ── Summary Cards ────────────────────────────────────────── */}
      <div className="grid gap-4 grid-cols-1 sm:grid-cols-3">
        {/* My Subjects */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.06, ease }}
          className="rounded-2xl border border-white/60 bg-white p-5 shadow-[0_1px_3px_rgba(0,0,0,0.04)]"
        >
          <div className="flex items-start justify-between">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/50">My Subjects</p>
              <p className="mt-2 text-[26px] font-bold tracking-tight text-foreground">
                {busy ? <Skeleton className="inline-block h-7 w-16 rounded-md" /> : assignments.length}
              </p>
              <p className="mt-1 text-[11px] text-muted-foreground/45">{byArm.length} class{byArm.length === 1 ? "" : "es"}</p>
            </div>
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50 ring-1 ring-blue-100">
              <BookOpen className="h-5 w-5 text-blue-600" strokeWidth={1.75} />
            </div>
          </div>
        </motion.div>

        {/* Scores Entered */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.1, ease }}
          className="rounded-2xl border border-white/60 bg-white p-5 shadow-[0_1px_3px_rgba(0,0,0,0.04)]"
        >
          <div className="flex items-start justify-between">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/50">Scores Entered</p>
              <p className="mt-2 text-[26px] font-bold tracking-tight text-foreground">
                {busy ? <Skeleton className="inline-block h-7 w-16 rounded-md" /> : `${totals.entered}/${totals.students}`}
              </p>
              <p className="mt-1 text-[11px] text-muted-foreground/45">{progressPct}% complete</p>
            </div>
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-violet-50 ring-1 ring-violet-100">
              <ClipboardCheck className="h-5 w-5 text-violet-600" strokeWidth={1.75} />
            </div>
          </div>
          <div className="mt-3">
            <Progress value={progressPct} size="sm" className="h-1.5" indicatorClassName={progressPct >= 100 ? "bg-emerald-500" : progressPct > 0 ? "bg-violet-500" : "bg-muted-foreground/15"} />
          </div>
        </motion.div>

        {/* Pending Submissions */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.14, ease }}
          className="rounded-2xl border border-white/60 bg-white p-5 shadow-[0_1px_3px_rgba(0,0,0,0.04)]"
        >
          <div className="flex items-start justify-between">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/50">Pending</p>
              <p className="mt-2 text-[26px] font-bold tracking-tight text-foreground">
                {busy ? <Skeleton className="inline-block h-7 w-16 rounded-md" /> : totals.pending}
              </p>
              <p className="mt-1 text-[11px] text-muted-foreground/45">
                {totals.submitted > 0 ? `${totals.submitted} submitted` : "Ready to enter"}
              </p>
            </div>
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-50 ring-1 ring-amber-100">
              <Clock className="h-5 w-5 text-amber-500" strokeWidth={1.75} />
            </div>
          </div>
        </motion.div>
      </div>

      {/* ── Quick Actions ────────────────────────────────────────── */}
      {toolShortcuts.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.18, ease }}
          className="rounded-2xl border border-white/60 bg-white p-6 shadow-[0_1px_3px_rgba(0,0,0,0.04)]"
        >
          <h3 className="text-[14px] font-semibold tracking-tight text-foreground">Quick Actions</h3>
          <p className="mt-0.5 text-[12px] text-muted-foreground/50">Frequently used tools</p>
          <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            {toolShortcuts.map((shortcut, idx) => {
              const Icon = shortcut.icon;
              return (
                <motion.div
                  key={shortcut.label}
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ duration: 0.3, delay: 0.22 + idx * 0.03, ease }}
                >
                  <Link
                    href={shortcut.href}
                    className="group flex flex-col items-center gap-2.5 rounded-xl p-3 transition-all duration-200 hover:bg-muted/30"
                  >
                    <div className={cn("flex h-12 w-12 items-center justify-center rounded-xl transition-transform duration-200 group-hover:scale-110", shortcut.bg)}>
                      <Icon className={cn("h-5 w-5", shortcut.color)} strokeWidth={1.75} />
                    </div>
                    <span className="text-[11px] font-medium text-foreground/70 text-center leading-tight">{shortcut.label}</span>
                  </Link>
                </motion.div>
              );
            })}
          </div>
        </motion.div>
      )}

      {/* ── Main Content: Responsibilities + Classes ─────────────── */}
      <div className="grid gap-5 lg:grid-cols-3">
        {/* Responsibilities */}
        <div className="lg:col-span-2">
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.26, ease }}
            className="rounded-2xl border border-white/60 bg-white shadow-[0_1px_3px_rgba(0,0,0,0.04)] overflow-hidden"
          >
            <div className="border-b border-border/20 px-5 py-4">
              <h3 className="text-[14px] font-semibold tracking-tight text-foreground">Your Responsibilities</h3>
              <p className="mt-0.5 text-[12px] text-muted-foreground/50">Score entry progress by subject</p>
            </div>
            {busy ? (
              <div className="p-5 space-y-3">
                <Skeleton className="h-16 w-full rounded-lg" />
                <Skeleton className="h-16 w-full rounded-lg" />
                <Skeleton className="h-16 w-full rounded-lg" />
              </div>
            ) : myRows.length === 0 ? (
              <div className="flex flex-col items-center justify-center px-5 py-12 text-center">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-muted/30">
                  <GraduationCap className="h-5 w-5 text-muted-foreground/25" />
                </div>
                <p className="mt-3 text-[13px] font-medium text-foreground/50">No classes assigned yet</p>
                <p className="mt-1 text-[11px] text-muted-foreground/40">Your assigned classes will appear here.</p>
              </div>
            ) : (
              <div className="divide-y divide-border/15">
                {myRows.map((r) => {
                  const pct = r.student_count ? Math.round((r.entered / r.student_count) * 100) : 0;
                  const done = r.pending === 0 && r.student_count > 0;
                  const status = r.submitted > 0 && r.submitted >= r.student_count
                    ? { label: "Submitted", variant: "success" as const, dot: "bg-emerald-500" }
                    : done
                      ? { label: "Ready", variant: "info" as const, dot: "bg-blue-500" }
                      : r.entered > 0
                        ? { label: "In progress", variant: "warning" as const, dot: "bg-amber-500" }
                        : { label: "Not started", variant: "muted" as const, dot: "bg-muted-foreground/20" };
                  return (
                    <Link
                      key={`${r.arm_id}-${r.subject_id}`}
                      href={`/results/score?arm_id=${r.arm_id}&subject_id=${r.subject_id}&term_id=${term?.id ?? ""}`}
                      className="group flex items-center gap-4 px-5 py-3.5 transition-colors duration-150 hover:bg-muted/15"
                    >
                      <div className={cn("h-2 w-2 shrink-0 rounded-full", status.dot)} />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <p className="text-[13px] font-medium text-foreground/80 truncate">{r.subject_name}</p>
                          <span className="text-[11px] text-muted-foreground/35">·</span>
                          <p className="text-[11px] text-muted-foreground/45 truncate">{r.arm_name}</p>
                        </div>
                        <div className="mt-1.5 flex items-center gap-3">
                          <Progress value={pct} size="sm" className="h-1 flex-1" indicatorClassName={done ? "bg-emerald-500" : pct > 0 ? "bg-blue-500" : "bg-muted-foreground/15"} />
                          <span className="text-[10px] font-medium text-muted-foreground/45 shrink-0">{pct}%</span>
                        </div>
                      </div>
                      <Badge variant={status.variant} className="shrink-0 text-[10px]">{status.label}</Badge>
                    </Link>
                  );
                })}
              </div>
            )}
          </motion.div>
        </div>

        {/* My Classes + AI */}
        <div className="space-y-5">
          {/* My Classes */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.3, ease }}
            className="rounded-2xl border border-white/60 bg-white shadow-[0_1px_3px_rgba(0,0,0,0.04)] overflow-hidden"
          >
            <div className="border-b border-border/20 px-5 py-4">
              <h3 className="text-[14px] font-semibold tracking-tight text-foreground">My Classes</h3>
            </div>
            {byArm.length === 0 ? (
              <p className="px-5 py-5 text-[12px] text-muted-foreground/45">No classes assigned yet.</p>
            ) : (
              <div className="divide-y divide-border/15">
                {byArm.map((arm) => (
                  <div key={arm.arm_name} className="flex items-center justify-between px-5 py-3 transition-colors duration-150 hover:bg-muted/15">
                    <div className="min-w-0">
                      <p className="text-[13px] font-medium text-foreground/80">{arm.arm_name}</p>
                      <p className="truncate text-[10px] text-muted-foreground/40">{arm.subjects.join(" · ")}</p>
                    </div>
                    <span className="flex h-6 min-w-6 items-center justify-center rounded-lg bg-muted/30 px-1.5 text-[10px] font-semibold text-muted-foreground/50">
                      {arm.subjects.length}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </motion.div>

          {/* AI Tools */}
          {hasPermission("ai.copilot") && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.34, ease }}
              className="rounded-2xl border border-white/60 bg-white shadow-[0_1px_3px_rgba(0,0,0,0.04)] overflow-hidden"
            >
              <div className="border-b border-border/20 px-5 py-4">
                <div className="flex items-center gap-2">
                  <h3 className="text-[14px] font-semibold tracking-tight text-foreground">AI Tools</h3>
                  <span className="inline-flex items-center gap-1 rounded-full bg-gradient-to-r from-violet-500 to-primary px-2 py-0.5 text-[9px] font-bold text-white uppercase tracking-wider">
                    <Sparkles className="h-2.5 w-2.5" /> AI
                  </span>
                </div>
              </div>
              <div className="divide-y divide-border/15">
                <Link href="/lesson-plans" className="group flex items-center gap-3 px-5 py-3.5 transition-colors duration-150 hover:bg-muted/15">
                  <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-amber-50 transition-colors duration-200 group-hover:bg-amber-100">
                    <NotebookPen className="h-4 w-4 text-amber-500" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-[12px] font-medium text-foreground/80">Generate a lesson plan</p>
                    <p className="text-[10px] text-muted-foreground/40">AI drafts objectives & procedure</p>
                  </div>
                  <ArrowUpRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground/20 transition-colors duration-200 group-hover:text-primary/60" />
                </Link>
                <Link href="/question-banks" className="group flex items-center gap-3 px-5 py-3.5 transition-colors duration-150 hover:bg-muted/15">
                  <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-violet-50 transition-colors duration-200 group-hover:bg-violet-100">
                    <Sparkles className="h-4 w-4 text-violet-600" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-[12px] font-medium text-foreground/80">Create questions</p>
                    <p className="text-[10px] text-muted-foreground/40">Strand questions with answers</p>
                  </div>
                  <ArrowUpRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground/20 transition-colors duration-200 group-hover:text-primary/60" />
                </Link>
              </div>
            </motion.div>
          )}
        </div>
      </div>
    </div>
  );
}
