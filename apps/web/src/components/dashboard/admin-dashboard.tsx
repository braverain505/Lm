"use client";

import { motion } from "framer-motion";
import {
  Users,
  GraduationCap,
  BookOpen,
  CalendarCheck,
  UserPlus,
  FileText,
  Calendar,
  Bell,
  Mail,
  Download,
  ArrowUpRight,
  Clock,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useAuth } from "@/providers/auth-provider";
import { useSessionTerm } from "@/providers/session-context";
import { cn } from "@/lib/utils";
import {
  PerformanceTrendChart,
  AttendanceOverviewChart,
  EnrollmentDonut,
} from "@/components/dashboard/premium-charts";

const ease = [0.25, 0.46, 0.45, 0.94] as const;

/* ─── KPI cards ─────────────────────────────────────────────────────────── */

const kpis = [
  {
    label: "Total Students",
    value: "2,847",
    delta: "+12.5%",
    deltaLabel: "vs last month",
    icon: Users,
    color: "text-blue-600",
    bg: "bg-blue-50",
    ring: "ring-blue-100",
    href: "/students",
  },
  {
    label: "Total Teachers",
    value: "142",
    delta: "+3.2%",
    deltaLabel: "vs last month",
    icon: GraduationCap,
    color: "text-violet-600",
    bg: "bg-violet-50",
    ring: "ring-violet-100",
    href: "/teachers",
  },
  {
    label: "Active Classes",
    value: "86",
    delta: "+5.1%",
    deltaLabel: "vs last month",
    icon: BookOpen,
    color: "text-rose-500",
    bg: "bg-rose-50",
    ring: "ring-rose-100",
    href: "/classes",
  },
  {
    label: "Attendance Rate",
    value: "94.2%",
    delta: "+2.4%",
    deltaLabel: "vs last month",
    icon: CalendarCheck,
    color: "text-emerald-600",
    bg: "bg-emerald-50",
    ring: "ring-emerald-100",
    href: "/attendance",
  },
];

/* ─── Quick actions ─────────────────────────────────────────────────────── */

const quickActions = [
  { label: "Add Student", icon: UserPlus, href: "/students", color: "text-blue-600", bg: "bg-blue-50 hover:bg-blue-100" },
  { label: "Create Report", icon: FileText, href: "/reports", color: "text-violet-600", bg: "bg-violet-50 hover:bg-violet-100" },
  { label: "Schedule Event", icon: Calendar, href: "/schedule", color: "text-rose-500", bg: "bg-rose-50 hover:bg-rose-100" },
  { label: "Send Notice", icon: Bell, href: "/notices", color: "text-emerald-600", bg: "bg-emerald-50 hover:bg-emerald-100" },
  { label: "Email Parents", icon: Mail, href: "/communications", color: "text-amber-500", bg: "bg-amber-50 hover:bg-amber-100" },
  { label: "Export Data", icon: Download, href: "/exports", color: "text-cyan-600", bg: "bg-cyan-50 hover:bg-cyan-100" },
];

/* ─── Activity feed (static) ────────────────────────────────────────────── */

const recentActivity = [
  { title: "New student enrolled", detail: "JSS 1A — Amara Okafor", time: "2m ago", icon: UserPlus, color: "text-blue-600 bg-blue-50" },
  { title: "Results compiled", detail: "SS 3 — First Term", time: "18m ago", icon: FileText, color: "text-violet-600 bg-violet-50" },
  { title: "Attendance marked", detail: "JSS 2B — Morning session", time: "1h ago", icon: CalendarCheck, color: "text-emerald-600 bg-emerald-50" },
  { title: "Fee payment received", detail: "Chidinma Eze — NGN 45,000", time: "2h ago", icon: Sparkles, color: "text-amber-500 bg-amber-50" },
];

/* ─── Component ─────────────────────────────────────────────────────────── */

export function AdminDashboard() {
  const { user } = useAuth();
  const { term } = useSessionTerm();
  const [time, setTime] = useState(() => new Date());

  useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const hour = time.getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";

  return (
    <div className="space-y-8">
      {/* ── Greeting ─────────────────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease }}
      >
        <h1 className="text-[28px] font-bold tracking-tight text-foreground">
          {greeting}, {user?.full_name?.split(" ")[0] ?? "there"} 👋
        </h1>
        <p className="mt-1.5 text-[14px] text-muted-foreground/60">
          Here&apos;s what&apos;s happening across your school today.
        </p>
        <div className="mt-2 flex items-center gap-3">
          {term && (
            <p className="inline-flex items-center gap-1.5 rounded-full bg-primary/5 px-3 py-1 text-[12px] font-medium text-primary/70">
              <span className="h-1.5 w-1.5 rounded-full bg-primary/60" />
              {term.name}
            </p>
          )}
          <p className="inline-flex items-center gap-1.5 rounded-full bg-muted/30 px-3 py-1 text-[11px] font-medium text-muted-foreground/50">
            <Clock className="h-3 w-3" />
            {time.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
          </p>
        </div>
      </motion.div>

      {/* ── KPI Cards ────────────────────────────────────────────── */}
      <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-4">
        {kpis.map((kpi, idx) => {
          const Icon = kpi.icon;
          return (
            <motion.div
              key={kpi.label}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, delay: 0.06 + idx * 0.05, ease }}
            >
              <Link
                href={kpi.href}
                className="group relative block rounded-2xl border border-white/60 bg-white p-5 shadow-[0_1px_3px_rgba(0,0,0,0.04)] transition-all duration-200 hover:shadow-[0_4px_12px_rgba(0,0,0,0.06)] hover:-translate-y-0.5"
              >
                <div className="flex items-start justify-between">
                  <div className="min-w-0 flex-1">
                    <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/50">
                      {kpi.label}
                    </p>
                    <p className="mt-2 text-[26px] font-bold tracking-tight text-foreground">
                      {kpi.value}
                    </p>
                    <div className="mt-2 flex items-center gap-1.5">
                      <span className="inline-flex items-center gap-0.5 rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-600">
                        <ArrowUpRight className="h-3 w-3" />
                        {kpi.delta}
                      </span>
                      <span className="text-[10px] text-muted-foreground/40">{kpi.deltaLabel}</span>
                    </div>
                  </div>
                  <div className={cn("flex h-11 w-11 items-center justify-center rounded-xl ring-1", kpi.bg, kpi.ring)}>
                    <Icon className={cn("h-5 w-5", kpi.color)} strokeWidth={1.75} />
                  </div>
                </div>
              </Link>
            </motion.div>
          );
        })}
      </div>

      {/* ── Quick Actions ────────────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.15, ease }}
        className="rounded-2xl border border-white/60 bg-white p-6 shadow-[0_1px_3px_rgba(0,0,0,0.04)]"
      >
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-[14px] font-semibold tracking-tight text-foreground">Quick Actions</h3>
            <p className="mt-0.5 text-[12px] text-muted-foreground/50">Frequently used tasks</p>
          </div>
          <Clock className="h-4 w-4 text-muted-foreground/30" />
        </div>

        <div className="mt-5 grid grid-cols-3 gap-3 sm:grid-cols-6">
          {quickActions.map((action, idx) => {
            const Icon = action.icon;
            return (
              <motion.div
                key={action.label}
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.3, delay: 0.2 + idx * 0.03, ease }}
              >
                <Link
                  href={action.href}
                  className="group flex flex-col items-center gap-2.5 rounded-xl p-3 transition-all duration-200 hover:bg-muted/30"
                >
                  <div className={cn("flex h-12 w-12 items-center justify-center rounded-xl transition-transform duration-200 group-hover:scale-110", action.bg)}>
                    <Icon className={cn("h-5 w-5", action.color)} strokeWidth={1.75} />
                  </div>
                  <span className="text-[11px] font-medium text-foreground/70 text-center leading-tight">{action.label}</span>
                </Link>
              </motion.div>
            );
          })}
        </div>
      </motion.div>

      {/* ── Charts Row ────────────────────────────────────────────── */}
      <div className="grid gap-5 lg:grid-cols-3">
        {/* Performance Trend */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.2, ease }}
          className="rounded-2xl border border-white/60 bg-white p-6 shadow-[0_1px_3px_rgba(0,0,0,0.04)]"
        >
          <div className="mb-4">
            <h3 className="text-[14px] font-semibold tracking-tight text-foreground">Performance Trend</h3>
            <p className="mt-0.5 text-[12px] text-muted-foreground/50">Average score & pass rate</p>
          </div>
          <div className="mb-3 flex items-center gap-4 text-[10px]">
            <span className="flex items-center gap-1.5 text-muted-foreground/50">
              <span className="h-1.5 w-1.5 rounded-full bg-[#6366f1]" /> Average
            </span>
            <span className="flex items-center gap-1.5 text-muted-foreground/50">
              <span className="h-1.5 w-1.5 rounded-full bg-[#10b981]" /> Pass rate
            </span>
          </div>
          <PerformanceTrendChart
            data={[
              { month: "Sep", avg: 68, pass: 72 },
              { month: "Oct", avg: 71, pass: 75 },
              { month: "Nov", avg: 74, pass: 78 },
              { month: "Dec", avg: 72, pass: 76 },
              { month: "Jan", avg: 76, pass: 80 },
              { month: "Feb", avg: 78, pass: 82 },
            ]}
            height={180}
          />
        </motion.div>

        {/* Attendance Overview */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.24, ease }}
          className="rounded-2xl border border-white/60 bg-white p-6 shadow-[0_1px_3px_rgba(0,0,0,0.04)]"
        >
          <div className="mb-4">
            <h3 className="text-[14px] font-semibold tracking-tight text-foreground">Attendance Overview</h3>
            <p className="mt-0.5 text-[12px] text-muted-foreground/50">This week&apos;s breakdown</p>
          </div>
          <div className="mb-3 flex items-center gap-4 text-[10px]">
            <span className="flex items-center gap-1.5 text-muted-foreground/50">
              <span className="h-1.5 w-1.5 rounded-full bg-[#10b981]" /> Present
            </span>
            <span className="flex items-center gap-1.5 text-muted-foreground/50">
              <span className="h-1.5 w-1.5 rounded-full bg-[#f59e0b]" /> Late
            </span>
            <span className="flex items-center gap-1.5 text-muted-foreground/50">
              <span className="h-1.5 w-1.5 rounded-full bg-[#f43f5e]" /> Absent
            </span>
          </div>
          <AttendanceOverviewChart
            data={[
              { name: "Mon", present: 245, absent: 18, late: 12 },
              { name: "Tue", present: 252, absent: 14, late: 9 },
              { name: "Wed", present: 248, absent: 20, late: 11 },
              { name: "Thu", present: 255, absent: 12, late: 8 },
              { name: "Fri", present: 240, absent: 22, late: 15 },
            ]}
            height={180}
          />
        </motion.div>

        {/* Enrollment Distribution */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.28, ease }}
          className="rounded-2xl border border-white/60 bg-white p-6 shadow-[0_1px_3px_rgba(0,0,0,0.04)]"
        >
          <div className="mb-4">
            <h3 className="text-[14px] font-semibold tracking-tight text-foreground">Enrollment</h3>
            <p className="mt-0.5 text-[12px] text-muted-foreground/50">Students by level</p>
          </div>
          <EnrollmentDonut
            data={[
              { name: "Primary", value: 820, color: "#6366f1" },
              { name: "JSS", value: 945, color: "#10b981" },
              { name: "SSS", value: 680, color: "#f59e0b" },
              { name: "Other", value: 402, color: "#f43f5e" },
            ]}
            total={2847}
            height={170}
          />
          <div className="mt-2 grid grid-cols-2 gap-2">
            {[
              { label: "Primary", value: 820, color: "#6366f1" },
              { label: "JSS", value: 945, color: "#10b981" },
              { label: "SSS", value: 680, color: "#f59e0b" },
              { label: "Other", value: 402, color: "#f43f5e" },
            ].map((item) => (
              <div key={item.label} className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full" style={{ backgroundColor: item.color }} />
                <span className="text-[10px] text-muted-foreground/50">{item.label}</span>
                <span className="text-[10px] font-semibold text-foreground/60 ml-auto">{item.value}</span>
              </div>
            ))}
          </div>
        </motion.div>
      </div>

      {/* ── Bottom Grid: Activity + Upcoming ─────────────────────── */}
      <div className="grid gap-5 lg:grid-cols-5">
        {/* Recent Activity */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.22, ease }}
          className="lg:col-span-3 rounded-2xl border border-white/60 bg-white p-6 shadow-[0_1px_3px_rgba(0,0,0,0.04)]"
        >
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-[14px] font-semibold tracking-tight text-foreground">Recent Activity</h3>
              <p className="mt-0.5 text-[12px] text-muted-foreground/50">Latest changes across the school</p>
            </div>
            <Link href="/activity" className="text-[11px] font-semibold text-primary/70 hover:text-primary transition-colors">
              View all
            </Link>
          </div>
          <div className="space-y-1">
            {recentActivity.map((item, idx) => {
              const Icon = item.icon;
              return (
                <motion.div
                  key={idx}
                  initial={{ opacity: 0, x: -5 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.3, delay: 0.28 + idx * 0.04, ease }}
                  className="flex items-center gap-3 rounded-xl px-3 py-2.5 transition-colors duration-150 hover:bg-muted/20"
                >
                  <div className={cn("flex h-9 w-9 shrink-0 items-center justify-center rounded-lg", item.color.split(" ")[1])}>
                    <Icon className={cn("h-4 w-4", item.color.split(" ")[0])} strokeWidth={1.75} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-[12px] font-medium text-foreground/80 truncate">{item.title}</p>
                    <p className="text-[11px] text-muted-foreground/45 truncate">{item.detail}</p>
                  </div>
                  <span className="shrink-0 text-[10px] text-muted-foreground/35">{item.time}</span>
                </motion.div>
              );
            })}
          </div>
        </motion.div>

        {/* Upcoming Events */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.26, ease }}
          className="lg:col-span-2 rounded-2xl border border-white/60 bg-white p-6 shadow-[0_1px_3px_rgba(0,0,0,0.04)]"
        >
          <div className="mb-4">
            <h3 className="text-[14px] font-semibold tracking-tight text-foreground">Upcoming Events</h3>
            <p className="mt-0.5 text-[12px] text-muted-foreground/50">School calendar</p>
          </div>
          <div className="space-y-3">
            {[
              { title: "Parent-Teacher Meeting", date: "Dec 15, 2025", time: "10:00 AM", color: "bg-violet-50 text-violet-600" },
              { title: "Mid-Term Break", date: "Dec 20, 2025", time: "All day", color: "bg-rose-50 text-rose-500" },
              { title: "Sports Day", date: "Jan 10, 2026", time: "9:00 AM", color: "bg-emerald-50 text-emerald-600" },
            ].map((event, idx) => (
              <div key={idx} className="flex items-start gap-3 rounded-xl px-2 py-2">
                <div className={cn("flex h-9 w-9 shrink-0 items-center justify-center rounded-lg", event.color.split(" ")[0])}>
                  <Calendar className={cn("h-4 w-4", event.color.split(" ")[1])} strokeWidth={1.75} />
                </div>
                <div className="min-w-0">
                  <p className="text-[12px] font-medium text-foreground/80">{event.title}</p>
                  <p className="text-[11px] text-muted-foreground/45">{event.date} · {event.time}</p>
                </div>
              </div>
            ))}
          </div>
        </motion.div>
      </div>
    </div>
  );
}
