"use client";

import { AlertTriangle } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { EmptyState, Panel, PanelSkeleton, StatCard, StatusBadge, fmtDateTime, titleCase } from "@/components/platform-utils";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useSaIssues } from "@/hooks/use-superadmin";

export default function SuperAdminIssuesPage() {
  const [severity, setSeverity] = useState("all");
  const [status, setStatus] = useState("all");
  const { data, isLoading } = useSaIssues({
    severity: severity === "all" ? undefined : severity,
    status: status === "all" ? undefined : status,
  });

  const counts = (data?.counts ?? {}) as Record<string, number>;
  const items = (data?.items ?? []) as Array<{
    id: string; severity: string; service: string; title: string; detail: string;
    ts: string | null; affected_tenants: number; status: string; action: string; href: string | null;
  }>;

  return (
    <div className="space-y-6">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <StatCard label="Critical" value={counts.critical} accent="text-destructive" />
        <StatCard label="High" value={counts.high} accent="text-destructive" />
        <StatCard label="Medium" value={counts.medium} accent="text-warning" />
        <StatCard label="Low" value={counts.low} />
        <StatCard label="Open" value={counts.open} />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Select value={severity} onValueChange={setSeverity}>
          <SelectTrigger className="h-9 w-36">
            <SelectValue placeholder="Severity" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All severities</SelectItem>
            <SelectItem value="critical">Critical</SelectItem>
            <SelectItem value="high">High</SelectItem>
            <SelectItem value="medium">Medium</SelectItem>
            <SelectItem value="low">Low</SelectItem>
          </SelectContent>
        </Select>
        <Select value={status} onValueChange={setStatus}>
          <SelectTrigger className="h-9 w-36">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="open">Open</SelectItem>
            <SelectItem value="resolved">Resolved</SelectItem>
            <SelectItem value="in_progress">In progress</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {isLoading ? (
        <PanelSkeleton rows={6} />
      ) : items.length === 0 ? (
        <div className="rounded-xl border bg-card">
          <EmptyState message="No issues match these filters." />
        </div>
      ) : (
        <Panel title="Issues" subtitle="Derived from live platform state">
          <div className="divide-y">
            {items.map((i) => (
              <div key={i.id} className="flex flex-wrap items-start justify-between gap-3 py-3">
                <div className="flex min-w-0 flex-1 items-start gap-3">
                  <span
                    className={
                      i.severity === "critical" || i.severity === "high"
                        ? "mt-0.5 text-destructive"
                        : "mt-0.5 text-warning"
                    }
                  >
                    <AlertTriangle className="h-4 w-4" />
                  </span>
                  <div className="min-w-0">
                    <p className="flex flex-wrap items-center gap-2 font-medium">
                      {i.title}
                      <StatusBadge status={i.status} />
                    </p>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {titleCase(i.service)} · {fmtDateTime(i.ts)} · {i.affected_tenants} tenant(s)
                    </p>
                    <p className="mt-1 text-[13px] text-muted-foreground">{i.detail}</p>
                    {i.action && (
                      <p className="mt-1 text-xs font-medium text-foreground">
                        Suggested action: {i.action}
                      </p>
                    )}
                  </div>
                </div>
                <div className="flex shrink-0 flex-col items-end gap-2">
                  <StatusBadge status={i.severity} />
                  {i.href && (
                    <Button size="sm" variant="outline" asChild>
                      <Link href={i.href}>Open school</Link>
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Panel>
      )}
    </div>
  );
}