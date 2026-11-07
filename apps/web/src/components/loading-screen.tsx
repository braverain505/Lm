"use client";

import { AnimatePresence, motion } from "framer-motion";

import { Loader } from "@/components/ui/loader";
import { cn } from "@/lib/utils";

interface LoadingScreenProps {
  /** Optional line under the spinner. Omitted by default. */
  text?: string;
  className?: string;
  isLoading?: boolean;
  onComplete?: () => void;
}

/**
 * The product's single loading treatment: the ring spinner.
 *
 * Used for the first paint and for any background work (saving changes,
 * processing a result status, publishing) that runs long enough to be worth a
 * pause. There is deliberately only one mark — no branded wordmark, no
 * alternate animation — so "loading" looks the same everywhere in Clearis.
 */
export function LoadingScreen({
  text,
  className,
  isLoading = true,
  onComplete,
}: LoadingScreenProps) {
  return (
    <AnimatePresence onExitComplete={onComplete}>
      {isLoading && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.18, ease: "easeOut" }}
          className={cn(
            "fixed inset-0 z-[80] grid place-items-center bg-background/70 backdrop-blur-sm print:hidden",
            className,
          )}
        >
          <div className="flex flex-col items-center gap-3">
            <Loader className="h-9 w-9 border-[2.5px]" />
            {text && (
              <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-muted-foreground">
                {text}
              </p>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/** Same treatment, for surfaces that render it inline instead of globally. */
export function LoadingOverlay() {
  return (
    <div className="fixed inset-0 z-[80] grid place-items-center bg-background/70 backdrop-blur-sm print:hidden">
      <Loader className="h-9 w-9 border-[2.5px]" />
    </div>
  );
}