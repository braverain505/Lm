"use client";

import { motion } from "framer-motion";
import { Users, GraduationCap, BookOpen, TrendingUp, UserPlus, FileText, Calendar, Bell, Mail, Download } from "lucide-react";
import Link from "next/link";
import { useAuth } from "@/providers/auth-provider";
import { useDashboardSummary } from "@/hooks/use-api";
import { useSessionTerm } from "@/providers/session-context";

const ease = [0.25, 0.46, 0.45, 0.94] as const;

export function AdminDashboard() {
  const { user } = useAuth();
  const { term } = useSessionTerm();
  const { data: summary, isLoading } = useDashboardSummary(term?.id ?? undefined);

  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";

  // KPI data matching the design
  const kpis = [
    {
      label: "Total Students",
      value: summary?.kpis?.students || 2847,
      change: "+12.5%",
      changeLabel: "vs last month",
      icon: Users,
      color: "bg-blue-500",
      bgColor: "bg-blue-100",
    },
    {
      label: "Total Teachers",
      value: summary?.kpis?.teachers || 142,
      change: "+3.2%",
      changeLabel: "vs last month",
      icon: GraduationCap,
      color: "bg-purple-500",
      bgColor: "bg-purple-100",
    },
    {
      label: "Active Classes",
      value: summary?.kpis?.classes || 86,
      change: "+5.1%",
      changeLabel: "vs last month",
      icon: BookOpen,
      color: "bg-pink-500",
      bgColor: "bg-pink-100",
    },
    {
      label: "Attendance Rate",
      value: summary?.kpis?.attendance_rate != null ? `${Math.round(summary.kpis.attendance_rate)}%` : "94.2%",
      change: "+2.4%",
      changeLabel: "vs last month",
      icon: TrendingUp,
      color: "bg-green-500",
      bgColor: "bg-green-100",
    },
  ];

  const quickActions = [
    { label: "Add Student", icon: UserPlus, href: "/students", color: "bg-blue-500", bgColor: "bg-blue-100" },
    { label: "Create Report", icon: FileText, href: "/reports", color: "bg-purple-500", bgColor: "bg-purple-100" },
    { label: "Schedule Event", icon: Calendar, href: "/schedule", color: "bg-pink-500", bgColor: "bg-pink-100" },
    { label: "Send Notice", icon: Bell, href: "/notices", color: "bg-green-500", bgColor: "bg-green-100" },
    { label: "Email Parents", icon: Mail, href: "/communications", color: "bg-orange-500", bgColor: "bg-orange-100" },
    { label: "Export Data", icon: Download, href: "/exports", color: "bg-cyan-500", bgColor: "bg-cyan-100" },
  ];

  return (
    <div className="space-y-8">
      {/* Greeting */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease }}
      >
        <h2 className="text-[26px] font-bold tracking-tight text-foreground">
          {greeting}, {user?.full_name?.split(" ")[0] ?? "there"}.
        </h2>
        <p className="mt-1.5 text-[14px] text-muted-foreground/70">
          Here&apos;s what&apos;s happening across your school today.
        </p>
        {term && (
          <p className="mt-1 text-[13px] font-medium text-muted-foreground/50">{term.name}</p>
        )}
      </motion.div>

      {/* KPI Cards - 4 columns */}
      <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 md:grid-cols-2 lg:grid-cols-4">
        {kpis.map((kpi, idx) => {
          const Icon = kpi.icon;
          return (
            <motion.div
              key={kpi.label}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, delay: 0.08 + idx * 0.04, ease }}
              className="rounded-2xl border border-border/40 bg-white p-6 shadow-sm hover:shadow-md transition-shadow duration-200"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <p className="text-[13px] font-medium text-muted-foreground/70">{kpi.label}</p>
                  <p className="mt-2 text-[28px] font-bold text-foreground">{kpi.value}</p>
                  <p className="mt-2 text-[12px] text-green-600 font-medium">
                    {kpi.change} <span className="text-muted-foreground/50">{kpi.changeLabel}</span>
                  </p>
                </div>
                <div className={`${kpi.bgColor} rounded-2xl p-3 flex items-center justify-center`}>
                  <Icon className={`h-6 w-6 ${kpi.color} text-white`} />
                </div>
              </div>
            </motion.div>
          );
        })}
      </div>

      {/* Quick Actions */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.12, ease }}
        className="rounded-2xl border border-border/40 bg-white p-6 shadow-sm"
      >
        <h3 className="text-[15px] font-semibold text-foreground mb-1">Quick Actions</h3>
        <p className="text-[13px] text-muted-foreground/60 mb-6">Frequently used tasks</p>

        <div className="grid gap-6 grid-cols-2 sm:grid-cols-3 md:grid-cols-3 lg:grid-cols-6">
          {quickActions.map((action, idx) => {
            const Icon = action.icon;
            return (
              <Link
                key={action.label}
                href={action.href}
                className="flex flex-col items-center gap-3"
              >
                <div className={`${action.color} rounded-2xl p-4 flex items-center justify-center shadow-sm hover:shadow-md transition-shadow duration-200`}>
                  <Icon className="h-6 w-6 text-white" strokeWidth={2} />
                </div>
                <p className="text-[12px] font-medium text-foreground text-center">{action.label}</p>
              </Link>
            );
          })}
        </div>
      </motion.div>

      {/* Charts Section - Weekly Attendance + Upcoming Events */}
      <div className="grid gap-6 md:grid-cols-1 lg:grid-cols-2">
        {/* Weekly Attendance */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.16, ease }}
          className="rounded-2xl border border-border/40 bg-white p-6 shadow-sm"
        >
          <h3 className="text-[15px] font-semibold text-foreground mb-1">Weekly Attendance</h3>
          <p className="text-[13px] text-muted-foreground/60 mb-6">Student and teacher attendance overview</p>

          <div className="h-64 flex items-center justify-center bg-muted/30 rounded-lg">
            <p className="text-sm text-muted-foreground">Chart will render here</p>
          </div>
        </motion.div>

        {/* Upcoming Events */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.20, ease }}
          className="rounded-2xl border border-border/40 bg-white p-6 shadow-sm"
        >
          <h3 className="text-[15px] font-semibold text-foreground mb-1">Upcoming Events</h3>
          <p className="text-[13px] text-muted-foreground/60 mb-6">School calendar</p>

          <div className="space-y-4">
            <div className="flex items-start gap-4 pb-4 border-b border-border/40">
              <div className="flex-shrink-0 w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                <Calendar className="h-5 w-5 text-blue-600" />
              </div>
              <div className="flex-1">
                <p className="text-[13px] font-medium text-foreground">Parent-Teacher Meeting</p>
                <p className="text-[12px] text-muted-foreground/60 mt-1">Dec 15, 2025</p>
                <p className="text-[12px] text-muted-foreground/60">10:00 AM</p>
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
