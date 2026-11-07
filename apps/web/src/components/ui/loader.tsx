import { cn } from "@/lib/utils";

/**
 * The one loading mark in Clearis.
 *
 * A thin rotating ring, used everywhere something is happening — page loads,
 * saving a change, processing a result status, publishing. Keeping a single
 * mark is deliberate: the same gesture means the same thing on every screen.
 *
 * `tone="inherit"` follows the surrounding text colour, which is what a
 * button needs when its background is the brand colour.
 */
export function Loader({
  className,
  tone = "brand",
}: {
  className?: string;
  tone?: "brand" | "inherit";
}) {
  return (
    <div
      role="status"
      aria-label="Loading"
      className={cn(
        "h-6 w-6 animate-spin rounded-full border-2",
        tone === "brand" && "border-primary/35 border-t-primary",
        className,
      )}
      style={
        tone === "inherit"
          ? {
              borderColor: "color-mix(in srgb, currentColor 28%, transparent)",
              borderTopColor: "currentColor",
            }
          : undefined
      }
    />
  );
}