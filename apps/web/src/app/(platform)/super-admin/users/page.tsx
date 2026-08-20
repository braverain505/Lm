"use client";

import { useState } from "react";

import { TrendArea } from "@/components/platform-charts";
import { EmptyState, Panel, PanelSkeleton, StatCard, fmtNum } from "@/components/platform-utils";
import { Button } from "@/components/ui/button";
import { useSaUsers } from "@/hooks/use-superadmin";

const RANGES = ["6m", "12m", "all"];

export default function SuperAdminUsersPage() {
  const [range, setRange] = useState("12m");
  const { data, isLoading } = useSaUsers(range);

  const totals = (data?.totals ?? {}) as Record<string, number>;
  const series = (data?.series ?? []) as Array<{ period: string; students: number; teachers: number; parents: number; admins: number; total: number }>;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-2">
        {RANGES.map((r) => (
          <Button key={r} size="sm" variant={range === r ? "default" : "outline"} onClick={() => setRange(r)}>
            {r}
          </Button>
        ))}
      </div>

      {isLoading ? (
        <PanelSkeleton rows={6} />
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Students" value={fmtNum(totals.students)} />
            <StatCard label="Teachers" value={fmtNum(totals.teachers)} />
            <StatCard label="Parents" value={fmtNum(totals.parents)} />
            <StatCard label="School admins" value={fmtNum(totals.admins)} />
          </div>

          <Panel title="User base growth" subtitle="Cumulative accounts by role">
            <TrendArea
              data={series as Array<Record<string, unknown>>}
              keys={[
                { key: "students", name: "Students", color: "hsl(var(--chart-1))" },
                { key: "teachers", name: "Teachers", color: "hsl(var(--chart-3))" },
                { key: "parents", name: "Parents", color: "hsl(var(--chart-4))" },
                { key: "admins", name: "Admins", color: "hsl(var(--chart-5))" },
              ]}
            />
          </Panel>
        </>
      )}
    </div>
  );
}