"use client";

import { cn } from "@/lib/utils";

interface ReadinessBarProps {
  /** Percentage 0–100. */
  value: number;
  /** Rendered height. */
  size?: "sm" | "md" | "lg";
  /** Show the animated sheen while still in progress (value < 100). */
  sheen?: boolean;
  className?: string;
}

function toneFor(pct: number): string {
  if (pct >= 100) return "from-emerald-400 to-emerald-600";
  if (pct >= 70) return "from-sky-400 to-blue-600";
  if (pct >= 50) return "from-amber-400 to-orange-500";
  return "from-rose-400 to-red-600";
}

function glowFor(pct: number): string {
  if (pct >= 100) return "shadow-[0_0_10px_rgba(16,185,129,0.55)]";
  if (pct >= 70) return "shadow-[0_0_10px_rgba(14,165,233,0.5)]";
  if (pct >= 50) return "shadow-[0_0_10px_rgba(245,158,11,0.45)]";
  return "shadow-[0_0_10px_rgba(244,63,94,0.45)]";
}

/**
 * Sleek, fully-rounded progress bar for result-readiness tracking.
 * Gradient fill with a soft glow, an inset-ring track, and an optional
 * animated sheen that runs while the bar is still filling up.
 */
export function ReadinessBar({
  value,
  size = "md",
  sheen = true,
  className,
}: ReadinessBarProps) {
  const clamped = Math.max(0, Math.min(100, value));
  const done = clamped >= 100;

  return (
    <div
      role="progressbar"
      aria-valuenow={Math.round(clamped)}
      aria-valuemin={0}
      aria-valuemax={100}
      className={cn(
        "relative w-full overflow-hidden rounded-full bg-muted shadow-[inset_0_1px_2px_rgba(0,0,0,0.08)] ring-1 ring-inset ring-black/[0.04]",
        size === "sm" && "h-2",
        size === "md" && "h-3",
        size === "lg" && "h-4",
        className,
      )}
    >
      <div
        className={cn(
          "relative h-full overflow-hidden rounded-full bg-gradient-to-r transition-[width] duration-700 ease-out",
          toneFor(clamped),
          glowFor(clamped),
        )}
        style={{ width: `${clamped}%` }}
      >
        {sheen && !done && (
          <span className="readiness-sheen pointer-events-none absolute inset-0" />
        )}
      </div>
    </div>
  );
}
