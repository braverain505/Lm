"use client";

import { motion } from "framer-motion";
import {
  ArrowRight,
  Banknote,
  FileText,
  Wallet,
  TrendingUp,
  Clock,
  Users,
  Receipt,
  ArrowUpRight,
} from "lucide-react";
import Link from "next/link";
import { useMemo } from "react";

import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/providers/auth-provider";
import { useSessionTerm } from "@/providers/session-context";
import { useDashboardSummary, useInvoices } from "@/hooks/use-api";
import { cn } from "@/lib/utils";

const ngn = new Intl.NumberFormat("en-NG", { maximumFractionDigits: 0 });
const ease = [0.25, 0.46, 0.45, 0.94] as const;

export function AccountantDashboard() {
  const { user } = useAuth();
  const { term } = useSessionTerm();
  const { data, isLoading } = useDashboardSummary(term?.id ?? undefined);
  const { data: invoices = [], isLoading: invoicesLoading } = useInvoices(null);

  const { todayCount, todayAmount, thisWeekCount, thisWeekAmount, recent } = useMemo(() => {
    const paid = invoices.filter((i) => i.paid_date);
    const now = new Date();
    const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
    const today = now.toISOString().slice(0, 10);
    const todays = paid.filter((i) => i.paid_date?.slice(0, 10) === today);
    const thisWeek = paid.filter((i) => i.paid_date && i.paid_date >= weekAgo.toISOString().slice(0, 10));
    const recent = [...paid].sort((a, b) => (b.paid_date ?? "").localeCompare(a.paid_date ?? "")).slice(0, 5);
    return {
      todayCount: todays.length,
      todayAmount: todays.reduce((s, i) => s + i.total_amount, 0),
      thisWeekCount: thisWeek.length,
      thisWeekAmount: thisWeek.reduce((s, i) => s + i.total_amount, 0),
      recent,
    };
  }, [invoices]);

  const feeCount = data?.tasks?.find((t) => t.kind === "finance")?.count ?? 0;
  const currency = data?.kpis?.fee_currency ?? "NGN";
  const outstandingFees = data?.kpis?.outstanding_fees ?? 0;

  const hour = new Date().getHours();
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
          Here&apos;s the financial picture for your school.
        </p>
        {term && (
          <p className="mt-1 inline-flex items-center gap-1.5 rounded-full bg-primary/5 px-3 py-1 text-[12px] font-medium text-primary/70">
            <span className="h-1.5 w-1.5 rounded-full bg-primary/60" />
            {term.name}
          </p>
        )}
      </motion.div>

      {/* ── Financial KPIs ───────────────────────────────────────── */}
      <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-4">
        {/* Outstanding Fees */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.06, ease }}
          className="rounded-2xl border border-white/60 bg-white p-5 shadow-[0_1px_3px_rgba(0,0,0,0.04)]"
        >
          <div className="flex items-start justify-between">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/50">Outstanding</p>
              <p className="mt-2 text-[22px] font-bold tracking-tight text-foreground">
                {isLoading ? <Skeleton className="inline-block h-6 w-24 rounded-md" /> : `${currency} ${ngn.format(outstandingFees)}`}
              </p>
              <p className="mt-1 text-[10px] text-muted-foreground/40">{feeCount} students with balances</p>
            </div>
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-rose-50 ring-1 ring-rose-100">
              <Wallet className="h-5 w-5 text-rose-500" strokeWidth={1.75} />
            </div>
          </div>
        </motion.div>

        {/* Today's Collections */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.1, ease }}
          className="rounded-2xl border border-white/60 bg-white p-5 shadow-[0_1px_3px_rgba(0,0,0,0.04)]"
        >
          <div className="flex items-start justify-between">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/50">Today&apos;s Collections</p>
              <p className="mt-2 text-[22px] font-bold tracking-tight text-foreground">
                {isLoading ? <Skeleton className="inline-block h-6 w-24 rounded-md" /> : `${currency} ${ngn.format(todayAmount)}`}
              </p>
              <div className="mt-1">
                <Badge variant="success" className="text-[10px]">{todayCount} payment{todayCount === 1 ? "" : "s"}</Badge>
              </div>
            </div>
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-50 ring-1 ring-emerald-100">
              <Banknote className="h-5 w-5 text-emerald-600" strokeWidth={1.75} />
            </div>
          </div>
        </motion.div>

        {/* This Week */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.14, ease }}
          className="rounded-2xl border border-white/60 bg-white p-5 shadow-[0_1px_3px_rgba(0,0,0,0.04)]"
        >
          <div className="flex items-start justify-between">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/50">This Week</p>
              <p className="mt-2 text-[22px] font-bold tracking-tight text-foreground">
                {isLoading ? <Skeleton className="inline-block h-6 w-24 rounded-md" /> : `${currency} ${ngn.format(thisWeekAmount)}`}
              </p>
              <p className="mt-1 text-[10px] text-muted-foreground/40">{thisWeekCount} payments</p>
            </div>
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50 ring-1 ring-blue-100">
              <TrendingUp className="h-5 w-5 text-blue-600" strokeWidth={1.75} />
            </div>
          </div>
        </motion.div>

        {/* Students with Balance */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.18, ease }}
          className="rounded-2xl border border-white/60 bg-white p-5 shadow-[0_1px_3px_rgba(0,0,0,0.04)]"
        >
          <div className="flex items-start justify-between">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/50">With Balance</p>
              <p className="mt-2 text-[22px] font-bold tracking-tight text-foreground">
                {isLoading ? <Skeleton className="inline-block h-6 w-12 rounded-md" /> : feeCount}
              </p>
              <p className="mt-1 text-[10px] text-muted-foreground/40">students owing</p>
            </div>
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-50 ring-1 ring-amber-100">
              <Users className="h-5 w-5 text-amber-500" strokeWidth={1.75} />
            </div>
          </div>
        </motion.div>
      </div>

      {/* ── Bottom Grid: Recent Payments + Quick Links ────────────── */}
      <div className="grid gap-5 lg:grid-cols-5">
        {/* Recent Payments */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.22, ease }}
          className="lg:col-span-3 rounded-2xl border border-white/60 bg-white shadow-[0_1px_3px_rgba(0,0,0,0.04)] overflow-hidden"
        >
          <div className="flex items-center justify-between border-b border-border/20 px-5 py-4">
            <div>
              <h3 className="text-[14px] font-semibold tracking-tight text-foreground">Recent Payments</h3>
              <p className="mt-0.5 text-[12px] text-muted-foreground/50">Latest recorded collections</p>
            </div>
            <Link href="/billing" className="text-[11px] font-semibold text-primary/70 hover:text-primary transition-colors">
              View all
            </Link>
          </div>
          {invoicesLoading ? (
            <div className="p-5 space-y-3">
              <Skeleton className="h-12 w-full rounded-lg" />
              <Skeleton className="h-12 w-full rounded-lg" />
              <Skeleton className="h-12 w-full rounded-lg" />
            </div>
          ) : recent.length === 0 ? (
            <div className="flex flex-col items-center justify-center px-5 py-10 text-center">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-muted/30">
                <Receipt className="h-5 w-5 text-muted-foreground/25" />
              </div>
              <p className="mt-3 text-[12px] font-medium text-foreground/50">No payments recorded yet</p>
            </div>
          ) : (
            <div className="divide-y divide-border/15">
              {recent.map((i) => (
                <div key={i.id} className="flex items-center gap-3 px-5 py-3.5 transition-colors duration-150 hover:bg-muted/15">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-emerald-50">
                    <Banknote className="h-4 w-4 text-emerald-600" strokeWidth={1.75} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[12px] font-medium text-foreground/80">{i.payment_method ?? "Payment"}</p>
                    <p className="text-[10px] text-muted-foreground/40">
                      {i.paid_date ? new Date(i.paid_date).toLocaleDateString(undefined, { day: "numeric", month: "short" }) : ""}
                    </p>
                  </div>
                  <span className="shrink-0 text-[12px] font-semibold text-emerald-600">
                    {currency} {ngn.format(i.total_amount)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </motion.div>

        {/* Quick Links */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.26, ease }}
          className="lg:col-span-2 rounded-2xl border border-white/60 bg-white p-6 shadow-[0_1px_3px_rgba(0,0,0,0.04)]"
        >
          <div className="mb-4">
            <h3 className="text-[14px] font-semibold tracking-tight text-foreground">Quick Links</h3>
            <p className="mt-0.5 text-[12px] text-muted-foreground/50">Financial reports & tools</p>
          </div>
          <div className="space-y-2">
            {[
              { href: "/billing", label: "Fee Statement", desc: "Per-student balances", icon: FileText, color: "text-blue-600", bg: "bg-blue-50" },
              { href: "/payroll", label: "Payroll Runs", desc: "Gross, tax & net", icon: TrendingUp, color: "text-violet-600", bg: "bg-violet-50" },
              { href: "/reports", label: "Report Cards", desc: "Published results", icon: FileText, color: "text-emerald-600", bg: "bg-emerald-50" },
            ].map((r) => {
              const Icon = r.icon;
              return (
                <Link
                  key={r.href}
                  href={r.href}
                  className="group flex items-center gap-3 rounded-xl px-3 py-3 transition-colors duration-150 hover:bg-muted/20"
                >
                  <div className={cn("flex h-9 w-9 items-center justify-center rounded-lg", r.bg)}>
                    <Icon className={cn("h-4 w-4", r.color)} strokeWidth={1.75} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-[12px] font-medium text-foreground/80">{r.label}</p>
                    <p className="text-[10px] text-muted-foreground/40">{r.desc}</p>
                  </div>
                  <ArrowUpRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground/20 transition-colors duration-200 group-hover:text-primary/60" />
                </Link>
              );
            })}
          </div>
        </motion.div>
      </div>
    </div>
  );
}
