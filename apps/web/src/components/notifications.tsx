"use client";

import { motion, AnimatePresence } from "framer-motion";
import {
  Bell,
  CheckCircle2,
  LogOut,
  UserPlus,
  FileText,
  CalendarCheck,
  AlertTriangle,
  Info,
  GraduationCap,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Dropdown } from "@/components/ui/dropdown";
import { Avatar } from "@/components/ui/avatar";
import { useAuth } from "@/providers/auth-provider";

/* ─── Mock notifications (replace with real API when ready) ──────────── */

const MOCK_NOTIFICATIONS = [
  { id: "1", title: "New student enrolled", body: "JSS 1A — Amara Okafor", icon: UserPlus, color: "text-blue-600 bg-blue-50", time: "2m ago", unread: true },
  { id: "2", title: "Results compiled", body: "SS 3 — First Term results ready", icon: FileText, color: "text-violet-600 bg-violet-50", time: "18m ago", unread: true },
  { id: "3", title: "Attendance submitted", body: "JSS 2B — Morning session marked", icon: CalendarCheck, color: "text-emerald-600 bg-emerald-50", time: "1h ago", unread: true },
  { id: "4", title: "Fee payment received", body: "Chidinma Eze — NGN 45,000", icon: CheckCircle2, color: "text-amber-500 bg-amber-50", time: "2h ago", unread: false },
  { id: "5", title: "Low attendance alert", body: "JSS 3A — 3 students absent today", icon: AlertTriangle, color: "text-rose-500 bg-rose-50", time: "3h ago", unread: false },
  { id: "6", title: "Term results pending", body: "5 classes awaiting compilation", icon: GraduationCap, color: "text-cyan-600 bg-cyan-50", time: "5h ago", unread: false },
];

/* ─── Notifications bell ─────────────────────────────────────────────── */

export function Notifications() {
  const [readIds, setReadIds] = useState<Set<string>>(new Set());
  const notifications = MOCK_NOTIFICATIONS;
  const unreadCount = notifications.filter((n) => n.unread && !readIds.has(n.id)).length;

  function markAllRead() {
    setReadIds(new Set(notifications.map((n) => n.id)));
  }

  return (
    <Dropdown
      contentClassName="w-80 p-0"
      trigger={
        <motion.span
          className="relative flex h-9 w-9 items-center justify-center rounded-xl text-muted-foreground/50 transition-all duration-200 hover:bg-muted/50 hover:text-foreground"
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
        >
          <Bell className="h-[18px] w-[18px]" strokeWidth={1.75} />
          <AnimatePresence>
            {unreadCount > 0 && (
              <motion.span
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                exit={{ scale: 0 }}
                transition={{ type: "spring", stiffness: 500, damping: 15 }}
                className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-500 px-1 text-[9px] font-bold text-white shadow-sm"
              >
                {unreadCount}
              </motion.span>
            )}
          </AnimatePresence>
        </motion.span>
      }
    >
      {(close) => (
        <div className="overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between border-b border-border/20 px-4 py-3">
            <div className="flex items-center gap-2">
              <h3 className="text-[13px] font-semibold text-foreground">Notifications</h3>
              {unreadCount > 0 && (
                <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-rose-500/10 px-1.5 text-[9px] font-bold text-rose-500">
                  {unreadCount}
                </span>
              )}
            </div>
            {unreadCount > 0 && (
              <button
                onClick={markAllRead}
                className="text-[10px] font-semibold text-primary/70 hover:text-primary transition-colors"
              >
                Mark all read
              </button>
            )}
          </div>

          {/* Notification list */}
          <div className="scrollbar-thin max-h-80 overflow-y-auto">
            {notifications.length === 0 ? (
              <div className="flex flex-col items-center gap-2 px-4 py-10 text-center">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-50">
                  <CheckCircle2 className="h-5 w-5 text-emerald-500" />
                </div>
                <p className="text-[12px] font-medium text-foreground/60">All caught up</p>
                <p className="text-[11px] text-muted-foreground/40">No new notifications</p>
              </div>
            ) : (
              notifications.map((item, idx) => {
                const Icon = item.icon;
                const isUnread = item.unread && !readIds.has(item.id);
                return (
                  <motion.div
                    key={item.id}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.2, delay: idx * 0.03 }}
                    className="border-b border-border/10 last:border-0"
                  >
                    <div
                      className={`group flex items-start gap-3 px-4 py-3 transition-colors duration-150 hover:bg-muted/20 ${isUnread ? "bg-primary/[0.02]" : ""}`}
                    >
                      <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${item.color.split(" ")[1]}`}>
                        <Icon className={`h-4 w-4 ${item.color.split(" ")[0]}`} strokeWidth={1.75} />
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <p className="text-[12px] font-medium text-foreground/80 truncate">{item.title}</p>
                          {isUnread && <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-blue-500" />}
                        </div>
                        <p className="text-[11px] text-muted-foreground/45 truncate">{item.body}</p>
                      </div>
                      <span className="shrink-0 text-[9px] text-muted-foreground/35 mt-0.5">{item.time}</span>
                    </div>
                  </motion.div>
                );
              })
            )}
          </div>

          {/* Footer */}
          <div className="border-t border-border/20 px-2 py-2">
            <Link
              href="/dashboard"
              onClick={close}
              className="flex items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-[11px] font-semibold text-primary/70 transition-colors hover:bg-muted/20 hover:text-primary"
            >
              View all activity
            </Link>
          </div>
        </div>
      )}
    </Dropdown>
  );
}

/* ─── Profile menu ───────────────────────────────────────────────────── */

export function ProfileMenu() {
  const { user, activeSchool } = useAuth();
  const handleLogout = async () => {
    await fetch("/api/auth/logout", { method: "POST" });
    window.location.href = "/login";
  };

  return (
    <Dropdown
      trigger={
        <div className="flex items-center gap-2 rounded-xl px-2 py-1.5 transition-colors duration-200 hover:bg-muted/40 cursor-pointer">
          <Avatar name={user?.full_name} className="h-8 w-8 bg-gradient-to-br from-primary to-primary-hover text-xs font-semibold text-white" />
          <span className="hidden text-[12px] font-medium text-foreground/70 md:block">{user?.full_name?.split(" ")[0]}</span>
        </div>
      }
      contentClassName="w-60 p-0"
    >
      {(close) => (
        <div>
          <div className="flex items-center gap-3 border-b border-border/20 px-4 py-3.5">
            <Avatar name={user?.full_name} className="h-10 w-10 bg-gradient-to-br from-primary to-primary-hover text-sm font-semibold text-white" />
            <div className="min-w-0">
              <p className="truncate text-[13px] font-semibold text-foreground">{user?.full_name}</p>
              <p className="truncate text-[11px] text-muted-foreground/50">{user?.email}</p>
            </div>
          </div>
          <div className="px-4 py-2.5">
            <p className="text-[9px] font-semibold uppercase tracking-wider text-muted-foreground/40">Current role</p>
            <p className="mt-0.5 text-[12px] font-medium text-foreground/70 capitalize">{activeSchool?.role?.name ?? "Member"}</p>
          </div>
          <div className="border-t border-border/20" />
          <div className="p-1.5">
            <Link href="/settings" onClick={close} className="flex items-center gap-2 rounded-lg px-3 py-2 text-[12px] font-medium text-foreground/70 transition-colors hover:bg-muted/30 hover:text-foreground">
              Account settings
            </Link>
          </div>
          <div className="border-t border-border/20" />
          <div className="p-1.5">
            <button
              onClick={() => { close(); handleLogout(); }}
              className="w-full flex items-center gap-2 rounded-lg px-3 py-2 text-[12px] font-medium text-rose-500 transition-colors hover:bg-rose-50"
            >
              <LogOut className="h-3.5 w-3.5" />
              Sign out
            </button>
          </div>
        </div>
      )}
    </Dropdown>
  );
}
