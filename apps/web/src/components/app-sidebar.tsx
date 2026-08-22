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
        collapsed ? "w-[76px]" : "w-[260px]",
      )}
    >
      {/* Brand */}
      <div className={cn("flex h-16 shrink-0 items-center border-b border-sidebar-border", collapsed ? "justify-center px-3" : "gap-3 px-5")}>
        <Link href="/dashboard" className="focus-ring flex items-center gap-3 rounded-lg" onClick={onNavigate}>
          <Image
            src="/logo_lumo.png"
            alt="Lumo"
            width={1536}
            height={1024}
            priority
            className="h-11 w-auto shrink-0 rounded-lg object-contain"
          />
        </Link>
      </div>

      {/* School context */}
      {!collapsed && activeSchool && (
        <div className="shrink-0 px-4 pt-4">
          <div className="rounded-xl border border-sidebar-border bg-sidebar-accent/60 px-3.5 py-3">
            <p className="truncate text-[13px] font-semibold text-white">{activeSchool.school_name}</p>
            <p className="mt-0.5 flex items-center gap-1.5 text-[11px] text-sidebar-muted">
              <span className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-400" />
              {session ? session.name : "No active session"}
              {term ? ` · ${term.name}` : ""}
            </p>
          </div>
        </div>
      )}

      {/* Nav */}
      <nav className="scrollbar-thin flex-1 space-y-5 overflow-y-auto px-3 py-4">
        {sections.map((section) => (
          <div key={section.label}>
            {!collapsed && (
              <p className="mb-1.5 px-3 text-[10px] font-semibold uppercase tracking-[0.14em] text-sidebar-muted/70">
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
                      "group relative flex items-center rounded-lg text-[13px] font-medium transition-colors",
                      collapsed ? "justify-center px-2 py-2.5" : "gap-3 px-3 py-2",
                      active
                        ? "bg-sidebar-active text-white"
                        : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-white",
                    )}
                  >
                    {active && <span className="absolute left-0 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-full bg-sidebar-primary" />}
                    <Icon
                      className={cn(
                        "h-4 w-4 shrink-0 transition-colors",
                        active ? "text-sidebar-primary" : "text-sidebar-muted group-hover:text-sidebar-foreground",
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
          "focus-ring mx-3 mb-1 flex items-center gap-2 rounded-lg px-2.5 py-2 text-[12px] font-medium text-sidebar-muted transition-colors hover:bg-sidebar-accent hover:text-white",
          collapsed && "justify-center",
        )}
      >
        {collapsed ? <PanelLeft className="h-4 w-4" /> : (
          <>
            <ChevronLeft className="h-4 w-4" />
            Collapse
          </>
        )}
      </button>

      {/* Profile */}
      <div className="shrink-0 border-t border-sidebar-border p-3">
        <div className={cn("rounded-xl", collapsed ? "flex justify-center" : "bg-sidebar-accent/60 p-3")}>
          <div className={cn("flex items-center", collapsed ? "flex-col" : "gap-3")}>
            <Link href="/settings" className="focus-ring rounded-full" onClick={onNavigate} title={collapsed ? user?.full_name ?? "Profile" : undefined}>
              <Avatar name={user?.full_name} initials={initials} className="bg-gradient-to-br from-indigo-500 to-indigo-700 text-white ring-2 ring-white/10" />
            </Link>
            {!collapsed && (
              <div className="min-w-0 flex-1">
                <p className="truncate text-[13px] font-semibold text-white">{user?.full_name}</p>
                <p className="truncate text-[11px] text-sidebar-muted capitalize">{activeSchool?.role?.name ?? "Member"}</p>
              </div>
            )}
          </div>

          {!collapsed && memberships.length > 0 && (
            <div className="mt-3">
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
                className="w-full rounded-lg border border-sidebar-border bg-sidebar px-2.5 py-1.5 text-xs font-medium text-sidebar-foreground outline-none focus-visible:ring-2 focus-visible:ring-sidebar-primary"
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
              className="focus-ring mt-2 flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-xs font-medium text-sidebar-muted transition-colors hover:bg-sidebar-accent hover:text-white"
            >
              <LogOut className="h-3.5 w-3.5" /> Sign out
            </button>
          )}
          {collapsed && (
            <button
              onClick={handleLogout}
              title="Sign out"
              className="focus-ring mt-2 flex w-full items-center justify-center rounded-lg px-2 py-1.5 text-sidebar-muted transition-colors hover:bg-sidebar-accent hover:text-white"
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