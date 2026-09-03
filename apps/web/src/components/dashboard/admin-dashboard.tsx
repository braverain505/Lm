"use client";

import { motion } from "framer-motion";
import { UserPlus, FileText, Calendar, Bell, Mail, Download } from "lucide-react";
import Link from "next/link";
import { useAuth } from "@/providers/auth-provider";
import { useDashboardSummary } from "@/hooks/use-api";
import { useSessionTerm } from "@/providers/session-context";
import { cn } from "@/lib/utils";

const ease = [0.25, 0.46, 0.45, 0.94] as const;

export function AdminDashboard() {
  const { user } = useAuth();
  const { term } = useSessionTerm();
  const { data: summary } = useDashboardSummary(term?.id ?? undefined);

  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";

  const quickActions = [
    { label: "Add Student", icon: UserPlus, href: "/students", tile: "bg-blue-50 hover:bg-blue-100", iconColor: "text-blue-600" },
    { label: "Create Report", icon: FileText, href: "/reports", tile: "bg-purple-50 hover:bg-purple-100", iconColor: "text-purple-600" },
    { label: "Schedule Event", icon: Calendar, href: "/schedule", tile: "bg-pink-50 hover:bg-pink-100", iconColor: "text-pink-600" },
    { label: "Send Notice", icon: Bell, href: "/notices", tile: "bg-green-50 hover:bg-green-100", iconColor: "text-green-600" },
    { label: "Email Parents", icon: Mail, href: "/communications", tile: "bg-orange-50 hover:bg-orange-100", iconColor: "text-orange-600" },
    { label: "Export Data", icon: Download, href: "/exports", tile: "bg-cyan-50 hover:bg-cyan-100", iconColor: "text-cyan-600" },
  ];

  return (
    <div className="space-y-8 rounded-3xl bg-gradient-to-b from-indigo-50/60 via-transparent to-transparent p-1 sm:p-2">
      {/* Greeting */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease }}
        className="pt-2"
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

      {/* Quick Actions */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.12, ease }}
        className="rounded-2xl border border-border/60 bg-card p-6 shadow-xs hover:shadow-card transition-all duration-200"
      >
        <h3 className="text-[14px] font-semibold tracking-tight text-foreground">Quick Actions</h3>
        <p className="mt-1 text-[12px] text-muted-foreground/60">Frequently used tasks</p>

        <div className="mt-6 grid gap-6 grid-cols-2 sm:grid-cols-3 md:grid-cols-3 lg:grid-cols-6">
          {quickActions.map((action) => {
            const Icon = action.icon;
            return (
              <Link
                key={action.label}
                href={action.href}
                className="group flex flex-col items-center gap-3 transition-all duration-200"
              >
                <div className={cn("flex items-center justify-center h-16 w-16 rounded-2xl transition-colors duration-200", action.tile)}>
                  <Icon className={cn("h-8 w-8 transition-colors duration-200", action.iconColor)} strokeWidth={1.75} />
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
          className="rounded-2xl border border-border/60 bg-card p-6 shadow-xs hover:shadow-card transition-all duration-200"
        >
          <h3 className="text-[14px] font-semibold tracking-tight text-foreground">Weekly Attendance</h3>
          <p className="mt-1 text-[12px] text-muted-foreground/60">Student and teacher attendance overview</p>

          <div className="mt-6 h-64 flex items-center justify-center bg-muted/30 rounded-lg">
            <p className="text-sm text-muted-foreground">Chart will render here</p>
          </div>
        </motion.div>

        {/* Upcoming Events */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.20, ease }}
          className="rounded-2xl border border-border/60 bg-card p-6 shadow-xs hover:shadow-card transition-all duration-200"
        >
          <h3 className="text-[14px] font-semibold tracking-tight text-foreground">Upcoming Events</h3>
          <p className="mt-1 text-[12px] text-muted-foreground/60">School calendar</p>

          <div className="mt-6 space-y-4">
            <div className="flex items-start gap-4 pb-4 border-b border-border/40">
              <div className="flex-shrink-0 w-10 h-10 bg-indigo-100 rounded-lg flex items-center justify-center">
                <Calendar className="h-5 w-5 text-indigo-600" />
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
