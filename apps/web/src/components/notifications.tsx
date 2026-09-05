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
  X,
  ArrowRight,
  Clock,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Dropdown } from "@/components/ui/dropdown";
import { Avatar } from "@/components/ui/avatar";
import { useAuth } from "@/providers/auth-provider";
import { isSchoolAdminRole } from "@/lib/roles";

/* ─── Mock notifications (replace with real API when ready) ──────────── */

type Notification = {
  id: string;
  title: string;
  body: string;
  detail: string;
  icon: typeof Bell;
  color: string;
  time: string;
  unread: boolean;
};

const MOCK_NOTIFICATIONS: Notification[] = [
  {
    id: "1",
    title: "New student enrolled",
    body: "JSS 1A — Amara Okafor",
    detail: "Amara Okafor has been successfully enrolled into Junior Secondary School 1A. The student was registered by Guardian Mrs. Okafor. All required documents have been uploaded and verified. The student is assigned to class teacher Mrs. Adekunle.",
    icon: UserPlus,
    color: "text-blue-600 bg-blue-50",
    time: "2m ago",
    unread: true,
  },
  {
    id: "2",
    title: "Results compiled",
    body: "SS 3 — First Term results ready",
    detail: "First Term results for Senior Secondary School 3 have been compiled and are ready for review. 32 students have been graded across 8 subjects. Average score: 72.4%. Pass rate: 81.2%. You can now approve and publish the results to the portal.",
    icon: FileText,
    color: "text-violet-600 bg-violet-50",
    time: "18m ago",
    unread: true,
  },
  {
    id: "3",
    title: "Attendance submitted",
    body: "JSS 2B — Morning session marked",
    detail: "Morning attendance for JSS 2B has been submitted by Mr. Chukwu. 28 students present, 2 absent, 1 late. Attendance rate: 90.3%. Parents of absent students will receive automatic SMS notifications.",
    icon: CalendarCheck,
    color: "text-emerald-600 bg-emerald-50",
    time: "1h ago",
    unread: true,
  },
  {
    id: "4",
    title: "Fee payment received",
    body: "Chidinma Eze — NGN 45,000",
    detail: "Payment of NGN 45,000 received from Chidinma Eze (SS 2A) for Second Term school fees. Transaction reference: TXN-2025-0847. Remaining balance: NGN 15,000. Receipt has been automatically generated and sent to the parent's email.",
    icon: CheckCircle2,
    color: "text-amber-500 bg-amber-50",
    time: "2h ago",
    unread: false,
  },
  {
    id: "5",
    title: "Low attendance alert",
    body: "JSS 3A — 3 students absent today",
    detail: "Attendance for JSS 3A shows 3 students absent today, which is above the normal threshold. Affected students: Emeka Nwosu, Fatima Abubakar, Yusuf Bello. Consider reaching out to their guardians. This is the 2nd consecutive absence for 2 of these students.",
    icon: AlertTriangle,
    color: "text-rose-500 bg-rose-50",
    time: "3h ago",
    unread: false,
  },
  {
    id: "6",
    title: "Term results pending",
    body: "5 classes awaiting compilation",
    detail: "5 classes are still awaiting result compilation for the current term: JSS 1A, JSS 1B, SS 2A, SS 2B, and Primary 6. Teachers have been notified. Deadline for score entry is December 20, 2025. 3 teachers have not yet submitted any scores.",
    icon: GraduationCap,
    color: "text-cyan-600 bg-cyan-50",
    time: "5h ago",
    unread: false,
  },
];

/* ─── Detail view ────────────────────────────────────────────────────── */

function NotificationDetail({
  notification,
  onClose,
}: {
  notification: Notification;
  onClose: () => void;
}) {
  const Icon = notification.icon;
  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 20 }}
      transition={{ duration: 0.25 }}
      className="absolute inset-0 z-10 flex flex-col bg-white"
    >
      {/* Header */}
      <div className="flex items-center gap-3 border-b border-border/20 px-4 py-3">
        <button
          onClick={onClose}
          className="flex h-7 w-7 items-center justify-center rounded-lg text-muted-foreground/50 transition-colors hover:bg-muted/30 hover:text-foreground"
        >
          <X className="h-4 w-4" />
        </button>
        <div className="flex items-center gap-2">
          <div className={`flex h-7 w-7 items-center justify-center rounded-lg ${notification.color.split(" ")[1]}`}>
            <Icon className={`h-3.5 w-3.5 ${notification.color.split(" ")[0]}`} strokeWidth={1.75} />
          </div>
          <h3 className="text-[13px] font-semibold text-foreground">Notification</h3>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-4 py-5">
        <div className="mb-4">
          <h2 className="text-[16px] font-bold tracking-tight text-foreground">
            {notification.title}
          </h2>
          <p className="mt-1 text-[13px] font-medium text-muted-foreground/60">
            {notification.body}
          </p>
        </div>

        <div className="mb-4 flex items-center gap-2 text-[11px] text-muted-foreground/40">
          <Clock className="h-3 w-3" />
          {notification.time}
        </div>

        <div className="h-px bg-gradient-to-r from-transparent via-border to-transparent mb-4" />

        <p className="text-[13px] leading-relaxed text-foreground/70">
          {notification.detail}
        </p>
      </div>

      {/* Footer */}
      <div className="border-t border-border/20 px-4 py-3">
        <button
          onClick={onClose}
          className="flex h-9 w-full items-center justify-center gap-1.5 rounded-xl bg-muted/30 text-[12px] font-semibold text-foreground/60 transition-colors hover:bg-muted/50"
        >
          Dismiss
        </button>
      </div>
    </motion.div>
  );
}

/* ─── Notifications bell ─────────────────────────────────────────────── */

export function Notifications() {
  const [readIds, setReadIds] = useState<Set<string>>(new Set());
  const [selected, setSelected] = useState<Notification | null>(null);
  const notifications = MOCK_NOTIFICATIONS;
  const unreadCount = notifications.filter((n) => n.unread && !readIds.has(n.id)).length;

  function markAllRead() {
    setReadIds(new Set(notifications.map((n) => n.id)));
  }

  function handleClick(n: Notification, e: React.MouseEvent) {
    // Prevent the Dropdown's mousedown listener from closing the dropdown
    e.stopPropagation();
    e.preventDefault();
    setReadIds((prev) => new Set(prev).add(n.id));
    setSelected(n);
  }

  function goBack() {
    setSelected(null);
  }

  return (
    <Dropdown
      contentClassName="w-80 p-0"
      onOpenChange={(open) => { if (!open) setSelected(null); }}
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
        <div className="overflow-hidden relative" onMouseDown={(e) => e.stopPropagation()}>
          <AnimatePresence mode="wait">
            {selected ? (
              <NotificationDetail
                key="detail"
                notification={selected}
                onClose={() => setSelected(null)}
              />
            ) : (
              <motion.div
                key="list"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
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
                          <button
                            onClick={(e) => handleClick(item, e)}
                            className={`w-full group flex items-start gap-3 px-4 py-3 text-left transition-colors duration-150 hover:bg-muted/20 ${isUnread ? "bg-primary/[0.02]" : ""}`}
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
                            <div className="flex shrink-0 flex-col items-end gap-1">
                              <span className="text-[9px] text-muted-foreground/35">{item.time}</span>
                              <ArrowRight className="h-3 w-3 text-muted-foreground/20 group-hover:text-primary/40 transition-colors" />
                            </div>
                          </button>
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
              </motion.div>
            )}
          </AnimatePresence>
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
          {isSchoolAdminRole(activeSchool?.role?.code) && (
            <>
              <div className="border-t border-border/20" />
              <div className="p-1.5">
                <Link href="/settings" onClick={close} className="flex items-center gap-2 rounded-lg px-3 py-2 text-[12px] font-medium text-foreground/70 transition-colors hover:bg-muted/30 hover:text-foreground">
                  Account settings
                </Link>
              </div>
            </>
          )}
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
