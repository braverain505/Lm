"use client";

import { api } from "@schoolos/shared";
import { motion } from "framer-motion";
import { LogOut, ChevronRight } from "lucide-react";
import Image from "next/image";
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
import { isSchoolAdminRole } from "@/lib/roles";

interface NavigationPanelProps {
  open: boolean;
  onNavigate?: () => void;
  isTablet?: boolean;
}

export function NavigationPanel({ open, onNavigate, isTablet = false }: NavigationPanelProps) {
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
  const canManageSchool = permissions.includes("school.manage");

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
    <aside className={cn(
      "flex h-full flex-col border-r border-panel-border bg-panel shadow-panel",
      isTablet ? "w-[240px]" : "w-[260px]"
    )}>
      {/* Premium Brand Header */}
      <div className="flex h-[56px] shrink-0 items-center gap-3 border-b border-panel-border px-5">
        <Link href="/dashboard" className="flex items-center gap-3" onClick={onNavigate}>
          {schoolProfile?.logo_url ? (
            <img src={schoolProfile.logo_url} alt="Logo" className="h-8 w-8 rounded-lg object-contain" />
          ) : (
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-primary-hover">
              <Image src="/clearisbg.png" alt="Clearis" width={32} height={32} className="h-5 w-5 object-contain" priority />
            </div>
          )}
          <div className="min-w-0">
            <p className="truncate font-bold tracking-tight text-panel-foreground text-[13px] md:text-[14px]">
              {activeSchool?.school_name || "Clearis"}
            </p>
            <p className="text-[9px] font-medium uppercase tracking-wider text-panel-muted/50">School Management</p>
          </div>
        </Link>
      </div>

      {/* Premium School Context */}
      {activeSchool && (
        <motion.div
          className="shrink-0 border-b border-panel-border px-5 py-3.5"
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25, delay: 0.08, ease: [0.25, 0.46, 0.45, 0.94] }}
        >
          <p className="truncate font-semibold text-panel-foreground text-[12px] md:text-[13px]">
            {activeSchool.school_name}
          </p>
          <p className="mt-1 flex items-center gap-2 text-panel-muted text-[10px] md:text-[11px]">
            <motion.span
              className="inline-block h-1.5 w-1.5 rounded-full bg-success"
              animate={{ scale: [1, 1.3, 1], opacity: [1, 0.7, 1] }}
              transition={{ duration: 2.5, repeat: Infinity, ease: "easeInOut" }}
            />
            <span className="font-medium">{session ? session.name : "No session"}</span>
            {term && <span className="text-panel-muted/70">· {term.name}</span>}
          </p>
        </motion.div>
      )}

      {/* Premium Nav Sections - Sophisticated Typography */}
      <nav className="scrollbar-thin flex-1 space-y-6 overflow-y-auto px-4 py-5">
        {sections.map((section, sectionIndex) => (
          <motion.div
            key={section.label}
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25, delay: 0.08 + sectionIndex * 0.06, ease: [0.25, 0.46, 0.45, 0.94] }}
          >
            <p className="mb-2 px-3 font-semibold uppercase tracking-wider text-panel-muted/60 text-[9.5px] md:text-[10.5px]">
              {section.label}
            </p>
            <div className="space-y-0.5">
              {section.items.map(({ href, label, icon: Icon }) => {
                const active = isActive(href);
                return (
                  <Link
                    key={href}
                    href={href}
                    onClick={onNavigate}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "group flex items-center gap-3 rounded-lg px-3 py-2 font-medium transition-all duration-200 text-[12px] md:text-[13px]",
                      active
                        ? "bg-panel-active-bg text-panel-active-fg shadow-sm"
                        : "text-panel-foreground/70 hover:bg-panel-hover hover:text-panel-foreground hover:translate-x-1",
                    )}
                  >
                    <Icon className={cn(
                      "shrink-0 transition-all duration-200 h-[16px] w-[16px] md:h-[18px] md:w-[18px]",
                      active ? "text-panel-active-fg" : "text-panel-muted/60 group-hover:text-panel-foreground/80"
                    )} />
                    <span className="truncate">{label}</span>
                  </Link>
                );
              })}
            </div>
          </motion.div>
        ))}
      </nav>

      {/* Premium User Profile Section */}
      <div className="shrink-0 border-t border-panel-border p-4">
        <Dropdown
          trigger={
            <button className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition-all duration-200 hover:bg-panel-hover">
              <Avatar
                name={user?.full_name}
                initials={initials}
                className="h-8 w-8 bg-gradient-to-br from-primary to-primary-hover text-xs font-semibold text-white ring-2 ring-panel-border"
              />
              <div className="min-w-0 flex-1">
                <p className="truncate font-semibold text-panel-foreground text-[12px] md:text-[13px]">
                  {user?.full_name}
                </p>
                <p className="truncate text-panel-muted capitalize text-[10px] md:text-[11px]">
                  {activeSchool?.role?.name ?? "Member"}
                </p>
              </div>
              <ChevronRight className="h-4 w-4 shrink-0 text-panel-muted/50 transition-transform group-hover:translate-x-0.5" />
            </button>
          }
          contentClassName="w-64"
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
                {canManageSchool && isSchoolAdminRole(activeSchool?.role?.code) && (
                  <>
                    <Link href="/settings" onClick={close} className="flex items-center gap-2 rounded-md px-2.5 py-2 text-[12px] font-medium text-foreground/70 transition-colors hover:bg-accent hover:text-foreground">
                      Profile
                    </Link>
                    <Link href="/settings" onClick={close} className="flex items-center gap-2 rounded-md px-2.5 py-2 text-[12px] font-medium text-foreground/70 transition-colors hover:bg-accent hover:text-foreground">
                      Preferences
                    </Link>
                  </>
                )}
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
