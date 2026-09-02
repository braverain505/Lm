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
  const [isTablet, setIsTablet] = useState(false);

  useEffect(() => {
    const desktopMq = window.matchMedia("(min-width: 1024px)");
    const tabletMq = window.matchMedia("(min-width: 768px) and (max-width: 1023px)");

    const update = () => {
      setIsDesktop(desktopMq.matches);
      setIsTablet(tabletMq.matches);
    };

    update();
    desktopMq.addEventListener("change", update);
    tabletMq.addEventListener("change", update);

    return () => {
      desktopMq.removeEventListener("change", update);
      tabletMq.removeEventListener("change", update);
    };
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

  const contentPaddingLeft = isDesktop ? PANEL_WIDTH : isTablet ? 240 : 0;

  return (
    <SessionTermProvider>
      <div className="min-h-screen bg-background text-foreground">
        {/* ─── Desktop: Rail (hidden on tablets) ─── */}
        <div className="fixed inset-y-0 left-0 z-40 hidden lg:block print:hidden" style={{ width: RAIL_WIDTH }}>
          <NavigationRail onTogglePanel={togglePanel} panelOpen={panelOpen} />
        </div>

        {/* ─── Desktop & Tablet: Sidebar panel (always visible) ─── */}
        <div
          className="fixed inset-y-0 left-0 z-30 hidden md:block print:hidden"
          style={{ width: isTablet ? 240 : PANEL_WIDTH }}
        >
          <NavigationPanel open={true} isTablet={isTablet} />
        </div>

        {/* ─── Mobile: Full-screen drawer ─── */}
        {mobileOpen && (
          <motion.div
            className="fixed inset-0 z-50 lg:hidden"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            <motion.div
              className="absolute inset-0 bg-black/40 backdrop-blur-sm"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.15 }}
              onClick={closeMobile}
            />
            <motion.div
              className="absolute inset-y-0 left-0 shadow-elevated"
              style={{ width: isTablet ? 240 : 260 }}
              initial={{ x: isTablet ? -260 : -280 }}
              animate={{ x: 0 }}
              transition={{ duration: 0.25, ease: [0.21, 1.02, 0.73, 1] }}
            >
              <NavigationPanel open={true} onNavigate={closeMobile} isTablet={isTablet} />
            </motion.div>
          </motion.div>
        )}

        {/* ─── Main content ─── */}
        <motion.div
          className="flex min-h-screen flex-col print:!pl-0"
          initial={false}
          animate={{ paddingLeft: contentPaddingLeft }}
          transition={{ duration: 0.22, ease: [0.25, 0.46, 0.45, 0.94] }}
        >
          <AppHeader pathname={pathname} onOpenMobileNav={() => setMobileOpen(true)} />
          <motion.main
            key={pathname}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.15, ease: [0.25, 0.46, 0.45, 0.94] }}
            className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-6 sm:px-6 md:px-7 lg:px-8 md:py-7 lg:py-8 print:!max-w-none print:!p-0 print:!opacity-100 print:!translate-y-0"
          >
            {children}
          </motion.main>
        </motion.div>
      </div>
    </SessionTermProvider>
  );
}
