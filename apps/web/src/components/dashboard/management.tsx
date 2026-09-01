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
  ReadinessPanel,
  TasksPanel,
} from "@/components/dashboard/widgets";
import { useSessionTerm } from "@/providers/session-context";
import { useAuth } from "@/providers/auth-provider";
import { useDashboardSummary } from "@/hooks/use-api";

function Greeting() {
  const { user } = useAuth();
  const { term } = useSessionTerm();
  const hour = new Date().getHours();
  const part = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
  const today = new Date().toLocaleDateString(undefined, {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
  return (
    <div>
      <h2 className="text-[22px] font-bold tracking-tight text-foreground">
        {part}, {user?.full_name?.split(" ")[0] ?? "there"}.
      </h2>
      <p className="mt-1 text-[14px] text-muted-foreground">
        Here&apos;s what&apos;s happening today — {today}
      </p>
      {term && (
        <p className="mt-1 text-[13px] font-medium text-muted-foreground/70">{term.name}</p>
      )}
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
      <div className="space-y-8">
        <Greeting />
        <KpiRow data={summary} loading={isLoading} />

        <div className="grid gap-6 lg:grid-cols-2">
          <ReadinessPanel termId={term?.id} {...common} />
          <ApprovalQueuePanel termId={term?.id} {...common} />
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          <CompilePanel termId={term?.id} {...common} />
          <PerformancePanel {...common} />
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          <ClassPerformancePanel {...common} />
          <InsightsPanel items={summary?.insights?.insights} {...common} />
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          <AttendancePanel {...common} />
          <ActivityPanel items={summary?.activity} {...common} />
        </div>

        <TasksPanel tasks={summary?.tasks} {...common} />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <Greeting />
      <KpiRow data={summary} loading={isLoading} />

      <div className="grid gap-6 lg:grid-cols-2">
        <PerformancePanel {...common} />
        <ReadinessPanel termId={term?.id} {...common} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <AttendancePanel {...common} />
        <EnrollmentPanel {...common} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <ClassPerformancePanel {...common} />
        <ActivityPanel items={summary?.activity} {...common} />
      </div>

      <TasksPanel tasks={summary?.tasks} {...common} />
    </div>
  );
}
