"use client";

import { Bell, Bot, CheckCircle2, FileText, Sparkles, UserPlus, Users, Wallet } from "lucide-react";
import Link from "next/link";
import { useMemo } from "react";

import { Dropdown } from "@/components/ui/dropdown";
import { Avatar } from "@/components/ui/avatar";
import { useDashboardSummary } from "@/hooks/use-api";
import { useSessionTerm } from "@/providers/session-context";
import { useAuth } from "@/providers/auth-provider";

const KIND_ICON: Record<string, React.ElementType> = {
  result: FileText,
  student: UserPlus,
  staff: Users,
  payment: Wallet,
  ai: Bot,
  other: Sparkles,
};

function relative(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}

export function Notifications() {
  const { term } = useSessionTerm();
  const { data, isLoading } = useDashboardSummary(term?.id ?? undefined);

  // Lazily read recent activity for the bell preview (real data, tenant-scoped).
  const items = useMemo(() => data?.activity?.slice(0, 6) ?? [], [data]);
  const count = data?.tasks?.reduce((acc, t) => acc + t.count, 0) ?? 0;

  return (
    <Dropdown
      contentClassName="w-80"
      trigger={
        <span className="relative flex h-9 w-9 items-center justify-center rounded-lg border border-input bg-background text-muted-foreground shadow-card transition-colors hover:bg-accent/60 hover:text-foreground">
          <Bell className="h-4 w-4" />
          {count > 0 && (
            <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-bold text-white">
              {count > 99 ? "99+" : count}
            </span>
          )}
        </span>
      }
    >
      {(close) => (
        <div>
          <div className="flex items-center justify-between border-b px-3 py-2.5">
            <p className="text-sm font-semibold">Notifications</p>
            {count > 0 && <span className="text-[11px] text-muted-foreground">{count} pending tasks</span>}
          </div>
          <div className="scrollbar-thin max-h-80 overflow-y-auto p-1.5">
            {isLoading ? (
              <p className="px-3 py-6 text-center text-sm text-muted-foreground">Loading activity…</p>
            ) : items.length === 0 ? (
              <div className="flex flex-col items-center gap-2 px-3 py-8 text-center">
                <CheckCircle2 className="h-6 w-6 text-success" />
                <p className="text-sm font-medium">You&apos;re all caught up</p>
                <p className="text-xs text-muted-foreground">Recent actions will appear here.</p>
              </div>
            ) : (
              items.map((a) => {
                const Icon = KIND_ICON[a.kind] ?? Sparkles;
                return (
                  <Link
                    key={a.id}
                    href={a.href ?? "/dashboard"}
                    onClick={close}
                    className="flex items-start gap-3 rounded-lg px-3 py-2.5 transition-colors hover:bg-accent"
                  >
                    <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                      <Icon className="h-4 w-4" />
                    </span>
                    <div className="min-w-0">
                      <p className="truncate text-[13px] font-medium">{a.title}</p>
                      <p className="truncate text-xs text-muted-foreground">
                        {a.actor_name} · {relative(a.created_at)}
                      </p>
                    </div>
                  </Link>
                );
              })
            )}
          </div>
          <div className="border-t p-1.5">
            <Link
              href="/dashboard"
              onClick={close}
              className="block rounded-lg px-3 py-2 text-center text-[13px] font-medium text-primary hover:bg-accent"
            >
              View activity
            </Link>
          </div>
        </div>
      )}
    </Dropdown>
  );
}

export function ProfileMenu() {
  const { user, activeSchool } = useAuth();
  return (
    <Dropdown
      trigger={<Avatar name={user?.full_name} className="h-9 w-9 ring-2 ring-white ring-offset-2 ring-offset-background" />}
      contentClassName="w-64"
    >
      {(close) => (
        <div>
          <div className="flex items-center gap-3 border-b px-3 py-3">
            <Avatar name={user?.full_name} className="h-10 w-10" />
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold">{user?.full_name}</p>
              <p className="truncate text-xs text-muted-foreground">{user?.email}</p>
            </div>
          </div>
          <div className="px-3 py-2">
            <p className="text-[11px] uppercase tracking-wider text-muted-foreground">Current role</p>
            <p className="mt-0.5 text-[13px] font-medium capitalize">
              {activeSchool?.role?.name ?? "Member"}
            </p>
          </div>
          <div className="border-t" />
          <Link href="/settings" onClick={close} className="flex items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] font-medium hover:bg-accent">
            <span className="text-muted-foreground">Account settings</span>
          </Link>
        </div>
      )}
    </Dropdown>
  );
}