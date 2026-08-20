"use client";

import { motion } from "framer-motion";
import { usePathname } from "next/navigation";
import { ReactNode, useEffect, useState } from "react";

import { PlatformHeader } from "@/components/platform-header";
import { PlatformSidebar } from "@/components/platform-sidebar";

const SIDEBAR_WIDTH = 260;
const SIDEBAR_WIDTH_COLLAPSED = 76;
const COLLAPSE_KEY = "schoolos.sidebar-collapsed";

export function PlatformShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
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
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(COLLAPSE_KEY, collapsed ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, [collapsed]);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div
        className="fixed inset-y-0 left-0 z-30 hidden lg:block print:hidden"
        style={{ width: collapsed ? SIDEBAR_WIDTH_COLLAPSED : SIDEBAR_WIDTH }}
      >
        <PlatformSidebar collapsed={collapsed} onToggle={() => setCollapsed((v) => !v)} />
      </div>

      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm animate-fade-in-soft" onClick={() => setMobileOpen(false)} />
          <div className="absolute inset-y-0 left-0 w-[280px] shadow-pop animate-slide-in-right">
            <PlatformSidebar collapsed={false} onToggle={() => undefined} onNavigate={() => setMobileOpen(false)} />
          </div>
        </div>
      )}

      <div
        className="flex min-h-screen flex-col transition-[padding] duration-300 ease-in-out print:!pl-0"
        style={{ paddingLeft: isDesktop ? (collapsed ? SIDEBAR_WIDTH_COLLAPSED : SIDEBAR_WIDTH) : 0 }}
      >
        <div className="lg:hidden" />
        <PlatformHeader onOpenMobileNav={() => setMobileOpen(true)} />
        <motion.main
          key={pathname}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.18, ease: "easeOut" }}
          className="mx-auto w-full max-w-[1600px] flex-1 p-5 sm:p-6 lg:p-8 print:!max-w-none print:!p-0"
        >
          {children}
        </motion.main>
      </div>
    </div>
  );
}