"use client";

import { ArrowLeft, Bell, LogOut, Menu, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

import { platformMeta } from "@/components/platform-nav";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Dropdown, MenuItem, MenuLabel, MenuSeparator } from "@/components/ui/dropdown";
import { useSaNotifications, useSaMarkNotificationsRead } from "@/hooks/use-superadmin";
import { useAuth } from "@/providers/auth-provider";
import { cn } from "@/lib/utils";
import { api } from "@schoolos/shared";

const SEVERITY_TONE: Record<string, string> = {
  critical: "bg-destructive/10 text-destructive",
  warning: "bg-warning/10 text-warning",
  info: "bg-info/10 text-info",
};

export function PlatformHeader({ onOpenMobileNav }: { onOpenMobileNav: () => void }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, clear } = useAuth();
  const meta = platformMeta(pathname);
  const { data: notifications = [] } = useSaNotifications();
  const markRead = useSaMarkNotificationsRead();
  const [viewing, setViewing] = useState(false);

  const unread = notifications.filter((n: { read?: boolean }) => !n.read).length;

  async function handleLogout() {
    await api.logout();
    clear();
    router.replace("/login");
  }

  return (
    <header className="sticky top-0 z-20 flex h-16 shrink-0 items-center gap-3 border-b bg-background/85 px-4 backdrop-blur-xl lg:px-6 print:hidden">
      <button
        onClick={onOpenMobileNav}
        className="focus-ring -ml-1 flex h-9 w-9 items-center justify-center rounded-lg text-muted-foreground hover:bg-accent lg:hidden"
        aria-label="Open navigation"
      >
        <Menu className="h-5 w-5" />
      </button>

      <div className="min-w-0">
        <div className="flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground">
          <span className="flex items-center gap-1 text-amber-600 dark:text-amber-400">
            <ShieldCheck className="h-3 w-3" /> Super admin
          </span>
          {meta.breadcrumb && (
            <>
              <span className="text-border">/</span>
              <span>{meta.breadcrumb}</span>
            </>
          )}
        </div>
        <h1 className="truncate text-[15px] font-semibold leading-tight tracking-tight">{meta.title}</h1>
      </div>

      <div className="ml-auto flex items-center gap-2">
        <Link
          href="/dashboard"
          className="focus-ring hidden h-9 items-center gap-1.5 rounded-lg border border-input bg-background px-3 text-[13px] font-medium text-muted-foreground shadow-card transition-colors hover:bg-accent/60 hover:text-foreground sm:inline-flex"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> School view
        </Link>

        {/* Platform notifications */}
        <Dropdown
          trigger={
            <span className="relative flex h-9 w-9 items-center justify-center rounded-lg border border-input bg-background text-muted-foreground shadow-card transition-colors hover:bg-accent/60 hover:text-foreground">
              <Bell className="h-4 w-4" />
              {unread > 0 && (
                <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-bold text-destructive-foreground">
                  {unread}
                </span>
              )}
            </span>
          }
          contentClassName="w-80"
        >
          {(close) => (
            <div>
              <MenuLabel className="flex items-center justify-between">
                <span>Platform alerts</span>
                {unread > 0 && (
                  <button
                    className="text-[10px] font-semibold uppercase tracking-wide text-primary hover:underline"
                    onClick={() => markRead.mutate(notifications.map((n: { id: string; read?: boolean }) => n.id))}
                  >
                    Mark all read
                  </button>
                )}
              </MenuLabel>
              {notifications.length === 0 ? (
                <p className="px-3 py-6 text-center text-xs text-muted-foreground">No platform alerts.</p>
              ) : (
                <div className="max-h-72 space-y-0.5 overflow-y-auto">
                  {notifications.slice(0, 8).map((n: { id: string; title: string; body?: string | null; severity: string; created_at: string }) => (
                    <button
                      key={n.id}
                      onClick={() => {
                        setViewing(!viewing);
                        if (!n.id) return;
                        markRead.mutate([n.id]);
                      }}
                      className={cn(
                        "flex w-full items-start gap-2.5 rounded-lg px-3 py-2 text-left transition-colors hover:bg-accent",
                      )}
                    >
                      <span className={cn("mt-1 h-2 w-2 shrink-0 rounded-full", SEVERITY_TONE[n.severity] ?? "bg-muted")} />
                      <span className="min-w-0">
                        <span className="block text-[13px] font-medium leading-snug">{n.title}</span>
                        {n.body && <span className="block truncate text-xs text-muted-foreground">{n.body}</span>}
                        <span className="mt-0.5 block text-[10px] text-muted-foreground">
                          {new Date(n.created_at).toLocaleString()}
                        </span>
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </Dropdown>

        <span className="hidden h-6 w-px bg-border sm:block" />

        <Dropdown
          trigger={
            <Avatar
              name={user?.full_name}
              className="bg-gradient-to-br from-amber-500 to-orange-600 text-white ring-2 ring-ring/30"
            />
          }
        >
          <MenuLabel>{user?.full_name}</MenuLabel>
          <MenuItem
            icon={<ShieldCheck className="h-4 w-4" />}
            onClick={() => router.push("/super-admin/settings")}
          >
            Platform settings
          </MenuItem>
          <MenuSeparator />
          <MenuItem icon={<ArrowLeft className="h-4 w-4" />} onClick={() => router.push("/dashboard")}>
            Back to school view
          </MenuItem>
          <MenuItem variant="danger" icon={<LogOut className="h-4 w-4" />} onClick={handleLogout}>
            Sign out
          </MenuItem>
        </Dropdown>
      </div>
    </header>
  );
}

export function PlatformBadge({ severity }: { severity: string }) {
  return (
    <Badge variant={severity === "critical" ? "destructive" : severity === "warning" ? "warning" : "info"}>
      {severity}
    </Badge>
  );
}