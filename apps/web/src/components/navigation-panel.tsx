"use client";

import { api } from "@schoolos/shared";
import { LogOut, ChevronRight } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { visiblePanel } from "@/components/nav-config";
import { Avatar } from "@/components/ui/avatar";
import { Dropdown } from "@/components/ui/dropdown";
import { ThemeSwitch } from "@/components/theme-switch";
import { useSessionTerm } from "@/providers/session-context";
import { useAuth } from "@/providers/auth-provider";
import { useQuery } from "@tanstack/react-query";
import { cn } from "@/lib/utils";

interface NavigationPanelProps {
  open: boolean;
  onNavigate?: () => void;
}

export function NavigationPanel({ open, onNavigate }: NavigationPanelProps) {
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
  const sections = visiblePanel(permissions, user?.is_superadmin ?? false, activeSchool?.role?.code ?? undefined);

  const initials = (user?.full_name ?? "U").slice(0, 2).toUpperCase();

  async function handleLogout() {
    await api.logout();
    clear();
    router.replace("/login");
  }

  const isActive = (href: string) =>
    href === "/dashboard" ? pathname === "/dashboard" || pathname === "/" : pathname.startsWith(href);

  if (!open) return null;

  return (
    <aside className="flex h-full w-[260px] flex-col border-r border-panel-border bg-panel animate-slide-in-right">
      {/* Brand + school */}
      <div className="flex h-[52px] shrink-0 items-center gap-2.5 border-b border-panel-border px-4">
        <Link href="/dashboard" className="flex items-center gap-2.5" onClick={onNavigate}>
          <span className="text-[14px] font-bold tracking-tight text-panel-foreground">Lumo</span>
        </Link>
      </div>

      {/* School context */}
      {activeSchool && (
        <div className="shrink-0 border-b border-panel-border px-4 py-2.5">
          <p className="truncate text-[12px] font-medium text-panel-foreground/80">{activeSchool.school_name}</p>
          <p className="mt-0.5 flex items-center gap-1.5 text-[10.5px] text-panel-muted">
            <span className="inline-block h-1 w-1 rounded-full bg-success" />
            {session ? session.name : "No session"}
            {term ? ` · ${term.name}` : ""}
          </p>
        </div>
      )}

      {/* Nav sections */}
      <nav className="scrollbar-thin flex-1 space-y-4 overflow-y-auto px-3 py-3">
        {sections.map((section) => (
          <div key={section.label}>
            <p className="mb-1 px-2 text-[10px] font-semibold uppercase tracking-[0.1em] text-panel-muted/50">
              {section.label}
            </p>
            <div className="space-y-px">
              {section.items.map(({ href, label, icon: Icon }) => {
                const active = isActive(href);
                return (
                  <Link
                    key={href}
                    href={href}
                    onClick={onNavigate}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "group flex items-center gap-2.5 rounded-md px-2.5 py-[7px] text-[13px] font-medium transition-colors duration-100",
                      active
                        ? "bg-panel-active-bg/10 text-panel-active-bg"
                        : "text-panel-foreground/60 hover:bg-panel-hover hover:text-panel-foreground",
                    )}
                  >
                    <Icon className={cn("h-4 w-4 shrink-0", active ? "text-panel-active-bg" : "text-panel-muted/50 group-hover:text-panel-foreground/70")} />
                    <span className="truncate">{label}</span>
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Bottom: user profile */}
      <div className="shrink-0 border-t border-panel-border p-3">
        <Dropdown
          trigger={
            <button className="flex w-full items-center gap-2.5 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-panel-hover">
              <Avatar name={user?.full_name} initials={initials} className="h-7 w-7 text-[10px]" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-[12px] font-medium text-panel-foreground">{user?.full_name}</p>
                <p className="truncate text-[10.5px] text-panel-muted capitalize">{activeSchool?.role?.name ?? "Member"}</p>
              </div>
              <ChevronRight className="h-3.5 w-3.5 shrink-0 text-panel-muted/40" />
            </button>
          }
          contentClassName="w-56"
        >
          {(close) => (
            <div>
              {/* School switcher */}
              {memberships.length > 1 && (
                <>
                  <div className="px-3 py-2">
                    <label htmlFor="school-switcher-panel" className="sr-only">Switch school</label>
                    <select
                      id="school-switcher-panel"
                      value={activeSchool?.school_id ?? ""}
                      onChange={(e) => {
                        const m = memberships.find((x) => x.school_id === e.target.value);
                        if (m) setActiveSchool(m);
                        close();
                      }}
                      className="w-full rounded-md border border-border/50 bg-background px-2 py-1.5 text-[11px] font-medium text-foreground outline-none focus:ring-1 focus:ring-ring"
                    >
                      {memberships.map((m) => (
                        <option key={m.school_id} value={m.school_id}>{m.school_name}</option>
                      ))}
                    </select>
                  </div>
                  <div className="border-t border-border/30" />
                </>
              )}

              <div className="px-1 py-1">
                <Link href="/settings" onClick={close} className="flex items-center gap-2 rounded-md px-2.5 py-2 text-[12px] font-medium text-foreground/70 transition-colors hover:bg-accent hover:text-foreground">
                  Profile
                </Link>
                <Link href="/settings" onClick={close} className="flex items-center gap-2 rounded-md px-2.5 py-2 text-[12px] font-medium text-foreground/70 transition-colors hover:bg-accent hover:text-foreground">
                  Preferences
                </Link>
                <div className="flex items-center justify-between px-2.5 py-2">
                  <span className="text-[12px] font-medium text-foreground/70">Theme</span>
                  <ThemeSwitch />
                </div>
              </div>

              <div className="border-t border-border/30" />

              <div className="px-1 py-1">
                <button
                  onClick={() => { handleLogout(); close(); }}
                  className="flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-[12px] font-medium text-destructive/80 transition-colors hover:bg-destructive/5 hover:text-destructive"
                >
                  <LogOut className="h-3.5 w-3.5" />
                  Sign out
                </button>
              </div>
            </div>
          )}
        </Dropdown>
      </div>
    </aside>
  );
}
