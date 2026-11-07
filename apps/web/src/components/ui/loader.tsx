import type { CSSProperties } from "react";

import { cn } from "@/lib/utils";

/**
 * The one loading mark in Clearis: a double ring turning in opposite
 * directions, with the product name beneath it.
 *
 * Used everywhere something is happening — the first paint, saving a change,
 * processing a result status, publishing — so the same gesture means the same
 * thing on every screen.
 *
 * `tone="inherit"` follows the surrounding text colour, which is what a
 * button needs when its background is the brand colour.
 */
export function Loader({
  className,
  size = 28,
  tone = "brand",
  label = "Loading",
}: {
  className?: string;
  size?: number;
  tone?: "brand" | "inherit";
  label?: string;
}) {
  const ring =
    tone === "inherit"
      ? {
          "--ring-strong": "currentColor",
          "--ring-soft": "color-mix(in srgb, currentColor 45%, transparent)",
        }
      : {
          "--ring-strong": "hsl(var(--primary))",
          "--ring-soft": "hsl(var(--primary) / 0.42)",
        };

  return (
    <span
      role="status"
      aria-label={label}
      className={cn("relative grid place-items-center", className)}
      style={{ width: size, height: size, ...ring } as CSSProperties}
    >
      {/* Outer ring — clockwise. */}
      <span
        className="absolute inset-0 animate-orbit rounded-full border-transparent border-r-[var(--ring-soft)] border-t-[var(--ring-strong)] motion-reduce:animate-none"
        style={{ borderWidth: Math.max(1.5, size * 0.075) }}
      />
      {/* Inner ring — counter-clockwise. */}
      <span
        className="absolute animate-orbit-reverse rounded-full border-transparent border-b-[var(--ring-strong)] border-l-[var(--ring-soft)] motion-reduce:animate-none"
        style={{
          inset: size <= 22 ? "30%" : "26%",
          borderWidth: Math.max(1.5, size * 0.062),
        }}
      />
      {/* Quiet core so the centre does not read as a hole. */}
      <span className="h-[9%] w-[9%] rounded-full bg-[var(--ring-strong)] opacity-70" />
    </span>
  );
}

/**
 * The spinner with the wordmark beneath it — the app's "at rest, coming up"
 * state. Pair it with `LoadingScreen` for a full-page treatment.
 */
export function LoaderMark({
  size = 44,
  text = "Clearis",
  className,
  tone = "brand",
}: {
  size?: number;
  text?: string;
  className?: string;
  tone?: "brand" | "inherit";
}) {
  return (
    <span className={cn("inline-flex flex-col items-center gap-3", className)}>
      <Loader size={size} tone={tone} />
      <span className="text-[11px] font-medium uppercase tracking-[0.3em] text-muted-foreground">
        {text}
      </span>
    </span>
  );
}
