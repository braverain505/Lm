"use client";

import { useState } from "react";

import { Donut, SeriesBars, TrendArea } from "@/components/platform-charts";
import { EmptyState, Panel, PanelSkeleton, StatCard, StatusBadge, fmtCurrency, fmtDateTime, fmtNum, titleCase } from "@/components/platform-utils";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useSaRevenue } from "@/hooks/use-superadmin";

const RANGES = ["7d", "30d", "90d", "6m", "12m", "all"];

export default function SuperAdminRevenuePage() {
  const [range, setRange] = useState("12m");
  const [plan, setPlan] = useState("all");
  const [source, setSource] = useState("all");
  const { data, isLoading } = useSaRevenue({
    range,
    plan: plan === "all" ? undefined : plan,
    source: source === "all" ? undefined : source,
  });

  const metrics = (data?.metrics ?? {}) as Record<string, number | string>;
  const series = (data?.series ?? []) as Array<{ period: string; subscription: number; ai: number; total: number }>;
  const byPlan = (data?.by_plan ?? []) as Array<{ plan: string; code: string; schools: number; mrr: number; pct: number }>;
  const bySource = (data?.by_source ?? []) as Array<{ source: string; amount: number }>;
  const transactions = (data?.transactions ?? []) as Array<{ id: string; school_id: string; school_name: string; event_type: string; amount: number; status: string; created_at: string }>;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-2">
        {RANGES.map((r) => (
          <Button key={r} size="sm" variant={range === r ? "default" : "outline"} onClick={() => setRange(r)}>
            {r}
          </Button>
        ))}
        <div className="ml-auto flex gap-2">
          <Select value={plan} onValueChange={setPlan}>
            <SelectTrigger className="h-8 w-36">
              <SelectValue placeholder="Plan" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All plans</SelectItem>
              <SelectItem value="Trial">Trial</SelectItem>
              <SelectItem value="Starter">Starter</SelectItem>
              <SelectItem value="Professional">Professional</SelectItem>
              <SelectItem value="Enterprise">Enterprise</SelectItem>
            </SelectContent>
          </Select>
          <Select value={source} onValueChange={setSource}>
            <SelectTrigger className="h-8 w-36">
              <SelectValue placeholder="Source" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All sources</SelectItem>
              <SelectItem value="subscription">Subscription</SelectItem>
              <SelectItem value="ai">AI</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {isLoading ? (
        <PanelSkeleton rows={6} />
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="MRR" value={fmtCurrency(metrics.mrr)} />
            <StatCard label="ARR" value={fmtCurrency(metrics.arr)} />
            <StatCard label="Revenue this month" value={fmtCurrency(metrics.revenue_month)} />
            <StatCard label="Outstanding" value={fmtCurrency(metrics.outstanding)} sub={`${fmtNum(metrics.failed_payments)} failed payments`} accent="text-destructive" />
          </div>

          <div className="grid gap-6 lg:grid-cols-3">
            <Panel title="Revenue trend" subtitle="Subscription vs AI income" className="lg:col-span-2">
              <TrendArea
                data={series as Array<Record<string, unknown>>}
                keys={[
                  { key: "total", name: "Total", color: "hsl(var(--chart-1))" },
                  { key: "subscription", name: "Subscription", color: "hsl(var(--chart-3))" },
                  { key: "ai", name: "AI", color: "hsl(var(--chart-4))" },
                ]}
              />
            </Panel>

            <Panel title="Revenue by plan" subtitle="MRR split">
              {byPlan.length === 0 ? (
                <EmptyState message="No plan revenue." />
              ) : (
                <Donut data={byPlan as Array<Record<string, unknown>>} dataKey="mrr" nameKey="plan" />
              )}
            </Panel>

            <Panel title="Revenue by source" className="lg:col-span-3">
              {bySource.length === 0 ? (
                <EmptyState message="No revenue data." />
              ) : (
                <SeriesBars
                  data={bySource.map((s) => ({ period: titleCase(s.source), amount: s.amount })) as Array<Record<string, unknown>>}
                  keys={[{ key: "amount", name: "Amount", color: "hsl(var(--chart-2))" }]}
                  suffix=""
                />
              )}
            </Panel>
          </div>

          <Panel title="Recent transactions" subtitle="Latest subscription events">
            {transactions.length === 0 ? (
              <EmptyState message="No transactions yet." />
            ) : (
              <div className="divide-y">
                {transactions.map((t) => (
                  <div key={t.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5 text-sm">
                    <div className="min-w-0">
                      <p className="truncate font-medium">{t.school_name}</p>
                      <p className="text-xs capitalize text-muted-foreground">
                        {titleCase(t.event_type)} · {fmtDateTime(t.created_at)}
                      </p>
                    </div>
                    <div className="flex items-center gap-3">
                      {t.amount > 0 && <span className="font-semibold">{fmtCurrency(t.amount)}</span>}
                      <StatusBadge status={t.status} />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Panel>
        </>
      )}
    </div>
  );
}