"use client";

import { motion } from "framer-motion";
import {
  ArrowRight,
  BookOpen,
  CalendarCheck,
  ClipboardCheck,
  GraduationCap,
  UserPlus,
  Users,
  Wallet,
} from "lucide-react";
import Link from "next/link";

import { KpiCard } from "@/components/dashboard/shared";
import {
  ActivityPanel,
  ApprovalQueuePanel,
  AttendancePanel,
  ClassPerformancePanel,
  CompilePanel,
  EnrollmentPanel,
  InsightsPanel,
  PerformancePanel,
  QuickActions,
  ReadinessPanel,
  TasksPanel,
} from "@/components/dashboard/widgets";
import { Button } from "@/components/ui/button";
import { useDashboardSummary } from "@/hooks/use-api";
import { useAuth } from "@/providers/auth-provider";
import { useSessionTerm } from "@/providers/session-context";
import { cn, formatMoney } from "@/lib/utils";

const ease = [0.25, 0.46, 0.45, 0.94] as const;

/**
 * The school overview: KPIs, academics, finance, attendance and activity, all
 * from ``GET /api/dashboard/summary``.
 *
 * Every number is the school's own — nothing is invented. Panels the caller
 * cannot see data for (results, fees, attendance reports, AI) are dropped
 * rather than shown as zeros, mirroring how the API zeroes those fields for a
 * caller without the matching permission. Each panel renders its own loading,
 * empty and error state, so one failing section never blanks the page.
 */
export function ManagementDashboard({ variant }: { variant: "admin" | "academic" }) {
  const { user, activeSchool } = useAuth();
  const { term } = useSessionTerm();
  const { data, isLoading, isError, refetch } = useDashboardSummary(term?.id);

  const perms = activeSchool?.permissions ?? [];
  const isSuperadmin = user?.is_superadmin ?? false;
  // Platform admins bypass permission checks server-side, so mirror that here.
  const can = (permission: string) => isSuperadmin || perms.includes(permission);

  const canResults = can("results.view");
  const canStudents = can("students.view");
  const canFees = can("fees.view");
  const canAttendance = can("attendance.report");
  const canAi = can("ai.copilot");
  const canApprove = can("results.verify");

  const kpis = data?.kpis;
  const currency = kpis?.fee_currency ?? "NGN";
  const retry = () => void refetch();

  // Only the panels this caller can actually read data for — and the grid
  // adapts to how many survive, so a single panel is never one third wide.
  const detailPanels = [
    canStudents && (
      <EnrollmentPanel key="enrollment" data={data} loading={isLoading} error={isError} onRetry={retry} />
    ),
    canAttendance && (
      <AttendancePanel key="attendance" data={data} loading={isLoading} error={isError} onRetry={retry} />
    ),
    canResults && (
      <ClassPerformancePanel key="class-performance" data={data} loading={isLoading} error={isError} onRetry={retry} />
    ),
  ].filter(Boolean);

  const kpiCards = [
    {
      label: "Total students",
      value: (kpis?.students ?? 0).toLocaleString(),
      icon: Users,
      href: "/students",
      sub: `${data?.distribution.total ?? 0} enrolled this session`,
      show: canStudents,
      tone: "blue" as const,
      delay: 0.06,
    },
    {
      label: "Teaching staff",
      value: (kpis?.teachers ?? 0).toLocaleString(),
      icon: GraduationCap,
      href: "/teachers",
      sub: `${kpis?.staff ?? 0} staff in total`,
      show: true,
      tone: "emerald" as const,
      delay: 0.08,
    },
    {
      label: "Classes",
      value: (kpis?.classes ?? 0).toLocaleString(),
      icon: BookOpen,
      href: "/classes",
      sub: `${kpis?.subjects ?? 0} subjects offered`,
      show: can("academics.view"),
      tone: "violet" as const,
      delay: 0.1,
    },
    {
      label: "Attendance",
      value: kpis?.attendance_rate == null ? "—" : `${kpis.attendance_rate}%`,
      icon: CalendarCheck,
      href: "/attendance",
      sub: "This month",
      show: canAttendance,
      tone: "cyan" as const,
      delay: 0.12,
    },
    {
      label: "Outstanding fees",
      value: formatMoney(kpis?.outstanding_fees, currency),
      icon: Wallet,
      href: "/billing",
      sub: "Unpaid invoices",
      show: canFees,
      tone: "amber" as const,
      delay: 0.14,
    },
    {
      label: "Result readiness",
      value: kpis?.readiness_overall == null ? "—" : `${kpis.readiness_overall}%`,
      icon: ClipboardCheck,
      href: "/readiness",
      sub: `${kpis?.readiness_pending ?? 0} entries pending`,
      show: canResults,
      tone: "rose" as const,
      delay: 0.16,
    },
  ].filter((card) => card.show);

  return (
    <div className="space-y-6">
      {/* ── Page header ─────────────────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease }}
        className="flex flex-wrap items-end justify-between gap-4"
      >
        <div className="min-w-0">
          <h1 className="text-[24px] font-bold tracking-tight text-foreground">Overview</h1>
          <p className="mt-1 text-[13.5px] text-muted-foreground/60">
            Here&apos;s what&apos;s happening across {activeSchool?.school_name}.
          </p>
          {term && (
            <p className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-primary/5 px-3 py-1 text-[12px] font-medium text-primary/70">
              <span className="h-1.5 w-1.5 rounded-full bg-primary/60" />
              {term.name}
            </p>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {canStudents && (
            <Button asChild size="sm" className="gap-1.5">
              <Link href="/students">
                <UserPlus className="h-3.5 w-3.5" />
                Add student
              </Link>
            </Button>
          )}
          {canResults && (
            <Button asChild size="sm" variant="outline" className="gap-1.5">
              <Link href={variant === "academic" ? "/approvals" : "/reports"}>
                {variant === "academic" ? "Process results" : "Report cards"}
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </Button>
          )}
        </div>
      </motion.div>

      {/* ── KPIs ────────────────────────────────────────────────────── */}
      {kpiCards.length > 0 && (
        <div className="grid gap-3.5 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {kpiCards.map((card) => (
            <motion.div
              key={card.label}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, delay: card.delay, ease }}
            >
              <KpiCard
                label={card.label}
                value={card.value}
                icon={card.icon}
                sub={card.sub}
                href={card.href}
                tone={card.tone}
                loading={isLoading}
              />
            </motion.div>
          ))}
        </div>
      )}

      {/* ── Quick actions ───────────────────────────────────────────── */}
      <QuickActions />

      {/* ── Academics: performance + what needs attention ───────────── */}
      {canResults && (
        <div className="grid gap-5 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <PerformancePanel data={data} loading={isLoading} error={isError} onRetry={retry} />
          </div>
          <TasksPanel tasks={data?.tasks} loading={isLoading} error={isError} onRetry={retry} />
        </div>
      )}

      {/* ── Result work (academic roles only) ───────────────────────── */}
      {variant === "academic" && canApprove && (
        <div className="grid gap-5 lg:grid-cols-2">
          <ApprovalQueuePanel termId={term?.id ?? null} loading={isLoading} error={isError} onRetry={retry} />
          <ReadinessPanel termId={term?.id ?? null} summary={data} loading={isLoading} error={isError} onRetry={retry} />
        </div>
      )}

      {/* ── Students, attendance & class performance ────────────────── */}
      <div
        className={cn(
          "grid gap-5",
          detailPanels.length === 3 ? "lg:grid-cols-3" : detailPanels.length === 2 ? "lg:grid-cols-2" : "",
        )}
      >
        {detailPanels}
      </div>

      {/* ── Compile (academic roles) ────────────────────────────────── */}
      {variant === "academic" && canApprove && (
        <CompilePanel termId={term?.id ?? null} loading={isLoading} error={isError} onRetry={retry} />
      )}

      {/* ── Activity + insights ─────────────────────────────────────── */}
      <div className={cn("grid gap-5", canAi && "lg:grid-cols-3")}>
        <ActivityPanel
          items={data?.activity}
          loading={isLoading}
          error={isError}
          onRetry={retry}
          className={canAi ? "lg:col-span-2" : undefined}
        />
        {canAi && (
          <InsightsPanel
            items={data?.insights.insights}
            loading={isLoading}
            error={isError}
            onRetry={retry}
          />
        )}
      </div>
    </div>
  );
}
