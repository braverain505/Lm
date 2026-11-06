import { cn } from "@/lib/utils";

/**
 * The product's loading language.
 *
 * Three marks, one idea: something is happening, and it is under control.
 * Motion is linear and slow so it reads as instrumentation rather than a
 * spinner begging for attention. All of them respect `prefers-reduced-motion`.
 */

/** Legacy ring spinner — kept so existing call sites keep working. */
export function Loader({ className }: { className?: string }) {
  return (
    <div
      role="status"
      aria-label="Loading"
      className={cn(
        "h-6 w-6 animate-spin rounded-full border-2 border-primary/35 border-t-primary",
        className,
      )}
    />
  );
}

/**
 * Signature mark: two counter-rotating arcs around a softly pulsing core.
 * Use it wherever a surface is doing real work (imports, publishing,
 * generating) — it is quiet enough to sit next to a heading.
 */
export function OrbitLoader({
  className,
  size = 28,
  label = "Working",
}: {
  className?: string;
  size?: number;
  label?: string;
}) {
  return (
    <span
      role="status"
      aria-label={label}
      className={cn("relative inline-grid place-items-center align-middle", className)}
      style={{ width: size, height: size }}
    >
      <span className="absolute inset-0 rounded-full border border-primary/12" />
      <span className="absolute inset-0 animate-orbit rounded-full border-[1.5px] border-transparent border-r-primary/45 border-t-primary motion-reduce:animate-none" />
      <span className="absolute inset-[24%] animate-orbit-reverse rounded-full border border-transparent border-b-primary/70 border-l-primary/25 motion-reduce:animate-none" />
      <span className="h-[16%] w-[16%] animate-pulse-soft rounded-full bg-primary shadow-[0_0_10px_hsl(var(--primary)/0.75)] motion-reduce:animate-none" />
    </span>
  );
}

/** Three dots for compact states: "Saving", "Syncing", a table footer. */
export function DotsLoader({
  className,
  label = "Working",
}: {
  className?: string;
  label?: string;
}) {
  return (
    <span
      role="status"
      aria-label={label}
      className={cn("inline-flex items-center gap-1 align-middle", className)}
    >
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="h-1 w-1 animate-pulse-soft rounded-full bg-current motion-reduce:animate-none"
          style={{ animationDelay: `${i * 0.18}s` }}
        />
      ))}
    </span>
  );
}

/**
 * Hairline indeterminate rule. Sits at the bottom of a card or above a table
 * without moving any layout — the same gesture as the global top bar, scaled
 * down to one component.
 */
export function ProgressLine({
  active = true,
  className,
}: {
  active?: boolean;
  className?: string;
}) {
  return (
    <div
      aria-hidden
      className={cn(
        "relative h-px w-full overflow-hidden bg-border/50 transition-opacity duration-300",
        active ? "opacity-100" : "opacity-0",
        className,
      )}
    >
      <span className="absolute inset-y-0 w-1/3 animate-progress-sweep rounded-full bg-gradient-to-r from-transparent via-primary to-transparent motion-reduce:animate-none" />
    </div>
  );
}

/** Small inline chip that pairs a label with the dots. */
export function ProcessingPill({
  label = "Saving",
  className,
}: {
  label?: string;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border border-border/60 bg-background/70 px-2 py-0.5 text-[11px] font-medium text-muted-foreground backdrop-blur",
        className,
      )}
    >
      <DotsLoader label={label} />
      {label}
    </span>
  );
}