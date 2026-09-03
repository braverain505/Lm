"use client";

import { cn } from "@/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-lg bg-muted/40",
        className,
      )}
      aria-hidden
    >
      {/* Shimmer gradient overlay */}
      <div className="absolute inset-0 -translate-x-full animate-[shimmer_2s_infinite] bg-gradient-to-r from-transparent via-white/40 to-transparent dark:via-white/[0.04]" />
    </div>
  );
}

/* ─── Dashboard skeleton cards ──────────────────────────────────────────── */

export function DashboardCardSkeleton() {
  return (
    <div className="rounded-2xl border border-white/60 bg-white p-5 shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
      <div className="flex items-start justify-between">
        <div className="flex-1 space-y-2">
          <Skeleton className="h-3 w-20 rounded-md" />
          <Skeleton className="h-7 w-24 rounded-md" />
          <Skeleton className="h-4 w-16 rounded-md" />
        </div>
        <Skeleton className="h-10 w-10 rounded-xl" />
      </div>
    </div>
  );
}

export function DashboardChartSkeleton() {
  return (
    <div className="rounded-2xl border border-white/60 bg-white p-6 shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
      <div className="mb-4 space-y-1.5">
        <Skeleton className="h-4 w-32 rounded-md" />
        <Skeleton className="h-3 w-48 rounded-md" />
      </div>
      <Skeleton className="h-[180px] w-full rounded-xl" />
    </div>
  );
}

export function DashboardListSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="rounded-2xl border border-white/60 bg-white shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
      <div className="border-b border-border/20 px-5 py-4">
        <Skeleton className="h-4 w-28 rounded-md" />
        <Skeleton className="mt-1.5 h-3 w-40 rounded-md" />
      </div>
      <div className="divide-y divide-border/15">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="flex items-center gap-3 px-5 py-3.5">
            <Skeleton className="h-2 w-2 shrink-0 rounded-full" />
            <div className="flex-1 space-y-1.5">
              <Skeleton className="h-3 w-32 rounded-md" />
              <Skeleton className="h-2.5 w-24 rounded-md" />
            </div>
            <Skeleton className="h-5 w-14 rounded-md" />
          </div>
        ))}
      </div>
    </div>
  );
}

export function DashboardQuickActionsSkeleton() {
  return (
    <div className="rounded-2xl border border-white/60 bg-white p-6 shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
      <div className="mb-4 space-y-1.5">
        <Skeleton className="h-4 w-24 rounded-md" />
        <Skeleton className="h-3 w-36 rounded-md" />
      </div>
      <div className="grid grid-cols-3 gap-3 sm:grid-cols-6">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="flex flex-col items-center gap-2.5 rounded-xl p-3">
            <Skeleton className="h-12 w-12 rounded-xl" />
            <Skeleton className="h-2.5 w-14 rounded-md" />
          </div>
        ))}
      </div>
    </div>
  );
}
