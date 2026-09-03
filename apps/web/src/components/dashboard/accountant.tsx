"use client";

import { ArrowRight, FileText } from "lucide-react";
import { motion } from "framer-motion";
import Link from "next/link";
import { useMemo } from "react";


import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/providers/auth-provider";
import { useSessionTerm } from "@/providers/session-context";
import { useDashboardSummary, useInvoices } from "@/hooks/use-api";

const ngn = new Intl.NumberFormat("en-NG", { maximumFractionDigits: 0 });
const ease = [0.25, 0.46, 0.45, 0.94] as const;

export function AccountantDashboard() {
  const { user } = useAuth();
  const { term } = useSessionTerm();
  const { data, isLoading } = useDashboardSummary(term?.id ?? undefined);
  const { data: invoices = [], isLoading: invoicesLoading } = useInvoices(null);

  const { todayCount, todayAmount, recent } = useMemo(() => {
    const paid = invoices.filter((i) => i.paid_date);
    const today = new Date().toISOString().slice(0, 10);
    const todays = paid.filter((i) => i.paid_date?.slice(0, 10) === today);
    const recent = [...paid].sort((a, b) => (b.paid_date ?? "").localeCompare(a.paid_date ?? "")).slice(0, 6);
    return {
      todayCount: todays.length,
      todayAmount: todays.reduce((s, i) => s + i.total_amount, 0),
      recent,
    };
  }, [invoices]);

  const feeCount = data?.tasks?.find((t) => t.kind === "finance")?.count ?? 0;
  const currency = data?.kpis?.fee_currency ?? "NGN";

  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";

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
          Here&apos;s the financial picture for your school.
        </p>
      </motion.div>

      {/* Financial summary — 2 column */}
      <div className="grid gap-6 md:grid-cols-1 lg:grid-cols-2">
        {/* Outstanding fees */}
        <motion.div
          className="rounded-xl border border-border/40 bg-card px-5 py-5 shadow-xs transition-[border-color,box-shadow] duration-200 hover:border-border/60 hover:shadow-card"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.06, ease }}
        >
          <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground/50">Outstanding fees</p>
          <div className="mt-2.5 text-[28px] font-bold tracking-tight text-foreground">
            {isLoading ? <Skeleton className="inline-block h-8 w-32 rounded-md" /> : `${currency} ${ngn.format(data?.kpis?.outstanding_fees ?? 0)}`}
          </div>
          <p className="mt-1.5 text-[12px] text-muted-foreground/45">{feeCount} students carry a balance</p>
          <Link href="/billing" className="mt-3 inline-flex items-center gap-1.5 text-[12px] font-semibold text-primary transition-colors duration-200 hover:text-primary-hover">
            Open billing <ArrowRight className="h-3.5 w-3.5 transition-transform duration-200 group-hover:translate-x-0.5" />
          </Link>
        </motion.div>

        {/* Today's collections */}
        <motion.div
          className="rounded-xl border border-border/40 bg-card px-5 py-5 shadow-xs transition-[border-color,box-shadow] duration-200 hover:border-border/60 hover:shadow-card"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.1, ease }}
        >
          <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground/50">Today&apos;s collections</p>
          <div className="mt-2.5 text-[28px] font-bold tracking-tight text-foreground">
            {isLoading ? <Skeleton className="inline-block h-8 w-28 rounded-md" /> : `${currency} ${ngn.format(todayAmount)}`}
          </div>
          <div className="mt-2.5 flex items-center gap-2">
            <Badge variant="success">{todayCount} payment{todayCount === 1 ? "" : "s"}</Badge>
          </div>
        </motion.div>
      </div>

      {/* Quick reports */}
      <div>
        <h3 className="mb-3 text-[14px] font-semibold tracking-tight text-foreground/90">Financial reports</h3>
        <div className="grid gap-3 sm:grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
          {[
            { href: "/billing", label: "Fee statement", desc: "Per-student balances" },
            { href: "/payroll", label: "Payroll runs", desc: "Gross, tax & net" },
            { href: "/reports", label: "Report cards", desc: "Published results" },
          ].map((r) => (
            <Link
              key={r.href}
              href={r.href}
              className="group flex items-center gap-3 rounded-xl border border-border/40 bg-card px-4 py-3.5 shadow-xs transition-all duration-200 hover:border-border/60 hover:shadow-card hover:-translate-y-[1px]"
            >
              <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-muted/40 text-muted-foreground/40 transition-colors duration-200 group-hover:bg-primary/10 group-hover:text-primary/70">
                <FileText className="h-4 w-4" />
              </span>
              <div className="min-w-0">
                <p className="text-[13px] font-medium text-foreground">{r.label}</p>
                <p className="truncate text-[11px] text-muted-foreground/45">{r.desc}</p>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
