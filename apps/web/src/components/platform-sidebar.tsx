"use client";

import { ArrowLeft, ChevronLeft, LogOut, PanelLeft, ShieldCheck } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { PLATFORM_NAV } from "@/components/platform-nav";
import { Avatar } from "@/components/ui/avatar";
import { useAuth } from "@/providers/auth-provider";
import { cn } from "@/lib/utils";
import { api } from "@schoolos/shared";

interface PlatformSidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  onNavigate?: () => void;
}

export function PlatformSidebar({ collapsed, onToggle, onNavigate }: PlatformSidebarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, clear } = useAuth();

  const isActive = (href: string) => pathname.startsWith(href);
  const initials = (user?.full_name ?? "U").slice(0, 2).toUpperCase();

  async function handleLogout() {
    await api.logout();
    clear();
    router.replace("/login");
  }

  return (
    <aside
      className={cn(
        "flex h-full flex-col bg-sidebar text-sidebar-foreground transition-[width] duration-300 ease-in-out",
        collapsed ? "w-[76px]" : "w-[260px]",
      )}
    >
      {/* Brand */}
      <div
        className={cn(
          "flex h-16 shrink-0 items-center border-b border-sidebar-border",
          collapsed ? "justify-center px-3" : "gap-3 px-5",
        )}
      >
        <Link href="/super-admin" className="focus-ring flex items-center gap-3 rounded-lg" onClick={onNavigate}>
          <Image
            src="/clearis.png"
            alt="Clearis"
            width={1536}
            height={1024}
            priority
            className="h-11 w-auto shrink-0 rounded-lg object-contain"
          />
        </Link>
      </div>

      {/* Context */}
      {!collapsed && (
        <div className="shrink-0 px-4 pt-4">
          <div className="rounded-xl border border-sidebar-border bg-sidebar-accent/60 px-3.5 py-3">
            <p className="flex items-center gap-1.5 text-[13px] font-semibold text-white">
              <ShieldCheck className="h-3.5 w-3.5 text-sidebar-primary" /> Clearis Platform
            </p>
            <p className="mt-0.5 text-[11px] text-sidebar-muted">Super admin · every tenant</p>
          </div>
        </div>
      )}

      {/* Nav */}
      <nav className="scrollbar-thin flex-1 space-y-5 overflow-y-auto px-3 py-4">
        {PLATFORM_NAV.map((section) => (
          <div key={section.label}>
            {!collapsed && (
              <p className="mb-1.5 px-3 text-[10px] font-semibold uppercase tracking-[0.14em] text-sidebar-muted/70">
                {section.label}
              </p>
            )}
            <div className="space-y-0.5">
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
                      "group relative flex items-center rounded-lg text-[13px] font-medium transition-colors",
                      collapsed ? "justify-center px-2 py-2.5" : "gap-3 px-3 py-2",
                      active
                        ? "bg-sidebar-active text-white"
                        : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-white",
                    )}
                  >
                    {active && (
                      <span className="absolute left-0 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-full bg-sidebar-primary" />
                    )}
                    <Icon
                      className={cn(
                        "h-4 w-4 shrink-0 transition-colors",
                        active ? "text-sidebar-primary" : "text-sidebar-muted group-hover:text-sidebar-foreground",
                      )}
                    />
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
            <Link href="/super-admin/settings" className="focus-ring rounded-full" onClick={onNavigate} title={collapsed ? user?.full_name ?? "Profile" : undefined}>
              <Avatar
                name={user?.full_name}
                initials={initials}
                className="bg-gradient-to-br from-amber-500 to-orange-600 text-white ring-2 ring-white/10"
              />
            </Link>
            {!collapsed && (
              <div className="min-w-0 flex-1">
                <p className="truncate text-[13px] font-semibold text-white">{user?.full_name}</p>
                <p className="truncate text-[11px] text-sidebar-muted">Platform admin</p>
              </div>
            )}
          </div>

          {!collapsed && (
            <>
              <Link
                href="/dashboard"
                onClick={onNavigate}
                className="focus-ring mt-2 flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-xs font-medium text-sidebar-muted transition-colors hover:bg-sidebar-accent hover:text-white"
              >
                <ArrowLeft className="h-3.5 w-3.5" /> Back to school view
              </Link>
              <button
                onClick={handleLogout}
                className="focus-ring mt-1 flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-xs font-medium text-sidebar-muted transition-colors hover:bg-sidebar-accent hover:text-white"
              >
                <LogOut className="h-3.5 w-3.5" /> Sign out
              </button>
            </>
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
      </div>
    </aside>
  );
}