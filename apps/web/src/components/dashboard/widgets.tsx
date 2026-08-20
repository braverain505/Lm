"use client";

import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Bot,
  CalendarCheck,
  Check,
  CheckCircle2,
  ClipboardCheck,
  Clock,
  FileText,
  GraduationCap,
  LayoutGrid,
  Lightbulb,
  ListChecks,
  NotebookPen,
  Sparkles,
  TrendingUp,
  UserPlus,
  Users,
  Wallet,
} from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import {
  AttendanceBars,
  ClassPerformanceBar,
  DistributionDonut,
  PerformanceChart,
} from "@/components/dashboard-charts";
import {
  KpiCard,
  ReadinessRing,
  WidgetCard,
  relativeTime,
} from "@/components/dashboard/shared";
import { ReadinessBar } from "@/components/readiness-bar";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/providers/auth-provider";
import { useReadiness, useWorkbench } from "@/hooks/use-api";
import { cn } from "@/lib/utils";
import type {
  ActivityItem,
  AttendanceOverview,
  DashboardSummary,
  InsightItem,
  ReadyRow,
  TaskItem,
  WorkbenchRow,
} from "@schoolos/shared";

// ---------------------------------------------------------------------------
// Segmented control
// ---------------------------------------------------------------------------
function Segmented<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
}) {
  return (
    <div className="flex items-center gap-0.5 rounded-lg border bg-muted/50 p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={cn(
            "rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
            value === o.value ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// KPI row
// ---------------------------------------------------------------------------
export function KpiRow({ data, loading, accountant }: { data?: DashboardSummary; loading: boolean; accountant?: boolean }) {
  const k = data?.kpis;
  const attendance = data?.attendance;
  const attDelta =
    attendance && attendance.today.rate != null && attendance.week.rate != null
      ? attendance.today.rate - attendance.week.rate
      : null;
  const feeCount = data?.tasks?.find((t) => t.kind === "finance")?.count;

  const cards = accountant
    ? [
        {
          label: "Outstanding fees",
          value: `${k?.fee_currency ?? "NGN"} ${(k?.outstanding_fees ?? 0).toLocaleString()}`,
          icon: Wallet,
          sub: feeCount != null ? `${feeCount} students with balances` : "No balances yet",
          href: "/billing",
          iconClass: "bg-indigo-500/10 text-indigo-600 dark:text-indigo-300",
        },
        {
          label: "Students",
          value: k?.students ?? 0,
          icon: Users,
          sub: `${data?.distribution?.total ?? 0} enrolled`,
          href: "/students",
          iconClass: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
        },
        {
          label: "Classes",
          value: k?.classes ?? 0,
          icon: LayoutGrid,
          sub: `${k?.subjects ?? 0} subjects`,
          href: "/classes",
          iconClass: "bg-amber-500/14 text-amber-700 dark:text-amber-300",
        },
        {
          label: "Attendance rate",
          value: k?.attendance_rate == null ? "—" : `${Math.round(k.attendance_rate)}%`,
          icon: CalendarCheck,
          delta: attDelta,
          deltaLabel: "vs this week",
          sub: "All recorded sessions",
          href: "/attendance",
          iconClass: "bg-rose-500/10 text-rose-700 dark:text-rose-300",
        },
        {
          label: "Payroll",
          value: "—",
          icon: Wallet,
          sub: "View pay runs",
          href: "/payroll",
          iconClass: "bg-sky-500/10 text-sky-700 dark:text-sky-300",
        },
      ]
    : [
        {
          label: "Students",
          value: k?.students ?? 0,
          icon: Users,
          sub: `${data?.distribution?.total ?? 0} enrolled`,
          href: "/students",
          iconClass: "bg-indigo-500/10 text-indigo-600 dark:text-indigo-300",
        },
        {
          label: "Teachers",
          value: k?.teachers ?? 0,
          icon: GraduationCap,
          sub: `${k?.staff ?? 0} total staff`,
          href: "/teachers",
          iconClass: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
        },
        {
          label: "Classes",
          value: k?.classes ?? 0,
          icon: LayoutGrid,
          sub: `${k?.subjects ?? 0} subjects`,
          href: "/classes",
          iconClass: "bg-amber-500/14 text-amber-700 dark:text-amber-300",
        },
        {
          label: "Attendance",
          value: k?.attendance_rate == null ? "—" : `${Math.round(k.attendance_rate)}%`,
          icon: CalendarCheck,
          delta: attDelta,
          deltaLabel: "vs this week",
          sub: attDelta != null ? `${attDelta >= 0 ? "above" : "below"} weekly rate` : "All sessions",
          href: "/attendance",
          iconClass: "bg-rose-500/10 text-rose-700 dark:text-rose-300",
        },
        {
          label: "Result readiness",
          value: k?.readiness_overall == null ? "—" : `${Math.round(k.readiness_overall)}%`,
          icon: BarChart3,
          sub: `${k?.readiness_pending ?? 0} scores still pending`,
          href: "/readiness",
          iconClass: "bg-violet-500/10 text-violet-700 dark:text-violet-300",
        },
      ];

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
      {cards.map((c) => (
        <KpiCard key={c.label} {...c} loading={loading} />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Academic performance
// ---------------------------------------------------------------------------
export function PerformancePanel({ data, loading, error, onRetry }: { data?: DashboardSummary; loading: boolean; error?: boolean; onRetry?: () => void }) {
  const byTerm = data?.performance?.by_term ?? [];
  return (
    <WidgetCard
      title="Academic performance"
      icon={<TrendingUp className="h-4 w-4 text-primary" />}
      subtitle="Average score and pass rate by term"
      loading={loading}
      error={error}
      onRetry={onRetry}
      empty={!loading && byTerm.length === 0}
      emptyHint="Once scores are entered, performance trends will appear here."
      className="lg:col-span-2"
      bodyClassName="pt-4"
    >
      <div className="mb-3 flex items-center gap-4 text-xs">
        <span className="flex items-center gap-1.5 font-medium text-muted-foreground">
          <span className="h-2.5 w-2.5 rounded-full bg-chart-1" /> Average
        </span>
        <span className="flex items-center gap-1.5 font-medium text-muted-foreground">
          <span className="h-2.5 w-2.5 rounded-full bg-chart-3" /> Pass rate
        </span>
      </div>
      <PerformanceChart data={byTerm} />
    </WidgetCard>
  );
}

// ---------------------------------------------------------------------------
// Result readiness (core SchoolOS widget)
// ---------------------------------------------------------------------------
export function ReadinessPanel({
  termId,
  summary,
  loading,
  error,
  onRetry,
}: {
  termId?: string | null;
  summary?: DashboardSummary;
  loading: boolean;
  error?: boolean;
  onRetry?: () => void;
}) {
  const { data: rows, isLoading: rowsLoading } = useReadiness(termId ?? null);
  const readyLoading = loading || rowsLoading;

  const agg = useMemo(() => {
    if (!rows?.length) return null;
    const map = new Map<string, { subject: string; entered: number; submitted: number; pending: number; total: number }>();
    for (const r of rows) {
      const cur = map.get(r.subject_name) ?? { subject: r.subject_name, entered: 0, submitted: 0, pending: 0, total: 0 };
      cur.entered += r.entered;
      cur.submitted += r.submitted;
      cur.pending += r.pending;
      cur.total += r.student_count;
      map.set(r.subject_name, cur);
    }
    const list = [...map.values()].sort((a, b) => a.entered / a.total - b.entered / b.total);
    const totals = list.reduce(
      (acc, x) => ({ entered: acc.entered + x.entered, submitted: acc.submitted + x.submitted, pending: acc.pending + x.pending, total: acc.total + x.total }),
      { entered: 0, submitted: 0, pending: 0, total: 0 },
    );
    return { list, totals };
  }, [rows]);

  const overall =
    summary?.kpis?.readiness_overall ??
    (agg && agg.totals.total ? Math.round((agg.totals.entered / agg.totals.total) * 100) : null);
  const submitted = summary?.kpis?.readiness_submitted ?? agg?.totals.submitted ?? 0;
  const pending = summary?.kpis?.readiness_pending ?? agg?.totals.pending ?? 0;
  const inProgress = agg ? agg.totals.entered - agg.totals.submitted : 0;

  const statuses = [
    { label: "Submitted", value: submitted, color: "bg-chart-1", icon: ClipboardCheck },
    { label: "In progress", value: inProgress, color: "bg-chart-4", icon: Clock },
    { label: "Pending", value: pending, color: "bg-chart-6", icon: AlertTriangle },
  ];

  return (
    <WidgetCard
      title="Result readiness"
      icon={<BarChart3 className="h-4 w-4 text-primary" />}
      subtitle="What's blocking report cards"
      loading={readyLoading}
      error={error}
      onRetry={onRetry}
      empty={!readyLoading && !agg}
      emptyHint="Set up score entry to see readiness here."
      className="xl:col-span-1"
    >
      <div className="flex items-center gap-4">
        <ReadinessRing pct={overall} size="lg" />
        <div className="flex-1 space-y-2">
          {statuses.map(({ label, value, color, icon: Icon }) => (
            <div key={label} className="flex items-center justify-between text-[13px]">
              <span className="flex items-center gap-1.5 text-muted-foreground">
                <span className={cn("h-2 w-2 rounded-full", color)} />
                <Icon className="h-3.5 w-3.5" />
                {label}
              </span>
              <span className="font-semibold">{value}</span>
            </div>
          ))}
        </div>
      </div>

      {agg && agg.list.length > 0 && (
        <div className="mt-5 space-y-3 border-t pt-4">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            By subject
          </p>
          {agg.list.slice(0, 6).map((row) => {
            const pct = row.total ? Math.round((row.entered / row.total) * 100) : 0;
            const done = pct >= 100;
            return (
              <div key={row.subject}>
                <div className="flex items-center justify-between text-[13px]">
                  <span className="font-medium">{row.subject}</span>
                  <span className="flex items-center gap-1.5">
                    {done && <Check className="h-3.5 w-3.5 text-success" />}
                    <span className={cn("font-semibold", done ? "text-success" : "text-foreground")}>{pct}%</span>
                  </span>
                </div>
                <ReadinessBar value={pct} size="sm" sheen={!done} className="mt-1.5" />
              </div>
            );
          })}
        </div>
      )}

      <Link
        href="/readiness"
        className="mt-5 inline-flex w-full items-center justify-center gap-1.5 rounded-lg border bg-muted/30 px-3 py-2 text-[13px] font-semibold text-foreground transition-colors hover:bg-accent"
      >
        View Result Readiness <ArrowRight className="h-3.5 w-3.5" />
      </Link>
    </WidgetCard>
  );
}

// ---------------------------------------------------------------------------
// Enrollment distribution
// ---------------------------------------------------------------------------
export function EnrollmentPanel({ data, loading, error, onRetry }: { data?: DashboardSummary; loading: boolean; error?: boolean; onRetry?: () => void }) {
  const slices = data?.distribution?.slices ?? [];
  return (
    <WidgetCard
      title="Enrollment"
      icon={<Users className="h-4 w-4 text-primary" />}
      subtitle="Students by class level"
      loading={loading}
      error={error}
      onRetry={onRetry}
      empty={!loading && slices.length === 0}
      emptyHint="Enroll students to see the distribution."
      bodyClassName="pt-4"
    >
      <DistributionDonut data={slices} total={data?.distribution?.total} />
      <ul className="mt-3 space-y-1.5">
        {slices.slice(0, 6).map((s) => (
          <li key={s.level_code} className="flex items-center justify-between text-[13px]">
            <span className="flex items-center gap-2 text-muted-foreground">
              <span className="h-2 w-2 rounded-full bg-chart-1" />
              {s.level_name}
            </span>
            <span className="font-medium">
              {s.count} <span className="text-muted-foreground">· {s.pct}%</span>
            </span>
          </li>
        ))}
      </ul>
    </WidgetCard>
  );
}

// ---------------------------------------------------------------------------
// Attendance overview
// ---------------------------------------------------------------------------
export function AttendancePanel({ data, loading, error, onRetry }: { data?: DashboardSummary; loading: boolean; error?: boolean; onRetry?: () => void }) {
  const [range, setRange] = useState<"today" | "week" | "month">("today");
  const att = data?.attendance;
  const ov: AttendanceOverview | undefined = att?.[range];

  const bars = useMemo(() => {
    if (!att) return [];
    return (
      [
        { key: "today", name: "Today", present: att.today.present, absent: att.today.absent, late: att.today.late },
        { key: "week", name: "Week", present: att.week.present, absent: att.week.absent, late: att.week.late },
        { key: "month", name: "Month", present: att.month.present, absent: att.month.absent, late: att.month.late },
      ].filter((b) => b.present || b.absent || b.late)
    );
  }, [att]);

  return (
    <WidgetCard
      title="Attendance overview"
      icon={<CalendarCheck className="h-4 w-4 text-primary" />}
      subtitle="Student attendance across the school"
      loading={loading}
      error={error}
      onRetry={onRetry}
      empty={!loading && bars.length === 0}
      emptyHint="Mark attendance to see insights here."
      className="lg:col-span-2"
      bodyClassName="pt-4"
      actions={<Segmented value={range} options={[{ value: "today", label: "Today" }, { value: "week", label: "Week" }, { value: "month", label: "Month" }]} onChange={setRange} />}
    >
      <div className="grid gap-4 sm:grid-cols-[1fr_auto]">
        <div className="min-w-0">
          {bars.length > 0 ? (
            <AttendanceBars data={bars} height={190} />
          ) : (
            <div className="flex h-[190px] items-center justify-center text-sm text-muted-foreground">
              No attendance recorded yet.
            </div>
          )}
        </div>
        {ov && (
          <div className="flex flex-col justify-center gap-2">
            <div className="rounded-xl border bg-muted/30 px-4 py-3 text-center">
              <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Rate</p>
              <p className="text-2xl font-bold">{ov.rate == null ? "—" : `${Math.round(ov.rate)}%`}</p>
            </div>
            <div className="grid grid-cols-1 gap-1.5 text-[13px]">
              {[
                { label: "Present", value: ov.present, color: "bg-success" },
                { label: "Absent", value: ov.absent, color: "bg-destructive" },
                { label: "Late", value: ov.late, color: "bg-warning" },
              ].map((s) => (
                <div key={s.label} className="flex items-center justify-between gap-6 rounded-lg border px-3 py-1.5">
                  <span className="flex items-center gap-1.5 text-muted-foreground">
                    <span className={cn("h-2 w-2 rounded-full", s.color)} /> {s.label}
                  </span>
                  <span className="font-semibold">{s.value}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </WidgetCard>
  );
}

// ---------------------------------------------------------------------------
// Class performance
// ---------------------------------------------------------------------------
export function ClassPerformancePanel({ data, loading, error, onRetry }: { data?: DashboardSummary; loading: boolean; error?: boolean; onRetry?: () => void }) {
  const byClass = data?.performance?.by_class ?? [];
  return (
    <WidgetCard
      title="Class performance"
      icon={<LayoutGrid className="h-4 w-4 text-primary" />}
      subtitle="Average score for the selected term"
      loading={loading}
      error={error}
      onRetry={onRetry}
      empty={!loading && byClass.length === 0}
      emptyHint="Class averages appear once results are entered."
      bodyClassName="pt-4"
    >
      <ClassPerformanceBar data={byClass} />
      <ul className="mt-3 space-y-1.5 border-t pt-3">
        {byClass.slice(0, 6).map((c) => (
          <li key={c.arm_name} className="flex items-center justify-between text-[13px]">
            <span className="text-muted-foreground">{c.arm_name}</span>
            <span className="flex items-center gap-3">
              <span className="font-medium">{c.avg_score == null ? "—" : `${c.avg_score}%`}</span>
              <span className="w-14 text-right text-xs text-muted-foreground">{c.count} results</span>
            </span>
          </li>
        ))}
      </ul>
    </WidgetCard>
  );
}

// ---------------------------------------------------------------------------
// Quick actions
// ---------------------------------------------------------------------------
const ALL_ACTIONS: { label: string; desc: string; href: string; icon: React.ElementType; perm: string; tone: string }[] = [
  { label: "Add student", desc: "Enroll into a class", href: "/students", icon: UserPlus, perm: "students.create", tone: "bg-indigo-500/10 text-indigo-600" },
  { label: "Add teacher", desc: "Create a staff record", href: "/teachers", icon: GraduationCap, perm: "staff.create", tone: "bg-emerald-500/10 text-emerald-700" },
  { label: "Create class", desc: "Arms & offerings", href: "/classes", icon: LayoutGrid, perm: "academics.manage", tone: "bg-amber-500/14 text-amber-700" },
  { label: "Enter result", desc: "Open a score grid", href: "/results/score", icon: ClipboardCheck, perm: "results.enter", tone: "bg-rose-500/10 text-rose-700" },
  { label: "Mark attendance", desc: "Today's register", href: "/attendance", icon: CalendarCheck, perm: "attendance.mark", tone: "bg-sky-500/10 text-sky-700" },
  { label: "Review approvals", desc: "Verify & publish", href: "/approvals", icon: ListChecks, perm: "results.verify", tone: "bg-violet-500/10 text-violet-700" },
  { label: "Generate report", desc: "Report cards", href: "/reports", icon: FileText, perm: "results.view", tone: "bg-teal-500/10 text-teal-700" },
  { label: "AI lesson plan", desc: "Plan a topic", href: "/lesson-plans", icon: NotebookPen, perm: "results.comment", tone: "bg-fuchsia-500/10 text-fuchsia-700" },
];

export function QuickActions() {
  const { activeSchool } = useAuth();
  const perms = activeSchool?.permissions ?? [];
  const actions = ALL_ACTIONS.filter((a) => perms.includes(a.perm));
  if (actions.length === 0) return null;
  return (
    <WidgetCard
      title="Quick actions"
      icon={<Sparkles className="h-4 w-4 text-primary" />}
      subtitle="Jump straight into what matters"
      bodyClassName="pt-4"
    >
      <div className="grid gap-2 sm:grid-cols-2">
        {actions.map((a) => (
          <Link
            key={a.label}
            href={a.href}
            className="group flex items-center gap-3 rounded-xl border px-3.5 py-3 transition-all hover:border-primary/25 hover:bg-accent/50"
          >
            <span className={cn("flex h-8 w-8 shrink-0 items-center justify-center rounded-lg", a.tone)}>
              <a.icon className="h-4 w-4" />
            </span>
            <span className="min-w-0">
              <span className="block text-[13px] font-semibold leading-tight">{a.label}</span>
              <span className="block truncate text-[11px] text-muted-foreground">{a.desc}</span>
            </span>
          </Link>
        ))}
      </div>
    </WidgetCard>
  );
}

// ---------------------------------------------------------------------------
// Recent activity
// ---------------------------------------------------------------------------
const ACTIVITY_META: Record<string, { icon: React.ElementType; tone: string }> = {
  result: { icon: ClipboardCheck, tone: "bg-indigo-500/10 text-indigo-600" },
  student: { icon: UserPlus, tone: "bg-emerald-500/10 text-emerald-700" },
  staff: { icon: GraduationCap, tone: "bg-amber-500/14 text-amber-700" },
  payment: { icon: Wallet, tone: "bg-sky-500/10 text-sky-700" },
  ai: { icon: Bot, tone: "bg-violet-500/10 text-violet-700" },
  attendance: { icon: CalendarCheck, tone: "bg-rose-500/10 text-rose-700" },
  other: { icon: Clock, tone: "bg-muted text-muted-foreground" },
};

export function ActivityPanel({ items, loading, error, onRetry, className }: { items?: ActivityItem[]; loading: boolean; error?: boolean; onRetry?: () => void; className?: string }) {
  const list = items ?? [];
  return (
    <WidgetCard
      title="Recent activity"
      icon={<Clock className="h-4 w-4 text-primary" />}
      subtitle="Latest changes across the school"
      loading={loading}
      error={error}
      onRetry={onRetry}
      empty={!loading && list.length === 0}
      emptyHint="Actions across the school will show up here."
      className={className}
      bodyClassName="pt-3"
    >
      <ul className="space-y-1">
        {list.slice(0, 8).map((a) => {
          const meta = ACTIVITY_META[a.kind] ?? ACTIVITY_META.other;
          const Icon = meta.icon;
          return (
            <li key={a.id}>
              <Link
                href={a.href ?? "#"}
                className="group flex items-start gap-3 rounded-lg px-2 py-2 transition-colors hover:bg-accent"
              >
                <span className={cn("mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg", meta.tone)}>
                  <Icon className="h-4 w-4" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[13px] font-medium">{a.title}</p>
                  <p className="truncate text-xs text-muted-foreground">
                    {a.detail ? `${a.detail} · ` : ""}{a.actor_name}
                  </p>
                </div>
                <span className="shrink-0 text-[11px] text-muted-foreground/70">{relativeTime(a.created_at)}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </WidgetCard>
  );
}

// ---------------------------------------------------------------------------
// Pending tasks
// ---------------------------------------------------------------------------
const TASK_META: Record<string, { icon: React.ElementType; tone: string }> = {
  results: { icon: ClipboardCheck, tone: "bg-indigo-500/10 text-indigo-600" },
  finance: { icon: Wallet, tone: "bg-sky-500/10 text-sky-700" },
  students: { icon: UserPlus, tone: "bg-emerald-500/10 text-emerald-700" },
  attendance: { icon: CalendarCheck, tone: "bg-rose-500/10 text-rose-700" },
};

export function TasksPanel({ tasks, loading, error, onRetry }: { tasks?: TaskItem[]; loading: boolean; error?: boolean; onRetry?: () => void }) {
  const list = tasks ?? [];
  return (
    <WidgetCard
      title="Pending tasks"
      icon={<ListChecks className="h-4 w-4 text-primary" />}
      subtitle="Things that need attention"
      loading={loading}
      error={error}
      onRetry={onRetry}
      bodyClassName="pt-3"
    >
      {!loading && !error && list.length === 0 ? (
        <div className="flex items-center gap-2 rounded-lg border bg-success/5 px-3 py-3 text-sm">
          <CheckCircle2 className="h-4 w-4 text-success" /> All caught up — nothing pending.
        </div>
      ) : (
        <ul className="space-y-1">
          {list.map((t) => {
            const meta = TASK_META[t.kind] ?? TASK_META.results;
            const Icon = meta.icon;
            return (
              <li key={t.id}>
                <Link
                  href={t.href}
                  className="group flex items-center gap-3 rounded-lg border px-3.5 py-3 transition-all hover:border-primary/25 hover:bg-accent/50"
                >
                  <span className={cn("flex h-8 w-8 shrink-0 items-center justify-center rounded-lg", meta.tone)}>
                    <Icon className="h-4 w-4" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[13px] font-medium">{t.title}</p>
                    <p className="truncate text-xs text-muted-foreground">{t.detail}</p>
                  </div>
                  <span className="flex h-6 min-w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 px-1.5 text-xs font-bold text-primary">
                    {t.count}
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </WidgetCard>
  );
}

// ---------------------------------------------------------------------------
// AI insights
// ---------------------------------------------------------------------------
const INSIGHT_META: Record<string, { icon: React.ElementType; tone: string; dot: string }> = {
  positive: { icon: TrendingUp, tone: "border-success/25 bg-success/5", dot: "bg-success" },
  warning: { icon: AlertTriangle, tone: "border-warning/30 bg-warning/5", dot: "bg-warning" },
  info: { icon: Lightbulb, tone: "border-border bg-muted/30", dot: "bg-primary" },
};

export function InsightsPanel({ items, loading, error, onRetry }: { items?: InsightItem[]; loading: boolean; error?: boolean; onRetry?: () => void }) {
  const list = items ?? [];
  return (
    <WidgetCard
      title={
        <span className="flex items-center gap-2">
          Lumo AI insights
          <Badge variant="default" className="gap-1 bg-violet-500/10 text-violet-600 dark:text-violet-300">
            <Bot className="h-3 w-3" /> AI
          </Badge>
        </span>
      }
      icon={null}
      subtitle="Signals generated from your data"
      loading={loading}
      error={error}
      onRetry={onRetry}
      empty={!loading && list.length === 0}
      emptyHint="AI insights appear once there's enough data."
      bodyClassName="pt-3"
    >
      <ul className="space-y-2">
        {list.map((i) => {
          const meta = INSIGHT_META[i.tone] ?? INSIGHT_META.info;
          const Icon = meta.icon;
          return (
            <li key={i.id} className={cn("rounded-xl border p-3.5", meta.tone)}>
              <div className="flex items-start justify-between gap-3">
                <p className="flex items-center gap-2 text-[13px] font-semibold">
                  <Icon className="h-4 w-4 shrink-0 text-primary" />
                  {i.title}
                </p>
                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-violet-500/30 bg-violet-500/10">
                  <Bot className="h-3 w-3 text-violet-600 dark:text-violet-300" />
                </span>
              </div>
              <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">{i.body}</p>
              <div className="mt-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground/30" />
                  <span className="text-[11px] text-muted-foreground">Confidence {Math.round(i.confidence * 100)}%</span>
                </div>
                {i.href && (
                  <Link href={i.href} className="inline-flex items-center gap-1 text-[11px] font-semibold text-primary hover:underline">
                    View details <ArrowRight className="h-3 w-3" />
                  </Link>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </WidgetCard>
  );
}

// ---------------------------------------------------------------------------
// Approval queue (VP academics / principal focus)
// ---------------------------------------------------------------------------
export function ApprovalQueuePanel({
  termId,
  loading,
  error,
  onRetry,
}: {
  termId?: string | null;
  loading: boolean;
  error?: boolean;
  onRetry?: () => void;
}) {
  const { data: rows, isLoading } = useWorkbench(termId ?? null);
  const busy = loading || isLoading;
  const queue = rows ?? [];

  const totals = useMemo(
    () =>
      queue.reduce(
        (acc, r) => ({
          draft: acc.draft + r.draft,
          submitted: acc.submitted + r.submitted,
          verified: acc.verified + r.verified,
          approved: acc.approved + r.approved,
          rejected: acc.rejected + r.rejected,
        }),
        { draft: 0, submitted: 0, verified: 0, approved: 0, rejected: 0 },
      ),
    [queue],
  );

  const needsReview = queue
    .filter((r) => r.submitted > 0 || r.verified > 0)
    .sort((a, b) => b.submitted + b.verified - (a.submitted + a.verified))
    .slice(0, 5);

  const funnel = [
    { label: "Draft", value: totals.draft, color: "bg-muted-foreground/50" },
    { label: "Submitted", value: totals.submitted, color: "bg-chart-2" },
    { label: "Verified", value: totals.verified, color: "bg-chart-4" },
    { label: "Approved", value: totals.approved, color: "bg-chart-3" },
    { label: "Returned", value: totals.rejected, color: "bg-chart-6" },
  ];
  const maxStage = Math.max(1, ...funnel.map((f) => f.value));

  return (
    <WidgetCard
      title="Result approval queue"
      icon={<ListChecks className="h-4 w-4 text-primary" />}
      subtitle="Teacher submissions awaiting review"
      loading={busy}
      error={error}
      onRetry={onRetry}
      empty={!busy && queue.length === 0}
      emptyHint="Submissions will appear once teachers enter scores."
      bodyClassName="pt-4"
    >
      <div className="space-y-2.5">
        {funnel.map((f) => (
          <div key={f.label} className="flex items-center gap-3">
            <span className="w-20 shrink-0 text-[13px] text-muted-foreground">{f.label}</span>
            <div className="relative h-2.5 flex-1 overflow-hidden rounded-full bg-muted">
              <div className={cn("h-full rounded-full transition-all duration-500", f.color)} style={{ width: `${(f.value / maxStage) * 100}%` }} />
            </div>
            <span className="w-8 shrink-0 text-right text-[13px] font-semibold">{f.value}</span>
          </div>
        ))}
      </div>

      {needsReview.length > 0 && (
        <div className="mt-5 border-t pt-4">
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Needs attention
          </p>
          <ul className="space-y-1">
            {needsReview.map((r) => (
              <li key={`${r.arm_id}-${r.subject_id}`}>
                <Link
                  href="/approvals"
                  className="flex items-center justify-between rounded-lg px-2 py-1.5 text-[13px] transition-colors hover:bg-accent"
                >
                  <span className="truncate">
                    <span className="font-medium">{r.arm_name}</span>
                    <span className="text-muted-foreground"> · {r.subject_name}</span>
                  </span>
                  <span className="shrink-0 font-semibold text-primary">
                    {(r.submitted + r.verified).toLocaleString()}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </WidgetCard>
  );
}