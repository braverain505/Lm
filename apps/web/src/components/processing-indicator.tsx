"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useIsFetching, useIsMutating } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { OrbitLoader } from "@/components/ui/loader";
import { cn } from "@/lib/utils";

/**
 * True while any cached query is refetching or any mutation is in flight.
 * React Query already knows about background work, so this needs no wiring at
 * the call site — every save, import and refresh feeds it automatically.
 */
export function useIsProcessing() {
  const fetching = useIsFetching();
  const mutating = useIsMutating();
  return fetching + mutating > 0;
}

/**
 * The global "something is happening" line.
 *
 * A two-pixel gradient sweeps across the very top of the viewport whenever any
 * request is in flight. It is deliberately silent: no modal, no backdrop, no
 * page jump — the screen stays usable while it works. When the last request
 * settles the sweep resolves into a full line and fades out, so the eye gets a
 * clear "done" instead of a disappearing sliver.
 */
export function ProcessingBar() {
  const busy = useIsProcessing();
  const [visible, setVisible] = useState(false);
  const reduce = useReducedMotion();

  useEffect(() => {
    if (busy) {
      setVisible(true);
      return;
    }
    // Hold long enough for the completion state to register.
    const timeout = setTimeout(() => setVisible(false), 320);
    return () => clearTimeout(timeout);
  }, [busy]);

  return (
    <div
      aria-hidden
      className="pointer-events-none fixed inset-x-0 top-0 z-[100] h-[2px] print:hidden"
    >
      <AnimatePresence>
        {visible && (
          <motion.div
            key="processing"
            className="relative h-full w-full overflow-hidden"
            initial={{ opacity: 0 }}
            animate={{ opacity: busy ? 1 : 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.24, ease: "easeOut" }}
          >
            {busy ? (
              <motion.span
                className="absolute inset-y-0 w-1/3 rounded-full bg-gradient-to-r from-transparent via-primary to-transparent"
                style={{ boxShadow: "0 0 12px hsl(var(--primary) / 0.55)" }}
                animate={
                  reduce ? { opacity: [0.35, 1, 0.35] } : { x: ["-120%", "360%"] }
                }
                transition={
                  reduce
                    ? { duration: 1.8, repeat: Infinity, ease: "easeInOut" }
                    : { duration: 1.35, repeat: Infinity, ease: "easeInOut" }
                }
              />
            ) : (
              <span className="absolute inset-0 bg-gradient-to-r from-primary/50 via-primary to-primary/50" />
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/**
 * Blocking treatment for work the user must wait on (imports, bulk
 * publishing, generating a term's report cards). Everything else should use
 * `ProcessingBar` or an inline `OrbitLoader` instead.
 */
export function ProcessingOverlay({
  show,
  label = "Working",
  detail,
  className,
}: {
  show: boolean;
  label?: string;
  detail?: string;
  className?: string;
}) {
  return (
    <AnimatePresence>
      {show && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.18 }}
          className={cn(
            "fixed inset-0 z-[90] grid place-items-center bg-background/60 backdrop-blur-md print:hidden",
            className,
          )}
        >
          <motion.div
            initial={{ opacity: 0, y: 6, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 4, scale: 0.98 }}
            transition={{ duration: 0.2, ease: [0.25, 0.46, 0.45, 0.94] }}
            className="flex items-center gap-4 rounded-2xl border border-border/60 bg-card/90 py-4 pl-4 pr-6 shadow-pop"
          >
            <OrbitLoader size={30} label={label} />
            <div className="space-y-0.5">
              <p className="text-[13.5px] font-semibold tracking-tight">{label}</p>
              {detail && (
                <p className="text-[12px] text-muted-foreground">{detail}</p>
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}