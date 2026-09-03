"use client";

import { motion } from "framer-motion";
import {
  Users,
  GraduationCap,
  BookOpen,
  CalendarCheck,
  ClipboardCheck,
  BarChart3,
  FileText,
  Settings,
  ArrowUpRight,
  TrendingUp,
  Shield,
  Clock,
} from "lucide-react";
import Link from "next/link";

import { useSessionTerm } from "@/providers/session-context";
import { useAuth } from "@/providers/auth-provider";
import { cn } from "@/lib/utils";

const ease = [0.25, 0.46, 0.45, 0.94] as const;

/* ─── Greeting ──────────────────────────────────────────────────────────── */

function Greeting() {
  const { user } = useAuth();
  const { term } = useSessionTerm();
  const hour = new Date().getHours();
  const part = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
  const today = new Date().toLocaleDateString(undefined, {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease }}
    >
      <h1 className="text-[28px] font-bold tracking-tight text-foreground">
        {part}, {user?.full_name?.split(" ")[0] ?? "there"} 👋
      </h1>
      <p className="mt-1.5 text-[14px] text-muted-foreground/60">
        Here&apos;s what&apos;s happening today — {today}
      </p>
      {term && (
        <p className="mt-1 inline-flex items-center gap-1.5 rounded-full bg-primary/5 px-3 py-1 text-[12px] font-medium text-primary/70">
          <span className="h-1.5 w-1.5 rounded-full bg-primary/60" />
          {term.name}
        </p>
      )}
    </motion.div>
  );
}

/* ─── Stat card helper ──────────────────────────────────────────────────── */

function StatCard({
  label,
  icon: Icon,
  color,
  bg,
  ring,
  href,
  delay,
}: {
  label: string;
  icon: React.ElementType;
  color: string;
  bg: string;
  ring: string;
  href: string;
  delay: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay, ease }}
    >
      <Link
        href={href}
        className="group flex items-center gap-4 rounded-2xl border border-white/60 bg-white p-5 shadow-[0_1px_3px_rgba(0,0,0,0.04)] transition-all duration-200 hover:shadow-[0_4px_12px_rgba(0,0,0,0.06)] hover:-translate-y-0.5"
      >
        <div className={cn("flex h-11 w-11 items-center justify-center rounded-xl ring-1", bg, ring)}>
          <Icon className={cn("h-5 w-5", color)} strokeWidth={1.75} />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-[13px] font-medium text-foreground/80">{label}</p>
        </div>
        <ArrowUpRight className="h-4 w-4 text-muted-foreground/25 transition-colors duration-200 group-hover:text-primary/60" />
      </Link>
    </motion.div>
  );
}

/* ─── Admin variant ─────────────────────────────────────────────────────── */

function AdminVariant() {
  const adminLinks = [
    { label: "Manage Students", desc: "Enroll, edit, and view student records", icon: Users, color: "text-blue-600", bg: "bg-blue-50", ring: "ring-blue-100", href: "/students" },
    { label: "Manage Teachers", desc: "Staff records and assignments", icon: GraduationCap, color: "text-violet-600", bg: "bg-violet-50", ring: "ring-violet-100", href: "/teachers" },
    { label: "Classes & Arms", desc: "Class structure and offerings", icon: BookOpen, color: "text-rose-500", bg: "bg-rose-50", ring: "ring-rose-100", href: "/classes" },
    { label: "Attendance", desc: "Mark and review attendance", icon: CalendarCheck, color: "text-emerald-600", bg: "bg-emerald-50", ring: "ring-emerald-100", href: "/attendance" },
    { label: "Results & Reports", desc: "Enter, approve, and compile results", icon: ClipboardCheck, color: "text-amber-500", bg: "bg-amber-50", ring: "ring-amber-100", href: "/results" },
    { label: "Report Cards", desc: "Generate and publish reports", icon: FileText, color: "text-cyan-600", bg: "bg-cyan-50", ring: "ring-cyan-100", href: "/reports" },
  ];

  return (
    <>
      {/* Overview Links */}
      <div>
        <motion.h2
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.3, delay: 0.1, ease }}
          className="mb-3 text-[13px] font-semibold uppercase tracking-wider text-muted-foreground/40"
        >
          Management
        </motion.h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {adminLinks.map((link, idx) => {
            const Icon = link.icon;
            return (
              <motion.div
                key={link.label}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.35, delay: 0.12 + idx * 0.04, ease }}
              >
                <Link
                  href={link.href}
                  className="group flex items-center gap-4 rounded-2xl border border-white/60 bg-white p-5 shadow-[0_1px_3px_rgba(0,0,0,0.04)] transition-all duration-200 hover:shadow-[0_4px_12px_rgba(0,0,0,0.06)] hover:-translate-y-0.5"
                >
                  <div className={cn("flex h-11 w-11 items-center justify-center rounded-xl ring-1", link.bg, link.ring)}>
                    <Icon className={cn("h-5 w-5", link.color)} strokeWidth={1.75} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-[13px] font-medium text-foreground/80">{link.label}</p>
                    <p className="text-[11px] text-muted-foreground/40">{link.desc}</p>
                  </div>
                  <ArrowUpRight className="h-4 w-4 shrink-0 text-muted-foreground/20 transition-colors duration-200 group-hover:text-primary/60" />
                </Link>
              </motion.div>
            );
          })}
        </div>
      </div>

      {/* Quick Stats */}
      <div>
        <motion.h2
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.3, delay: 0.35, ease }}
          className="mb-3 text-[13px] font-semibold uppercase tracking-wider text-muted-foreground/40"
        >
          Quick Access
        </motion.h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="School Settings" icon={Settings} color="text-muted-foreground/50" bg="bg-muted/30" ring="ring-border/30" href="/settings" delay={0.38} />
          <StatCard label="Billing & Fees" icon={TrendingUp} color="text-emerald-600" bg="bg-emerald-50" ring="ring-emerald-100" href="/billing" delay={0.4} />
          <StatCard label="Timetable" icon={Clock} color="text-blue-600" bg="bg-blue-50" ring="ring-blue-100" href="/timetable" delay={0.42} />
          <StatCard label="Approvals" icon={Shield} color="text-amber-500" bg="bg-amber-50" ring="ring-amber-100" href="/approvals" delay={0.44} />
        </div>
      </div>
    </>
  );
}

/* ─── Academic variant ──────────────────────────────────────────────────── */

function AcademicVariant() {
  const academicLinks = [
    { label: "Readiness", desc: "Check result entry progress", icon: BarChart3, color: "text-blue-600", bg: "bg-blue-50", ring: "ring-blue-100", href: "/readiness" },
    { label: "Approvals", desc: "Review teacher submissions", icon: Shield, color: "text-amber-500", bg: "bg-amber-50", ring: "ring-amber-100", href: "/approvals" },
    { label: "Compile Results", desc: "Finalize scores into reports", icon: ClipboardCheck, color: "text-violet-600", bg: "bg-violet-50", ring: "ring-violet-100", href: "/approvals" },
    { label: "Performance", desc: "View academic trends", icon: TrendingUp, color: "text-emerald-600", bg: "bg-emerald-50", ring: "ring-emerald-100", href: "/reports" },
    { label: "Attendance", desc: "Review school attendance", icon: CalendarCheck, color: "text-rose-500", bg: "bg-rose-50", ring: "ring-rose-100", href: "/attendance" },
    { label: "Report Cards", desc: "Generate and publish", icon: FileText, color: "text-cyan-600", bg: "bg-cyan-50", ring: "ring-cyan-100", href: "/reports" },
  ];

  return (
    <div>
      <motion.h2
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.3, delay: 0.1, ease }}
        className="mb-3 text-[13px] font-semibold uppercase tracking-wider text-muted-foreground/40"
      >
        Academics
      </motion.h2>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {academicLinks.map((link, idx) => {
          const Icon = link.icon;
          return (
            <motion.div
              key={link.label}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, delay: 0.12 + idx * 0.04, ease }}
            >
              <Link
                href={link.href}
                className="group flex items-center gap-4 rounded-2xl border border-white/60 bg-white p-5 shadow-[0_1px_3px_rgba(0,0,0,0.04)] transition-all duration-200 hover:shadow-[0_4px_12px_rgba(0,0,0,0.06)] hover:-translate-y-0.5"
              >
                <div className={cn("flex h-11 w-11 items-center justify-center rounded-xl ring-1", link.bg, link.ring)}>
                  <Icon className={cn("h-5 w-5", link.color)} strokeWidth={1.75} />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-[13px] font-medium text-foreground/80">{link.label}</p>
                  <p className="text-[11px] text-muted-foreground/40">{link.desc}</p>
                </div>
                <ArrowUpRight className="h-4 w-4 shrink-0 text-muted-foreground/20 transition-colors duration-200 group-hover:text-primary/60" />
              </Link>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}

/* ─── Main export ───────────────────────────────────────────────────────── */

export function ManagementDashboard({ variant }: { variant: "admin" | "academic" }) {
  return (
    <div className="space-y-8">
      <Greeting />
      {variant === "admin" ? <AdminVariant /> : <AcademicVariant />}
    </div>
  );
}
