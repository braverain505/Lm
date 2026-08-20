"use client";

import { motion } from "framer-motion";
import { usePathname } from "next/navigation";
import { ReactNode, useEffect, useState } from "react";

import { AppHeader } from "@/components/app-header";
import { AppSidebar } from "@/components/app-sidebar";
import { SessionTermProvider } from "@/providers/session-context";
import { useAuth } from "@/providers/auth-provider";

const SIDEBAR_WIDTH = 260;
const SIDEBAR_WIDTH_COLLAPSED = 76;
const COLLAPSE_KEY = "schoolos.sidebar-collapsed";

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { activeSchool } = useAuth();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [isDesktop, setIsDesktop] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(min-width: 1024px)");
    const update = () => setIsDesktop(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    try {
      const saved = localStorage.getItem(COLLAPSE_KEY);
      if (saved) setCollapsed(saved === "1");
    } catch {
      /* ignore */
    }
  }, [activeSchool?.school_id]);

  useEffect(() => {
    try {
      localStorage.setItem(COLLAPSE_KEY, collapsed ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, [collapsed]);

  return (
    <SessionTermProvider>
      <div className="min-h-screen bg-background text-foreground">
        {/* Desktop sidebar */}
        <div
          className="fixed inset-y-0 left-0 z-30 hidden lg:block print:hidden"
          style={{ width: collapsed ? SIDEBAR_WIDTH_COLLAPSED : SIDEBAR_WIDTH }}
        >
          <AppSidebar collapsed={collapsed} onToggle={() => setCollapsed((v) => !v)} />
        </div>

        {/* Mobile drawer */}
        {mobileOpen && (
          <div className="fixed inset-0 z-40 lg:hidden">
            <div className="absolute inset-0 bg-black/50 backdrop-blur-sm animate-fade-in-soft" onClick={() => setMobileOpen(false)} />
            <div className="absolute inset-y-0 left-0 w-[280px] shadow-pop animate-slide-in-right">
              <AppSidebar
                collapsed={false}
                onToggle={() => undefined}
                onNavigate={() => setMobileOpen(false)}
                embedded
              />
            </div>
          </div>
        )}

        <div
          className="flex min-h-screen flex-col transition-[padding] duration-300 ease-in-out print:!pl-0"
          style={{ paddingLeft: isDesktop ? (collapsed ? SIDEBAR_WIDTH_COLLAPSED : SIDEBAR_WIDTH) : 0 }}
        >
          {/* Mobile spacer only — header is sticky within the padded column */}
          <div className="lg:hidden" />
          <AppHeader pathname={pathname} onOpenMobileNav={() => setMobileOpen(true)} />
          <motion.main
            key={pathname}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
            className="mx-auto w-full max-w-[1600px] flex-1 p-5 sm:p-6 lg:p-8 print:!max-w-none print:!p-0 print:!opacity-100 print:!translate-y-0"
          >
            {children}
          </motion.main>
        </div>
      </div>
    </SessionTermProvider>
  );
}