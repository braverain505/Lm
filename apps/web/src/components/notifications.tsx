"use client";

import { Bell, CheckCircle2, Sparkles } from "lucide-react";
import Link from "next/link";
import { useMemo } from "react";

import { Dropdown } from "@/components/ui/dropdown";
import { Avatar } from "@/components/ui/avatar";
import { useDashboardSummary } from "@/hooks/use-api";
import { useSessionTerm } from "@/providers/session-context";
import { useAuth } from "@/providers/auth-provider";

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

  const items = useMemo(() => data?.activity?.slice(0, 6) ?? [], [data]);
  const count = data?.tasks?.reduce((acc, t) => acc + t.count, 0) ?? 0;

  return (
    <Dropdown
      contentClassName="w-80"
      trigger={
        <span className="relative flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground/50 transition-colors hover:bg-accent hover:text-foreground">
          <Bell className="h-4 w-4" />
          {count > 0 && (
            <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[9px] font-bold text-white">
              {count > 99 ? "99+" : count}
            </span>
          )}
        </span>
      }
    >
      {(close) => (
        <div>
          <div className="flex items-center justify-between border-b border-border/30 px-3 py-2.5">
            <p className="text-[13px] font-semibold text-foreground">Notifications</p>
            {count > 0 && <span className="text-[10.5px] text-muted-foreground/50">{count} pending</span>}
          </div>
          <div className="scrollbar-thin max-h-80 overflow-y-auto p-1.5">
            {isLoading ? (
              <p className="px-3 py-6 text-center text-[12px] text-muted-foreground/50">Loading…</p>
            ) : items.length === 0 ? (
              <div className="flex flex-col items-center gap-2 px-3 py-8 text-center">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-success/10">
                  <CheckCircle2 className="h-4 w-4 text-success" />
                </div>
                <p className="text-[12px] font-medium text-foreground/70">All caught up</p>
                <p className="text-[11px] text-muted-foreground/40">Recent actions will appear here.</p>
              </div>
            ) : (
              items.map((a) => (
                <Link
                  key={a.id}
                  href={a.href ?? "/dashboard"}
                  onClick={close}
                  className="flex items-start gap-3 rounded-lg px-2.5 py-2.5 transition-colors duration-100 hover:bg-muted/30"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[12px] font-medium text-foreground/80">{a.title}</p>
                    <p className="truncate text-[11px] text-muted-foreground/40">
                      {a.actor_name} · {relative(a.created_at)}
                    </p>
                  </div>
                </Link>
              ))
            )}
          </div>
          <div className="border-t border-border/30 p-1.5">
            <Link
              href="/dashboard"
              onClick={close}
              className="block rounded-lg px-3 py-2 text-center text-[12px] font-semibold text-primary transition-colors hover:bg-muted/30"
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
      trigger={<Avatar name={user?.full_name} className="h-8 w-8 cursor-pointer" />}
      contentClassName="w-60"
    >
      {(close) => (
        <div>
          <div className="flex items-center gap-3 border-b border-border/30 px-3 py-3">
            <Avatar name={user?.full_name} className="h-9 w-9" />
            <div className="min-w-0">
              <p className="truncate text-[13px] font-semibold text-foreground">{user?.full_name}</p>
              <p className="truncate text-[11px] text-muted-foreground/50">{user?.email}</p>
            </div>
          </div>
          <div className="px-3 py-2.5">
            <p className="text-[10px] font-medium text-muted-foreground/40 uppercase tracking-wider">Current role</p>
            <p className="mt-0.5 text-[12px] font-medium text-foreground/80 capitalize">
              {activeSchool?.role?.name ?? "Member"}
            </p>
          </div>
          <div className="border-t border-border/30" />
          <Link href="/settings" onClick={close} className="flex items-center gap-2 rounded-lg px-3 py-2 text-[12px] font-medium text-foreground/70 transition-colors hover:bg-muted/30 hover:text-foreground">
            Account settings
          </Link>
        </div>
      )}
    </Dropdown>
  );
}
