"use client";

import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export function fmtCurrency(v: number | string | null | undefined, digits = 0): string {
  const n = typeof v === "string" ? Number(v) : (v ?? 0);
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: digits,
  }).format(n);
}

export function fmtNum(v: number | string | null | undefined): string {
  const n = typeof v === "string" ? Number(v) : (v ?? 0);
  return new Intl.NumberFormat("en-US").format(n);
}

export function fmtDate(iso?: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

export function fmtDateTime(iso?: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

export function titleCase(s: string): string {
  return s.replace(/[_-]+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

const STATUS_VARIANT: Record<string, "success" | "warning" | "destructive" | "info" | "muted" | "outline"> = {
  active: "success",
  operational: "success",
  resolved: "success",
  ok: "success",
  open: "info",
  in_progress: "info",
  awaiting_school: "warning",
  trial: "info",
  past_due: "warning",
  expired: "muted",
  cancelled: "muted",
  pending: "muted",
  suspended: "destructive",
  degraded: "warning",
  down: "destructive",
  high: "destructive",
  critical: "destructive",
  medium: "warning",
  low: "info",
  enabled: "success",
  disabled: "muted",
  failed: "destructive",
};

export function StatusBadge({ status }: { status: string }) {
  const variant = STATUS_VARIANT[status] ?? "outline";
  return <Badge variant={variant}>{titleCase(status)}</Badge>;
}

export function StatCard({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  accent?: string;
}) {
  return (
    <Card>
      <CardContent className="space-y-1 p-4">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>
        <p className={cn("text-2xl font-bold tracking-tight", accent)}>{value}</p>
        {sub && <p className="text-xs text-muted-foreground">{sub}</p>}
      </CardContent>
    </Card>
  );
}

export function Panel({
  title,
  subtitle,
  action,
  children,
  className,
}: {
  title?: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <Card className={className}>
      {(title || action) && (
        <CardHeader className="flex-row items-start justify-between space-y-0">
          <div className="space-y-0.5">
            {title && <CardTitle className="text-sm">{title}</CardTitle>}
            {subtitle && <p className="text-xs text-muted-foreground">{subtitle}</p>}
          </div>
          {action}
        </CardHeader>
      )}
      <CardContent>{children}</CardContent>
    </Card>
  );
}

export function PanelSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-8 w-full" />
      ))}
    </div>
  );
}

export function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center gap-2 py-10 text-center">
      <p className="text-sm text-muted-foreground">{message}</p>
    </div>
  );
}

export function ProgressBar({ pct, className }: { pct: number; className?: string }) {
  const tone = pct >= 90 ? "bg-destructive" : pct >= 70 ? "bg-warning" : "bg-primary";
  return (
    <div className={cn("h-1.5 w-full overflow-hidden rounded-full bg-muted", className)}>
      <div className={cn("h-full rounded-full transition-all", tone)} style={{ width: `${Math.min(100, Math.max(0, pct))}%` }} />
    </div>
  );
}