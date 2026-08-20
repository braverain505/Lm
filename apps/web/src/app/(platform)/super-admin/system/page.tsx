"use client";

import { useState } from "react";

import { EmptyState, Panel, PanelSkeleton, StatusBadge, fmtDateTime, titleCase } from "@/components/platform-utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useSaActivity, useSaHealth } from "@/hooks/use-superadmin";

export default function SuperAdminSystemPage() {
  const [category, setCategory] = useState("all");
  const { data: health, isLoading: healthLoading } = useSaHealth();
  const { data: activity = [], isLoading: activityLoading } = useSaActivity({ limit: 30, category: category === "all" ? undefined : category });

  const services = health?.services ?? [];
  const activities = activity as Array<{
    id: string; ts: string; school_id: string | null; school_name: string | null;
    actor: string; action: string; category: string; severity: string; detail: string; href: string | null;
  }>;

  return (
    <div className="space-y-6">
      <Panel title="Service health" subtitle={`Overall: ${titleCase(health?.overall ?? "…")} · checked ${fmtDateTime(health?.last_checked)}`}>
        {healthLoading ? (
          <PanelSkeleton rows={6} />
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {services.map((s) => (
              <div key={s.service} className="rounded-xl border bg-muted/30 p-4">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-semibold">{s.label}</p>
                  <StatusBadge status={s.status} />
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  {s.response_ms != null ? `${s.response_ms}ms` : "n/a"}
                  {s.last_checked ? ` · ${fmtDateTime(s.last_checked)}` : ""}
                </p>
                {"note" in s && (s as { note?: string | null }).note && (
                  <p className="mt-1 text-[11px] text-muted-foreground/70">{(s as { note: string }).note}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </Panel>

      <Panel
        title="Activity feed"
        subtitle="Recent platform events"
        action={
          <Select value={category} onValueChange={setCategory}>
            <SelectTrigger className="h-8 w-40">
              <SelectValue placeholder="Category" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All activity</SelectItem>
              <SelectItem value="ai">AI</SelectItem>
              <SelectItem value="billing">Billing</SelectItem>
              <SelectItem value="platform">Platform</SelectItem>
            </SelectContent>
          </Select>
        }
      >
        {activityLoading ? (
          <PanelSkeleton rows={6} />
        ) : activities.length === 0 ? (
          <EmptyState message="No activity to show." />
        ) : (
          <div className="divide-y">
            {activities.map((a) => (
              <div key={a.id} className="flex items-start gap-3 py-2.5">
                <span
                  className={
                    a.category === "billing"
                      ? "mt-1.5 h-2 w-2 shrink-0 rounded-full bg-chart-6"
                      : a.category === "ai"
                        ? "mt-1.5 h-2 w-2 shrink-0 rounded-full bg-chart-4"
                        : "mt-1.5 h-2 w-2 shrink-0 rounded-full bg-chart-1"
                  }
                />
                <div className="min-w-0 flex-1">
                  <p className="text-[13px] font-medium capitalize leading-snug">
                    {titleCase(a.action)}
                    <span className="ml-2 text-muted-foreground">{a.school_name ?? ""}</span>
                  </p>
                  <p className="truncate text-xs text-muted-foreground">{a.detail}</p>
                  <p className="text-[11px] text-muted-foreground/70">
                    {a.actor} · {fmtDateTime(a.ts)}
                  </p>
                </div>
                <Badge variant="outline">{titleCase(a.category)}</Badge>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}