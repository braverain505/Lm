"use client";

import { useState } from "react";

import { SeriesBars, TrendArea } from "@/components/platform-charts";
import { EmptyState, Panel, PanelSkeleton, ProgressBar, StatCard, StatusBadge, fmtCurrency, fmtNum, titleCase } from "@/components/platform-utils";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useSaAi } from "@/hooks/use-superadmin";

const RANGES = ["7d", "30d", "90d", "12m"];

export default function SuperAdminAiPage() {
  const [range, setRange] = useState("30d");
  const [feature, setFeature] = useState("all");
  const { data, isLoading } = useSaAi({ range, feature: feature === "all" ? undefined : feature });

  const metrics = (data?.metrics ?? {}) as Record<string, number | string>;
  const series = (data?.series ?? []) as Array<{ period: string; requests: number; credits: number; cost: number }>;
  const features = (data?.features ?? []) as Array<{ feature: string; count: number; cost: number; revenue: number }>;
  const topSchools = (data?.top_schools ?? []) as Array<{ school_id: string; name: string; count: number; credits: number; cost: number }>;
  const nearing = (data?.nearing_limits ?? []) as Array<{ school_id: string; name: string; used: number; total: number; pct: number }>;

  const featureOptions = features.map((f) => f.feature);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-2">
        {RANGES.map((r) => (
          <Button key={r} size="sm" variant={range === r ? "default" : "outline"} onClick={() => setRange(r)}>
            {r}
          </Button>
        ))}
        {featureOptions.length > 0 && (
          <Select value={feature} onValueChange={setFeature}>
            <SelectTrigger className="ml-auto h-8 w-48">
              <SelectValue placeholder="Feature" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All features</SelectItem>
              {featureOptions.map((f) => (
                <SelectItem key={f} value={f}>
                  {titleCase(f)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </div>

      {isLoading ? (
        <PanelSkeleton rows={6} />
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Requests (period)" value={fmtNum(metrics.requests_this_month)} />
            <StatCard label="Credits" value={fmtNum(metrics.credits)} />
            <StatCard label="Cost" value={fmtCurrency(metrics.cost, 2)} />
            <StatCard label="Revenue" value={fmtCurrency(metrics.revenue)} sub={`${metrics.margin_pct}% margin`} accent="text-success" />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Panel title="AI requests & credits" subtitle="Per period">
              <SeriesBars
                data={series as Array<Record<string, unknown>>}
                keys={[
                  { key: "requests", name: "Requests", color: "hsl(var(--chart-1))" },
                  { key: "credits", name: "Credits", color: "hsl(var(--chart-4))" },
                ]}
              />
            </Panel>

            <Panel title="Feature usage" subtitle="Requests and cost by feature">
              {features.length === 0 ? (
                <EmptyState message="No AI usage in this period." />
              ) : (
                <div className="divide-y">
                  {features.map((f) => (
                    <div key={f.feature} className="flex items-center justify-between gap-3 py-2.5 text-sm">
                      <div className="min-w-0">
                        <p className="truncate font-medium">{titleCase(f.feature)}</p>
                        <p className="text-xs text-muted-foreground">{fmtCurrency(f.cost, 3)} cost</p>
                      </div>
                      <span className="font-semibold">{fmtNum(f.count)}</span>
                    </div>
                  ))}
                </div>
              )}
            </Panel>

            <Panel title="Top schools by AI credits">
              {topSchools.length === 0 ? (
                <EmptyState message="No AI usage yet." />
              ) : (
                <div className="divide-y">
                  {topSchools.map((s) => (
                    <div key={s.school_id} className="flex items-center justify-between gap-3 py-2.5 text-sm">
                      <div className="min-w-0">
                        <p className="truncate font-medium">{s.name}</p>
                        <p className="text-xs text-muted-foreground">{fmtNum(s.count)} requests</p>
                      </div>
                      <span className="font-semibold">{fmtNum(s.credits)}</span>
                    </div>
                  ))}
                </div>
              )}
            </Panel>

            <Panel title="Near their AI limits" subtitle="At least 80% of credits used">
              {nearing.length === 0 ? (
                <EmptyState message="No schools near their limits." />
              ) : (
                <div className="space-y-3">
                  {nearing.map((s) => (
                    <div key={s.school_id} className="space-y-1">
                      <div className="flex items-center justify-between text-sm">
                        <span className="truncate font-medium">{s.name}</span>
                        <span className="shrink-0 text-xs text-muted-foreground">
                          {fmtNum(s.used)} / {fmtNum(s.total)}
                        </span>
                      </div>
                      <ProgressBar pct={s.pct} />
                    </div>
                  ))}
                </div>
              )}
            </Panel>
          </div>
        </>
      )}
    </div>
  );
}