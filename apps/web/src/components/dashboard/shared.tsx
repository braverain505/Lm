"use client";

import { AlertTriangle, ArrowDownRight, ArrowRight, ArrowUpRight, RotateCw, Sparkles } from "lucide-react";
import { motion } from "framer-motion";
import Link from "next/link";
import { ReactNode } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

const ease = [0.25, 0.46, 0.45, 0.94] as const;

// ---------------------------------------------------------------------------
// States
// ---------------------------------------------------------------------------

export function WidgetSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn("space-y-3", className)}>
      <Skeleton className="h-4 w-1/3 rounded-md" />
      <Skeleton className="h-20 w-full rounded-lg" />
      <Skeleton className="h-3 w-2/3 rounded-md" />
    </div>
  );
}

export function WidgetEmpty({ title, hint }: { title: string; hint?: string }) {
  return (
    <motion.div
      className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border/40 px-6 py-12 text-center"
      initial={{ opacity: 0, scale: 0.97 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3, ease }}
    >
      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-muted/40">
        <Sparkles className="h-5 w-5 text-muted-foreground/30" />
      </div>
      <p className="mt-3 text-[13px] font-medium text-foreground/60">{title}</p>
      {hint && <p className="mt-1.5 max-w-xs text-[12px] leading-relaxed text-muted-foreground/50">{hint}</p>}
    </motion.div>
  );
}

export function WidgetError({ message, onRetry }: { message?: string; onRetry?: () => void }) {
  return (
    <motion.div
      className="flex flex-col items-center gap-3 rounded-xl border border-dashed border-destructive/15 px-6 py-12 text-center"
      initial={{ opacity: 0, scale: 0.97 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3, ease }}
    >
      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-destructive/5">
        <AlertTriangle className="h-5 w-5 text-destructive/50" />
      </div>
      <p className="text-[13px] text-muted-foreground/60">{message ?? "Something went wrong"}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3.5 py-1.5 text-[12px] font-semibold text-primary-foreground shadow-xs transition-all duration-200 hover:bg-primary-hover hover:shadow-sm active:scale-[0.97]"
        >
          <RotateCw className="h-3.5 w-3.5" /> Try again
        </button>
      )}
    </motion.div>
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
    <motion.div
      className={cn(
        "flex flex-col rounded-xl border border-border/40 bg-card shadow-xs transition-[border-color,box-shadow] duration-200 hover:border-border/60 hover:shadow-card",
        className,
      )}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease }}
    >
      <div className="flex items-start justify-between gap-3 border-b border-border/20 px-5 py-3.5">
        <div className="min-w-0">
          <h3 className="flex items-center gap-2 text-[13px] font-semibold tracking-tight text-foreground">
            {icon}
            {title}
          </h3>
          {subtitle && <p className="mt-0.5 text-[11.5px] text-muted-foreground/50">{subtitle}</p>}
        </div>
        {actions && <div className="flex shrink-0 items-center gap-1.5">{actions}</div>}
      </div>
      <div className={cn("flex-1 p-5", bodyClassName)}>
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
    </motion.div>
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
    <Link href={href} className="group block rounded-xl border border-border/40 bg-card px-5 py-4 shadow-xs transition-[border-color,box-shadow,transform] duration-200 hover:border-border/60 hover:shadow-card hover:-translate-y-[1px]">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground/50">{label}</p>
          <div className="mt-1.5 text-[24px] font-bold tracking-tight text-foreground">
            {loading ? <Skeleton className="h-7 w-16 rounded-md" /> : value}
          </div>
          {delta != null && (
            <div className="mt-2 flex items-center gap-1.5">
              <span
                className={cn(
                  "inline-flex items-center gap-0.5 rounded-md px-1.5 py-0.5 text-[10px] font-semibold",
                  up ? "bg-success/10 text-success" : "bg-destructive/10 text-destructive",
                )}
              >
                {up ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
                {Math.abs(delta).toFixed(1)}%
              </span>
              {deltaLabel && <span className="text-[10px] text-muted-foreground/50">{deltaLabel}</span>}
            </div>
          )}
          {sub && !delta && (
            <p className="mt-2 text-[11px] text-muted-foreground/45">{sub}</p>
          )}
        </div>
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-muted/40 text-muted-foreground/40 transition-colors duration-200 group-hover:bg-primary/10 group-hover:text-primary/70">
          <Icon className="h-4 w-4" />
        </span>
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
