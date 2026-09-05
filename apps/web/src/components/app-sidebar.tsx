"use client";

import { api } from "@schoolos/shared";
import { ChevronLeft, PanelLeft } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { pageMeta, visibleNav } from "@/components/nav-config";
import { Avatar } from "@/components/ui/avatar";
import { useSessionTerm } from "@/providers/session-context";
import { useAuth } from "@/providers/auth-provider";
import { useQuery } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import { isSchoolAdminRole } from "@/lib/roles";

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  onNavigate?: () => void;
  embedded?: boolean;
}

export function AppSidebar({ collapsed, onToggle, onNavigate, embedded }: SidebarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, activeSchool, memberships, setActiveSchool, clear } = useAuth();
  const { session, term } = useSessionTerm();
  const { data: schoolProfile } = useQuery({
    queryKey: ["school", activeSchool?.school_id],
    queryFn: () => api.fetchSchoolMe(activeSchool!.school_id),
    enabled: Boolean(activeSchool?.school_id),
    staleTime: 5 * 60 * 1000,
  });

  const permissions = activeSchool?.permissions ?? [];
  const sections = visibleNav(permissions, user?.is_superadmin ?? false, activeSchool?.role?.code ?? undefined);
  const { title } = pageMeta(pathname);

  const initials = (user?.full_name ?? "U").slice(0, 2).toUpperCase();

  async function handleLogout() {
    await api.logout();
    clear();
    router.replace("/login");
  }

  const isActive = (href: string) =>
    href === "/dashboard" ? pathname === "/dashboard" || pathname === "/" : pathname.startsWith(href);

  return (
    <aside
      className={cn(
        "flex h-full flex-col bg-sidebar text-sidebar-foreground transition-[width] duration-200 ease-out",
        collapsed ? "w-[68px]" : "w-[240px]",
      )}
    >
      {/* Brand */}
      <div className={cn("flex h-[56px] shrink-0 items-center border-b border-sidebar-border", collapsed ? "justify-center px-2" : "gap-2.5 px-4")}>
        <Link href="/dashboard" className="flex items-center gap-2.5 rounded-lg" onClick={onNavigate}>
          {schoolProfile?.logo_url ? (
            <img src={schoolProfile.logo_url} alt={activeSchool?.school_name ?? "School"} className="h-8 w-8 shrink-0 rounded-md object-contain" />
          ) : (
            <Image src="/clearisbg.png" alt="Clearis" width={1536} height={1024} priority className="h-8 w-auto shrink-0 rounded-md object-contain" />
          )}
          {!collapsed && (
            <span className="truncate text-[13px] font-semibold text-white/90">
              {schoolProfile?.name || activeSchool?.school_name || "Clearis"}
            </span>
          )}
        </Link>
      </div>

      {/* School context */}
      {!collapsed && activeSchool && (
        <div className="shrink-0 px-3 pt-3">
          <div className="rounded-lg bg-white/[0.04] px-3 py-2">
            <p className="truncate text-[12px] font-medium text-white/80">{activeSchool.school_name}</p>
            <p className="mt-0.5 flex items-center gap-1.5 text-[10.5px] text-sidebar-muted">
              <span className="inline-block h-1 w-1 rounded-full bg-emerald-400" />
              {session ? session.name : "No active session"}
              {term ? ` · ${term.name}` : ""}
            </p>
          </div>
        </div>
      )}

      {/* Nav */}
      <nav className="scrollbar-thin flex-1 space-y-5 overflow-y-auto px-2.5 pt-3 pb-2">
        {sections.map((section) => (
          <div key={section.label}>
            {!collapsed && (
              <p className="mb-1 px-2.5 text-[10px] font-medium uppercase tracking-[0.12em] text-sidebar-muted/60">
                {section.label}
              </p>
            )}
            <div className="space-y-px">
              {section.items.map(({ href, label, icon: Icon }) => {
                const active = isActive(href);
                return (
                  <Link
                    key={href}
                    href={href}
                    onClick={onNavigate}
                    aria-current={active ? "page" : undefined}
                    title={collapsed ? label : undefined}
                    className={cn(
                      "group relative flex items-center rounded-lg text-[13px] font-medium transition-colors duration-100",
                      collapsed ? "justify-center px-2 py-2" : "gap-2.5 px-2.5 py-1.5",
                      active
                        ? "bg-white/[0.08] text-white"
                        : "text-white/50 hover:bg-white/[0.04] hover:text-white/80",
                    )}
                  >
                    {active && (
                      <span className="absolute left-0 top-1/2 h-4 w-[2px] -translate-y-1/2 rounded-full bg-sidebar-primary" />
                    )}
                    <Icon className={cn("h-4 w-4 shrink-0", active ? "text-sidebar-primary" : "text-white/30 group-hover:text-white/50")} />
                    {!collapsed && <span className="truncate">{label}</span>}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Collapse toggle */}
      <button
        onClick={onToggle}
        title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        className={cn(
          "mx-2.5 mb-1.5 flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-[11px] font-medium text-white/30 transition-colors hover:bg-white/[0.04] hover:text-white/60",
          collapsed && "justify-center",
        )}
      >
        {collapsed ? <PanelLeft className="h-4 w-4" /> : (
          <>
            <ChevronLeft className="h-3.5 w-3.5 transition-transform duration-200 group-hover:translate-x-0.5" />
            <span>Collapse</span>
          </>
        )}
      </button>

      {/* Profile */}
      <div className="shrink-0 border-t border-sidebar-border p-2.5">
        <div className={cn("rounded-lg", collapsed ? "flex justify-center" : "bg-white/[0.03] p-2")}>
          <div className={cn("flex items-center", collapsed ? "flex-col" : "gap-2")}>
            {isSchoolAdminRole(activeSchool?.role?.code) ? (
              <Link href="/settings" className="rounded-full" onClick={onNavigate} title={collapsed ? user?.full_name ?? "Profile" : undefined}>
                <Avatar name={user?.full_name} initials={initials} className="h-7 w-7 bg-gradient-to-br from-indigo-500 to-indigo-600 text-[10px] text-white" />
              </Link>
            ) : (
              <div className="rounded-full" title={collapsed ? user?.full_name ?? "Profile" : undefined}>
                <Avatar name={user?.full_name} initials={initials} className="h-7 w-7 bg-gradient-to-br from-indigo-500 to-indigo-600 text-[10px] text-white" />
              </div>
            )}
            {!collapsed && (
              <div className="min-w-0 flex-1">
                <p className="truncate text-[12px] font-medium text-white/80">{user?.full_name}</p>
                <p className="truncate text-[10.5px] text-sidebar-muted capitalize">{activeSchool?.role?.name ?? "Member"}</p>
              </div>
            )}
          </div>

          {!collapsed && memberships.length > 1 && (
            <div className="mt-2">
              <label htmlFor="school-switcher" className="sr-only">Switch school</label>
              <select
                id="school-switcher"
                value={activeSchool?.school_id ?? ""}
                onChange={(e) => {
                  const m = memberships.find((x) => x.school_id === e.target.value);
                  if (m) setActiveSchool(m);
                }}
                className="w-full rounded-md border border-white/[0.06] bg-white/[0.04] px-2 py-1 text-[11px] font-medium text-white/70 outline-none focus-visible:ring-1 focus-visible:ring-sidebar-primary"
              >
                {memberships.map((m) => (
                  <option key={m.school_id} value={m.school_id} className="bg-sidebar text-white">
                    {m.school_name}
                  </option>
                ))}
              </select>
            </div>
          )}

          {!collapsed && (
            <button
              onClick={handleLogout}
              className="mt-2 flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-[11px] font-medium text-white/40 transition-colors hover:bg-white/[0.04] hover:text-white/70"
            >
              <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
              Sign out
            </button>
          )}
          {collapsed && (
            <button
              onClick={handleLogout}
              title="Sign out"
              className="mt-1.5 flex w-full items-center justify-center rounded-md px-2 py-1.5 text-white/40 transition-colors hover:bg-white/[0.04] hover:text-white/70"
            >
              <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
            </button>
          )}
        </div>
        {!embedded && <span className="sr-only">{title}</span>}
      </div>
    </aside>
  );
}
