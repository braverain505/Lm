"use client";

import { motion } from "framer-motion";
import { usePathname } from "next/navigation";
import { ReactNode, useCallback, useEffect, useState } from "react";

import { AppHeader } from "@/components/app-header";
import { NavigationRail } from "@/components/navigation-rail";
import { NavigationPanel } from "@/components/navigation-panel";
import { SessionTermProvider } from "@/providers/session-context";
import { useAuth } from "@/providers/auth-provider";

const RAIL_WIDTH = 68;
const PANEL_WIDTH = 260;
const PANEL_KEY = "lumo.panel-open";

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { activeSchool } = useAuth();
  const [panelOpen, setPanelOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [isDesktop, setIsDesktop] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(min-width: 1024px)");
    const update = () => setIsDesktop(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);

  // Restore panel state
  useEffect(() => {
    try {
      const saved = localStorage.getItem(PANEL_KEY);
      if (saved) setPanelOpen(saved === "1");
    } catch { /* ignore */ }
  }, [activeSchool?.school_id]);

  // Persist panel state
  useEffect(() => {
    try {
      localStorage.setItem(PANEL_KEY, panelOpen ? "1" : "0");
    } catch { /* ignore */ }
  }, [panelOpen]);

  const togglePanel = useCallback(() => setPanelOpen((v) => !v), []);
  const closeMobile = useCallback(() => setMobileOpen(false), []);

  // Close mobile nav on route change
  useEffect(() => { setMobileOpen(false); }, [pathname]);

  const contentPaddingLeft = isDesktop ? RAIL_WIDTH + (panelOpen ? PANEL_WIDTH : 0) : 0;

  return (
    <SessionTermProvider>
      <div className="min-h-screen bg-background text-foreground">
        {/* ─── Desktop: Rail (always visible) ─── */}
        <div className="fixed inset-y-0 left-0 z-40 hidden lg:block print:hidden" style={{ width: RAIL_WIDTH }}>
          <NavigationRail onTogglePanel={togglePanel} panelOpen={panelOpen} />
        </div>

        {/* ─── Desktop: Expandable panel ─── */}
        {isDesktop && (
          <div
            className="fixed inset-y-0 z-30 hidden lg:block print:hidden transition-[width,opacity] duration-200 ease-out overflow-hidden"
            style={{
              left: RAIL_WIDTH,
              width: panelOpen ? PANEL_WIDTH : 0,
              opacity: panelOpen ? 1 : 0,
            }}
          >
            <NavigationPanel open={panelOpen} />
          </div>
        )}

        {/* ─── Mobile: Full-screen drawer ─── */}
        {mobileOpen && (
          <div className="fixed inset-0 z-50 lg:hidden">
            <div className="absolute inset-0 bg-black/40 backdrop-blur-sm animate-fade-in-soft" onClick={closeMobile} />
            <div className="absolute inset-y-0 left-0 flex shadow-elevated animate-slide-in-right">
              <NavigationRail onTogglePanel={closeMobile} panelOpen={false} />
              <NavigationPanel open={true} onNavigate={closeMobile} />
            </div>
          </div>
        )}

        {/* ─── Main content ─── */}
        <div
          className="flex min-h-screen flex-col transition-[padding] duration-200 ease-out print:!pl-0"
          style={{ paddingLeft: contentPaddingLeft }}
        >
          <AppHeader pathname={pathname} onOpenMobileNav={() => setMobileOpen(true)} />
          <motion.main
            key={pathname}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.15, ease: [0.25, 0.46, 0.45, 0.94] }}
            className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-8 print:!max-w-none print:!p-0 print:!opacity-100 print:!translate-y-0"
          >
            {children}
          </motion.main>
        </div>
      </div>
    </SessionTermProvider>
  );
}
