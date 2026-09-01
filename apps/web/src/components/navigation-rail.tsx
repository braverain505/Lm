"use client";

import { api } from "@schoolos/shared";
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
    <nav className="flex h-full w-[68px] flex-col items-center bg-rail py-3">
      {/* Logo / brand toggle */}
      <button
        onClick={onTogglePanel}
        className="group relative mb-4 flex h-9 w-9 items-center justify-center rounded-lg transition-colors hover:bg-white/[0.08]"
        title={panelOpen ? "Collapse navigation" : "Expand navigation"}
      >
        {schoolProfile?.logo_url ? (
          <img src={schoolProfile.logo_url} alt="Logo" className="h-6 w-6 rounded object-contain" />
        ) : (
          <Image src="/clearisbg.png" alt="Lumo" width={96} height={96} priority className="h-6 w-auto object-contain" />
        )}
        {/* Tooltip */}
        <span className="pointer-events-none absolute left-full ml-3 rounded-md bg-rail-foreground px-2.5 py-1 text-[11px] font-medium text-rail opacity-0 shadow-lg transition-opacity group-hover:opacity-100 whitespace-nowrap z-50">
          {schoolProfile?.name || activeSchool?.school_name || "Lumo"}
        </span>
      </button>

      {/* Navigation icons */}
      <div className="flex flex-1 flex-col items-center gap-0.5">
        {railItems.map(({ href, label, icon: Icon }) => {
          const active = isActive(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "group relative flex h-9 w-9 items-center justify-center rounded-lg transition-colors duration-100",
                active
                  ? "bg-rail-active-bg/15 text-rail-active-fg"
                  : "text-rail-muted hover:bg-white/[0.06] hover:text-rail-foreground",
              )}
              title={label}
            >
              {active && (
                <span className="absolute left-0 top-1/2 h-4 w-[2px] -translate-y-1/2 rounded-full bg-rail-active-bg" />
              )}
              <Icon className="h-[18px] w-[18px]" />
              {/* Tooltip */}
              <span className="pointer-events-none absolute left-full ml-3 rounded-md bg-rail-foreground px-2.5 py-1 text-[11px] font-medium text-rail opacity-0 shadow-lg transition-opacity group-hover:opacity-100 whitespace-nowrap z-50">
                {label}
              </span>
            </Link>
          );
        })}
      </div>

      {/* Bottom: avatar */}
      <Link
        href="/settings"
        className="group relative mt-auto flex h-9 w-9 items-center justify-center rounded-lg transition-colors hover:bg-white/[0.08]"
        title="Settings"
      >
        <Avatar name={user?.full_name} initials={initials} className="h-7 w-7 bg-gradient-to-br from-indigo-500 to-indigo-600 text-[10px] text-white" />
        {/* Tooltip */}
        <span className="pointer-events-none absolute left-full ml-3 rounded-md bg-rail-foreground px-2.5 py-1 text-[11px] font-medium text-rail opacity-0 shadow-lg transition-opacity group-hover:opacity-100 whitespace-nowrap z-50">
          Settings
        </span>
      </Link>
    </nav>
  );
}
