"use client";

import { motion, AnimatePresence } from "framer-motion";
import { Megaphone, X, ArrowRight } from "lucide-react";
import Link from "next/link";
import { useState, useEffect } from "react";

const DISMISS_KEY = "clearis-announcement-dismissed";

const ANNOUNCEMENT = {
  title: "New: AI-Powered Lesson Plans",
  body: "Generate lesson plans in seconds with our new AI copilot. Try it now!",
  href: "/lesson-plans",
};

export function AnnouncementBanner() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const dismissed = localStorage.getItem(DISMISS_KEY);
    if (!dismissed) setVisible(true);
  }, []);

  function dismiss() {
    setVisible(false);
    localStorage.setItem(DISMISS_KEY, "true");
  }

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          transition={{ duration: 0.3, ease: [0.25, 0.46, 0.45, 0.94] }}
          className="overflow-hidden"
        >
          <div className="relative flex items-center gap-3 bg-gradient-to-r from-primary/8 via-primary/5 to-violet-500/5 px-5 py-2.5 border-b border-primary/10">
            <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-primary/10">
              <Megaphone className="h-3 w-3 text-primary" strokeWidth={2} />
            </div>
            <p className="min-w-0 flex-1 text-[12px]">
              <span className="font-semibold text-foreground/80">{ANNOUNCEMENT.title}</span>
              <span className="ml-1.5 text-muted-foreground/50">{ANNOUNCEMENT.body}</span>
            </p>
            <Link
              href={ANNOUNCEMENT.href}
              className="hidden shrink-0 items-center gap-1 rounded-lg bg-primary/10 px-2.5 py-1 text-[10px] font-semibold text-primary transition-colors hover:bg-primary/15 sm:inline-flex"
            >
              Try it <ArrowRight className="h-3 w-3" />
            </Link>
            <button
              onClick={dismiss}
              className="shrink-0 rounded-lg p-1 text-muted-foreground/30 transition-colors hover:bg-muted/30 hover:text-muted-foreground/60"
              aria-label="Dismiss"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
