"use client";

import { api } from "@schoolos/shared";
import { ChevronLeft, LogOut, PanelLeft } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { pageMeta, visibleNav } from "@/components/nav-config";
import { Avatar } from "@/components/ui/avatar";
import { useSessionTerm } from "@/providers/session-context";
import { useAuth } from "@/providers/auth-provider";
import { useQuery } from "@tanstack/react-query";
import { cn } from "@/lib/utils";

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  onNavigate?: () => void;
  embedded?: boolean;
}

export function AppSidebar({ collapsed, onToggle, onNavigate, embedded }: SidebarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, memberships, activeSchool, setActiveSchool, clear } = useAuth();
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
        "flex h-full flex-col bg-sidebar text-sidebar-foreground transition-[width] duration-300 ease-in-out",
        collapsed ? "w-[72px]" : "w-[260px]",
      )}
    >
      {/* Brand */}
      <div className={cn("flex h-[60px] shrink-0 items-center border-b border-white/[0.06]", collapsed ? "justify-center px-3" : "gap-3 px-5")}>
        <Link href="/dashboard" className="flex items-center gap-3 rounded-lg" onClick={onNavigate}>
          {schoolProfile?.logo_url ? (
            <img src={schoolProfile.logo_url} alt={activeSchool?.school_name ?? "School"} className="h-11 w-11 shrink-0 rounded-lg bg-white object-contain" />
          ) : (
            <Image src="/clearisbg.png" alt="Clearis" width={1536} height={1024} priority className="h-11 w-auto shrink-0 rounded-lg object-contain" />
          )}
          {!collapsed && (
            <span className="text-[14px] font-bold tracking-tight text-white/90">
              {schoolProfile?.name || activeSchool?.school_name || "Clearis"}
            </span>
          )}
        </Link>
      </div>

      {/* School context */}
      {!collapsed && activeSchool && (
        <div className="shrink-0 px-3 pt-3">
          <div className="rounded-xl border border-white/[0.06] bg-white/[0.04] px-3.5 py-2.5">
            <p className="truncate text-[12px] font-semibold text-white/90">{activeSchool.school_name}</p>
            <p className="mt-0.5 flex items-center gap-1.5 text-[10.5px] text-sidebar-muted">
              <span className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-400" />
              {session ? session.name : "No active session"}
              {term ? ` · ${term.name}` : ""}
            </p>
          </div>
        </div>
      )}

      {/* Nav */}
      <nav className="scrollbar-thin flex-1 space-y-6 overflow-y-auto px-3 pt-4 pb-2">
        {sections.map((section) => (
          <div key={section.label}>
            {!collapsed && (
              <p className="mb-1 px-3 text-[10px] font-semibold uppercase tracking-[0.16em] text-sidebar-muted/50">
                {section.label}
              </p>
            )}
            <div className="space-y-0.5">
              {section.items.map(({ href, label, icon: Icon }) => {
                const active = isActive(href);
                const item = (
                  <Link
                    href={href}
                    onClick={onNavigate}
                    aria-current={active ? "page" : undefined}
                    title={collapsed ? label : undefined}
                    className={cn(
                      "group relative flex items-center rounded-xl text-[13px] font-medium transition-all duration-150",
                      collapsed ? "justify-center px-2 py-2" : "gap-2.5 px-3 py-2",
                      active
                        ? "bg-white/[0.1] text-white shadow-sm shadow-black/10"
                        : "text-sidebar-foreground/70 hover:bg-white/[0.06] hover:text-white/90",
                    )}
                  >
                    {active && (
                      <span className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-sidebar-primary" />
                    )}
                    <Icon
                      className={cn(
                        "h-[18px] w-[18px] shrink-0 transition-colors duration-150",
                        active ? "text-sidebar-primary" : "text-sidebar-muted/60 group-hover:text-sidebar-foreground/80",
                      )}
                    />
                    {!collapsed && <span className="truncate">{label}</span>}
                  </Link>
                );
                return <div key={href}>{item}</div>;
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
          "mx-3 mb-2 flex items-center gap-2 rounded-xl px-2.5 py-1.5 text-[11px] font-medium text-sidebar-muted/50 transition-colors hover:bg-white/[0.06] hover:text-white/70",
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
      <div className="shrink-0 border-t border-white/[0.06] p-3">
        <div className={cn("rounded-xl", collapsed ? "flex justify-center" : "bg-white/[0.04] p-2.5")}>
          <div className={cn("flex items-center", collapsed ? "flex-col" : "gap-2.5")}>
            <Link href="/settings" className="rounded-full" onClick={onNavigate} title={collapsed ? user?.full_name ?? "Profile" : undefined}>
              <Avatar name={user?.full_name} initials={initials} className="h-8 w-8 bg-gradient-to-br from-indigo-500 to-indigo-700 text-[11px] text-white ring-2 ring-white/10" />
            </Link>
            {!collapsed && (
              <div className="min-w-0 flex-1">
                <p className="truncate text-[12px] font-semibold text-white/90">{user?.full_name}</p>
                <p className="truncate text-[10.5px] text-sidebar-muted capitalize">{activeSchool?.role?.name ?? "Member"}</p>
              </div>
            )}
          </div>

          {!collapsed && memberships.length > 1 && (
            <div className="mt-2">
              <label htmlFor="school-switcher" className="sr-only">
                Switch school
              </label>
              <select
                id="school-switcher"
                value={activeSchool?.school_id ?? ""}
                onChange={(e) => {
                  const m = memberships.find((x) => x.school_id === e.target.value);
                  if (m) setActiveSchool(m);
                }}
                className="w-full rounded-lg border border-white/[0.08] bg-white/[0.04] px-2.5 py-1.5 text-[11px] font-medium text-white/80 outline-none focus-visible:ring-2 focus-visible:ring-sidebar-primary"
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
              className="mt-2 flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-[11px] font-medium text-sidebar-muted/60 transition-colors hover:bg-white/[0.06] hover:text-white/70"
            >
              <LogOut className="h-3.5 w-3.5" /> Sign out
            </button>
          )}
          {collapsed && (
            <button
              onClick={handleLogout}
              title="Sign out"
              className="mt-2 flex w-full items-center justify-center rounded-lg px-2 py-1.5 text-sidebar-muted/60 transition-colors hover:bg-white/[0.06] hover:text-white/70"
            >
              <LogOut className="h-4 w-4" />
            </button>
          )}
        </div>
        {!embedded && <span className="sr-only">{title}</span>}
      </div>
    </aside>
  );
}
