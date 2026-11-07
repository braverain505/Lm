"use client";

import { AnimatePresence, motion } from "framer-motion";

import { LoaderMark } from "@/components/ui/loader";
import { cn } from "@/lib/utils";

interface LoadingScreenProps {
  /** Wordmark under the spinner. Defaults to the product name. */
  text?: string;
  className?: string;
  isLoading?: boolean;
  onComplete?: () => void;
}

/**
 * The product's single loading treatment: the double-ring spinner with the
 * Clearis wordmark beneath it.
 *
 * Used for the first paint and for any background work (saving changes,
 * processing a result status, publishing) that runs long enough to be worth a
 * pause.
 */
export function LoadingScreen({
  text = "Clearis",
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
          <LoaderMark size={46} text={text} />
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/** Same treatment, for surfaces that render it inline instead of globally. */
export function LoadingOverlay() {
  return (
    <div className="fixed inset-0 z-[80] grid place-items-center bg-background/70 backdrop-blur-sm print:hidden">
      <LoaderMark size={46} />
    </div>
  );
}