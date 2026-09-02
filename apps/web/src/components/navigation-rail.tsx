"use client";

import { api } from "@schoolos/shared";
import { motion } from "framer-motion";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { visibleRail } from "@/components/nav-config";
import { Avatar } from "@/components/ui/avatar";
import { useAuth } from "@/providers/auth-provider";
import { useQuery } from "@tanstack/react-query";
import { cn } from "@/lib/utils";

interface NavigationRailProps {
  onTogglePanel: () => void;
  panelOpen: boolean;
}

export function NavigationRail({ onTogglePanel, panelOpen }: NavigationRailProps) {
  const pathname = usePathname();
  const { user, activeSchool } = useAuth();
  const { data: schoolProfile } = useQuery({
    queryKey: ["school", activeSchool?.school_id],
    queryFn: () => api.fetchSchoolMe(activeSchool!.school_id),
    enabled: Boolean(activeSchool?.school_id),
    staleTime: 5 * 60 * 1000,
  });

  const permissions = activeSchool?.permissions ?? [];
  const railItems = visibleRail(permissions, user?.is_superadmin ?? false, activeSchool?.role?.code ?? undefined);

  const initials = (user?.full_name ?? "U").slice(0, 2).toUpperCase();

  const isActive = (href: string) =>
    href === "/dashboard" ? pathname === "/dashboard" || pathname === "/" : pathname.startsWith(href);

  return (
    <nav className="flex h-full w-[68px] flex-col items-center border-r border-rail-border bg-rail py-4">
      {/* Logo / brand toggle - Premium styling */}
      <motion.button
        onClick={onTogglePanel}
        className="group relative mb-6 flex h-10 w-10 items-center justify-center rounded-xl transition-all duration-200 hover:bg-rail-active-bg/10 hover:scale-105"
        title={panelOpen ? "Collapse navigation" : "Expand navigation"}
        whileTap={{ scale: 0.95 }}
        transition={{ duration: 0.18 }}
      >
        {schoolProfile?.logo_url ? (
          <img src={schoolProfile.logo_url} alt="Logo" className="h-7 w-7 rounded object-contain" />
        ) : (
          <Image src="/clearisbg.png" alt="Lumo" width={96} height={96} priority className="h-7 w-auto object-contain opacity-90" />
        )}
        {/* Premium Tooltip */}
        <span className="pointer-events-none absolute left-full ml-3 rounded-lg bg-foreground px-3 py-1.5 text-xs font-medium text-background shadow-elevated opacity-0 transition-all duration-150 group-hover:opacity-100 group-hover:translate-x-1 whitespace-nowrap z-50">
          {schoolProfile?.name || activeSchool?.school_name || "Clearis"}
        </span>
      </motion.button>

      {/* Navigation icons - Premium monochrome design */}
      <div className="flex flex-1 flex-col items-center gap-1">
        {railItems.map(({ href, label, icon: Icon }, index) => {
          const active = isActive(href);
          return (
            <motion.div
              key={href}
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.04, duration: 0.25, ease: [0.25, 0.46, 0.45, 0.94] }}
            >
              <Link
                href={href}
                className={cn(
                  "group relative flex h-10 w-10 items-center justify-center rounded-xl transition-all duration-200",
                  active
                    ? "bg-rail-active-bg text-rail-active-fg shadow-sm"
                    : "text-rail-muted hover:bg-rail-active-bg/10 hover:text-rail-foreground hover:scale-105",
                )}
                title={label}
              >
                {active && (
                  <motion.span
                    className="absolute -left-[1px] top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-rail-active-bg"
                    layoutId="rail-active-indicator"
                    transition={{ duration: 0.25, ease: [0.25, 0.46, 0.45, 0.94] }}
                  />
                )}
                <Icon className={cn("h-5 w-5", active ? "stroke-[2.5]" : "stroke-[2]")} />
                {/* Premium Tooltip */}
                <span className="pointer-events-none absolute left-full ml-3 rounded-lg bg-foreground px-3 py-1.5 text-xs font-medium text-background shadow-elevated opacity-0 transition-all duration-150 group-hover:opacity-100 group-hover:translate-x-1 whitespace-nowrap z-50">
                  {label}
                </span>
              </Link>
            </motion.div>
          );
        })}
      </div>

      {/* Bottom: avatar - Premium style */}
      <Link
        href="/settings"
        className="group relative mt-auto flex h-10 w-10 items-center justify-center rounded-xl transition-all duration-200 hover:bg-rail-active-bg/10 hover:scale-105"
        title="Settings"
      >
        <Avatar
          name={user?.full_name}
          initials={initials}
          className="h-8 w-8 bg-gradient-to-br from-primary to-primary-hover text-[11px] font-medium text-white ring-2 ring-rail-border"
        />
        {/* Premium Tooltip */}
        <span className="pointer-events-none absolute left-full ml-3 rounded-lg bg-foreground px-3 py-1.5 text-xs font-medium text-background shadow-elevated opacity-0 transition-all duration-150 group-hover:opacity-100 group-hover:translate-x-1 whitespace-nowrap z-50">
          Settings
        </span>
      </Link>
    </nav>
  );
}
