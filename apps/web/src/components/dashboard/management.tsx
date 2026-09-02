"use client";

import { useMemo } from "react";
import { motion } from "framer-motion";

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

const ease = [0.25, 0.46, 0.45, 0.94] as const;

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
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease }}
    >
      <h2 className="text-[26px] font-bold tracking-tight text-foreground">
        {part}, {user?.full_name?.split(" ")[0] ?? "there"}.
      </h2>
      <p className="mt-1.5 text-[14px] text-muted-foreground/70">
        Here&apos;s what&apos;s happening today — {today}
      </p>
      {term && (
        <p className="mt-1 text-[13px] font-medium text-muted-foreground/50">{term.name}</p>
      )}
    </motion.div>
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
