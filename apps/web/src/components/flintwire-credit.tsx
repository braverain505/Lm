import { cn } from "@/lib/utils";

/**
 * Flintwire attribution.
 *
 * Clearis is a product of Flintwire Technologies, so every surface carrying the
 * Clearis brand also credits the parent brand: the auth pages, both dashboards
 * and the public result portal.
 *
 * Deliberately quiet — one line, small, muted, and below the fold of the actual
 * content — so it reads as a signature rather than competing with the school's
 * own branding (schools can replace the logo and see their own name in the
 * chrome, and this should never look like it belongs to them).
 */
export function FlintwireCredit({
  className,
  tone = "muted",
}: {
  className?: string;
  /** `onDark` is for the sidebar / dark footer surfaces. */
  tone?: "muted" | "onDark";
}) {
  const onDark = tone === "onDark";

  return (
    <p
      className={cn(
        "text-center text-[11px] leading-relaxed",
        onDark ? "text-white/40" : "text-muted-foreground/60",
        className,
      )}
    >
      Clearis is a product of{" "}
      <a
        href="https://flintwire.com"
        target="_blank"
        rel="noreferrer noopener"
        className={cn(
          "font-semibold transition-colors",
          onDark ? "text-white/75 hover:text-white" : "text-muted-foreground hover:text-foreground",
        )}
      >
        Flintwire Technologies
      </a>
    </p>
  );
}
