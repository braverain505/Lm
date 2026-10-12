"use client";

import { motion, useReducedMotion } from "framer-motion";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/** The same curve the auth screens use, so motion feels native to the product. */
export const EASE = [0.25, 0.46, 0.45, 0.94] as const;

/**
 * Fade-and-rise once, the first time an element scrolls into view.
 *
 * Marketing copy is the first thing a stranger reads, so the reveal has to be
 * quiet: a short 16px lift, never a slide that delays the text. Anyone who has
 * asked their OS for reduced motion gets the plain element instead.
 */
export function Reveal({
  children,
  className,
  delay = 0,
  y = 16,
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
  y?: number;
}) {
  const reduceMotion = useReducedMotion();
  if (reduceMotion) return <div className={className}>{children}</div>;

  return (
    <motion.div
      initial={{ opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-70px" }}
      transition={{ duration: 0.5, ease: EASE, delay }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

/** Small uppercase kicker that opens a section. */
export function SectionLabel({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border border-border/70 bg-card/70 px-3 py-1 text-[10.5px] font-semibold uppercase tracking-[0.14em] text-muted-foreground backdrop-blur",
        className,
      )}
    >
      {children}
    </span>
  );
}

export function SectionHeading({
  title,
  description,
  align = "left",
  className,
}: {
  title: ReactNode;
  description?: ReactNode;
  align?: "left" | "center";
  className?: string;
}) {
  return (
    <div
      className={cn(
        align === "center" ? "mx-auto max-w-2xl text-center" : "max-w-2xl",
        className,
      )}
    >
      <h2 className="text-[26px] font-bold leading-[1.15] tracking-tight text-foreground sm:text-[32px] lg:text-[38px]">
        {title}
      </h2>
      {description && (
        <p className="mt-4 text-[14.5px] leading-relaxed text-muted-foreground sm:text-[15.5px]">
          {description}
        </p>
      )}
    </div>
  );
}

/**
 * The brand backdrop: two soft primary glows over a faint grid, masked so the
 * grid fades out before it reaches the content.
 */
export function AuroraBackdrop({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={cn("pointer-events-none absolute inset-0 overflow-hidden", className)}
    >
      <div className="absolute -left-[18%] -top-[28%] h-[620px] w-[620px] rounded-full bg-primary/[0.09] blur-[130px]" />
      <div className="absolute -right-[12%] top-[6%] h-[520px] w-[520px] rounded-full bg-chart-5/[0.09] blur-[120px]" />
      <div
        className="absolute inset-0 opacity-[0.4] [mask-image:radial-gradient(ellipse_at_50%_0%,black,transparent_70%)]"
        style={{
          backgroundImage:
            "linear-gradient(to right, hsl(var(--border) / 0.8) 1px, transparent 1px), linear-gradient(to bottom, hsl(var(--border) / 0.8) 1px, transparent 1px)",
          backgroundSize: "48px 48px",
        }}
      />
    </div>
  );
}
