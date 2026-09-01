"use client";

import { AlertTriangle, ArrowDownRight, ArrowRight, ArrowUpRight, RotateCw, Sparkles } from "lucide-react";
import Link from "next/link";
import { ReactNode } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// States
// ---------------------------------------------------------------------------

export function WidgetSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn("space-y-3", className)}>
      <Skeleton className="h-4 w-1/3" />
      <Skeleton className="h-20 w-full" />
      <Skeleton className="h-3 w-2/3" />
    </div>
  );
}

export function WidgetEmpty({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border/50 px-6 py-10 text-center">
      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-muted/50">
        <Sparkles className="h-5 w-5 text-muted-foreground/40" />
      </div>
      <p className="mt-3 text-[13px] font-medium text-foreground/70">{title}</p>
      {hint && <p className="mt-1 max-w-xs text-[12px] text-muted-foreground/60">{hint}</p>}
    </div>
  );
}

export function WidgetError({ message, onRetry }: { message?: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed border-destructive/20 px-6 py-10 text-center">
      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-destructive/5">
        <AlertTriangle className="h-5 w-5 text-destructive/60" />
      </div>
      <p className="text-[13px] text-muted-foreground/70">{message ?? "Something went wrong"}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3.5 py-1.5 text-[12px] font-semibold text-primary-foreground shadow-xs transition-all hover:bg-primary/90 active:scale-[0.98]"
        >
          <RotateCw className="h-3.5 w-3.5" /> Try again
        </button>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Widget card — minimal, refined
// ---------------------------------------------------------------------------

export function WidgetCard({
  title,
  icon,
  subtitle,
  actions,
  loading,
  error,
  onRetry,
  empty,
  emptyHint,
  children,
  className,
  bodyClassName,
}: {
  title: ReactNode;
  icon?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  loading?: boolean;
  error?: boolean;
  onRetry?: () => void;
  empty?: boolean;
  emptyHint?: string;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col rounded-xl border border-border/40 bg-card shadow-xs transition-all",
        className,
      )}
    >
      <div className="flex items-start justify-between gap-3 border-b border-border/30 px-4 py-3">
        <div className="min-w-0">
          <h3 className="flex items-center gap-2 text-[13px] font-semibold tracking-tight text-foreground/90">
            {icon}
            {title}
          </h3>
          {subtitle && <p className="mt-0.5 text-[11.5px] text-muted-foreground/60">{subtitle}</p>}
        </div>
        {actions && <div className="flex shrink-0 items-center gap-1.5">{actions}</div>}
      </div>
      <div className={cn("flex-1 p-4", bodyClassName)}>
        {loading ? (
          <WidgetSkeleton />
        ) : error ? (
          <WidgetError onRetry={onRetry} />
        ) : empty ? (
          <WidgetEmpty title="No data yet" hint={emptyHint} />
        ) : (
          children
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// KPI card — clean, typographic
// ---------------------------------------------------------------------------

export function KpiCard({
  label,
  value,
  icon: Icon,
  sub,
  delta,
  deltaLabel,
  loading,
  href,
}: {
  label: string;
  value: ReactNode;
  icon: React.ElementType;
  sub?: string;
  delta?: number | null;
  deltaLabel?: string;
  loading?: boolean;
  href: string;
}) {
  const up = (delta ?? 0) >= 0;
  return (
    <Link href={href} className="group block rounded-xl border border-border/40 bg-card px-4 py-3.5 shadow-xs transition-all hover:border-border/60 hover:shadow-sm">
      <div className="flex items-start justify-between">
        <div className="min-w-0">
          <p className="text-[11px] font-medium text-muted-foreground/60">{label}</p>
          <div className="mt-1 text-[22px] font-bold tracking-tight text-foreground">
            {loading ? <Skeleton className="h-6 w-14" /> : value}
          </div>
        </div>
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-muted/50 text-muted-foreground/50">
          <Icon className="h-4 w-4" />
        </span>
      </div>
      <div className="mt-2 flex items-center gap-2">
        {delta != null && (
          <span
            className={cn(
              "inline-flex items-center gap-0.5 rounded-md px-1.5 py-0.5 text-[10px] font-semibold",
              up ? "bg-success/10 text-success" : "bg-destructive/10 text-destructive",
            )}
          >
            {up ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
            {Math.abs(delta).toFixed(1)}%
          </span>
        )}
        {sub && (
          <span className="flex items-center gap-1 text-[11px] text-muted-foreground/50">
            <span className="truncate">{sub}</span>
            <ArrowRight className="ml-auto h-3 w-3 shrink-0 opacity-0 transition-opacity duration-100 group-hover:opacity-40" />
          </span>
        )}
      </div>
    </Link>
  );
}

// ---------------------------------------------------------------------------
// Readiness ring
// ---------------------------------------------------------------------------

export function ReadinessRing({ pct, size = "md" }: { pct: number | null; size?: "sm" | "md" | "lg" }) {
  const dims = {
    sm: { box: 56, r: 24, stroke: 5, text: "text-sm" },
    md: { box: 88, r: 38, stroke: 7, text: "text-lg" },
    lg: { box: 120, r: 52, stroke: 8, text: "text-2xl" },
  }[size];
  const r = dims.r;
  const c = 2 * Math.PI * r;
  const val = Math.round(pct ?? 0);
  const color =
    pct === null
      ? "hsl(var(--muted))"
      : val >= 90
        ? "hsl(var(--success))"
        : val >= 70
          ? "hsl(var(--warning))"
          : "hsl(var(--destructive))";
  return (
    <div
      className="relative flex items-center justify-center"
      style={{ width: dims.box, height: dims.box }}
    >
      <svg
        className="-rotate-90"
        width={dims.box}
        height={dims.box}
        viewBox={`0 0 ${dims.box} ${dims.box}`}
      >
        <circle
          cx={dims.box / 2}
          cy={dims.box / 2}
          r={r}
          fill="none"
          stroke="hsl(var(--muted))"
          strokeWidth={dims.stroke}
        />
        <circle
          cx={dims.box / 2}
          cy={dims.box / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={dims.stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c - (c * val) / 100}
          className="transition-[stroke-dashoffset] duration-700 ease-out"
        />
      </svg>
      <div className={cn("absolute text-center font-bold", dims.text)}>
        {pct === null ? "—" : `${val}%`}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Relative time
// ---------------------------------------------------------------------------

export function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });
}
