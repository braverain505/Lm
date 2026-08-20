"use client";

import { useState } from "react";

import { TrendArea } from "@/components/platform-charts";
import { EmptyState, Panel, PanelSkeleton, StatCard, fmtNum } from "@/components/platform-utils";
import { Button } from "@/components/ui/button";
import { useSaGrowth } from "@/hooks/use-superadmin";

const RANGES = ["7d", "30d", "90d", "6m", "12m", "all"];

export default function SuperAdminGrowthPage() {
  const [range, setRange] = useState("12m");
  const { data, isLoading } = useSaGrowth(range);

  const series = (data?.series ?? []) as Array<{ period: string; total: number; new: number; activated: number; churned: number }>;
  const totals = (data?.totals ?? {}) as Record<string, number>;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-2">
        {RANGES.map((r) => (
          <Button
            key={r}
            size="sm"
            variant={range === r ? "default" : "outline"}
            onClick={() => setRange(r)}
          >
            {r}
          </Button>
        ))}
      </div>

      {isLoading ? (
        <PanelSkeleton rows={6} />
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Total schools" value={fmtNum(totals.total)} />
            <StatCard label="New" value={fmtNum(totals.new)} />
            <StatCard label="Activated" value={fmtNum(totals.activated)} />
            <StatCard label="Churned" value={fmtNum(totals.churned)} accent="text-destructive" />
          </div>

          <Panel title="School growth" subtitle="Cumulative total vs new and churned per period">
            <TrendArea
              data={series as Array<Record<string, unknown>>}
              keys={[
                { key: "total", name: "Total", color: "hsl(var(--chart-1))" },
                { key: "new", name: "New", color: "hsl(var(--chart-3))" },
                { key: "churned", name: "Churned", color: "hsl(var(--chart-6))" },
              ]}
            />
          </Panel>
        </>
      )}
    </div>
  );
}