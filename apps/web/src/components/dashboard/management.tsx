"use client";

import { useMemo } from "react";

import {
  ActivityPanel,
  ApprovalQueuePanel,
  AttendancePanel,
  ClassPerformancePanel,
  CompilePanel,
  EnrollmentPanel,
  InsightsPanel,
  KpiRow,
  PerformancePanel,
  QuickActions,
  ReadinessPanel,
  TasksPanel,
} from "@/components/dashboard/widgets";
import { useSessionTerm } from "@/providers/session-context";
import { useAuth } from "@/providers/auth-provider";
import { useDashboardSummary } from "@/hooks/use-api";

function Greeting() {
  const { user, activeSchool } = useAuth();
  const { term } = useSessionTerm();
  const hour = new Date().getHours();
  const part = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
  const today = new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" });
  return (
    <div className="flex flex-wrap items-end justify-between gap-4 rounded-2xl border border-primary/15 bg-gradient-to-r from-primary/[0.08] via-cyan-400/[0.06] to-transparent px-5 py-4 sm:px-6">
      <div>
        <h2 className="text-xl font-bold tracking-tight sm:text-2xl">
          {part}, {user?.full_name?.split(" ")[0] ?? "there"}
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Here&apos;s what&apos;s happening at {activeSchool?.school_name} — {today}.
        </p>
      </div>
      {term && <span className="rounded-full border border-primary/20 bg-card/80 px-3 py-1.5 text-xs font-semibold text-primary">{term.name}</span>}
    </div>
  );
}

export function ManagementDashboard({ variant }: { variant: "admin" | "academic" }) {
  const { term } = useSessionTerm();
  const { data, isLoading, isError, refetch } = useDashboardSummary(term?.id ?? undefined);

  const common = {
    data,
    loading: isLoading,
    error: isError,
    onRetry: refetch,
  };

  const summary = useMemo(() => data, [data]);

  if (variant === "academic") {
    return (
      <div className="space-y-6">
        <Greeting />

        <KpiRow data={summary} loading={isLoading} />

        <div className="grid gap-4 xl:grid-cols-3">
          <ReadinessPanel termId={term?.id} {...common} />
          <ApprovalQueuePanel termId={term?.id} {...common} />
        </div>

        <div className="grid gap-4 xl:grid-cols-3">
          <CompilePanel termId={term?.id} {...common} />
          <PerformancePanel {...common} />
          <InsightsPanel items={summary?.insights?.insights} {...common} />
        </div>

        <div className="grid gap-4 xl:grid-cols-3">
          <ClassPerformancePanel {...common} />
          <TasksPanel tasks={summary?.tasks} {...common} />
        </div>

        <div className="grid gap-4 xl:grid-cols-3">
          <AttendancePanel {...common} />
          <ActivityPanel items={summary?.activity} {...common} />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Greeting />

      <KpiRow data={summary} loading={isLoading} />

      <div className="grid gap-4 xl:grid-cols-3">
        <PerformancePanel {...common} />
        <ReadinessPanel termId={term?.id} {...common} />
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <AttendancePanel {...common} />
        <EnrollmentPanel {...common} />
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <ClassPerformancePanel {...common} />
        <QuickActions />
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <ActivityPanel items={summary?.activity} {...common} />
        <TasksPanel tasks={summary?.tasks} {...common} />
        <InsightsPanel items={summary?.insights?.insights} {...common} />
      </div>
    </div>
  );
}