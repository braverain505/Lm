"use client";

import { ArrowRight, Banknote, CheckCircle2, FileText, TrendingUp, Wallet } from "lucide-react";
import Link from "next/link";
import { useMemo } from "react";

import { ActivityPanel, KpiRow } from "@/components/dashboard/widgets";
import { WidgetCard, relativeTime } from "@/components/dashboard/shared";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/providers/auth-provider";
import { useSessionTerm } from "@/providers/session-context";
import { useDashboardSummary, useInvoices } from "@/hooks/use-api";

const ngn = new Intl.NumberFormat("en-NG", { maximumFractionDigits: 0 });

export function AccountantDashboard() {
  const { user } = useAuth();
  const { term } = useSessionTerm();
  const { data, isLoading, isError, refetch } = useDashboardSummary(term?.id ?? undefined);
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

  return (
    <div className="space-y-5">
      <div className="rounded-2xl border border-primary/[0.08] bg-gradient-to-br from-primary/[0.04] via-primary/[0.02] to-transparent px-6 py-5">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 className="text-[20px] font-bold tracking-tight text-foreground sm:text-[22px]">
              {new Date().getHours() < 12 ? "Good morning" : new Date().getHours() < 17 ? "Good afternoon" : "Good evening"},{" "}
              {user?.full_name?.split(" ")[0] ?? "there"}
            </h2>
            <p className="mt-1 text-[13px] text-muted-foreground">Here&apos;s the financial picture for your school.</p>
          </div>
        </div>
      </div>

      <KpiRow data={data} loading={isLoading} accountant />

      {/* Financial summary */}
      <div className="grid gap-4 lg:grid-cols-3">
        <WidgetCard
          title="Fee collections"
          icon={<Wallet className="h-4 w-4 text-primary" />}
          subtitle="Outstanding balances overview"
          loading={isLoading}
          error={isError}
          onRetry={refetch}
        >
          <div className="rounded-xl border border-border/40 bg-gradient-to-b from-muted/40 to-transparent p-6 text-center">
            <p className="text-[12px] text-muted-foreground/70">Total outstanding</p>
            <div className="mt-1 text-3xl font-bold tracking-tight">
              {isLoading ? <Skeleton className="mx-auto h-8 w-32" /> : `${currency} ${ngn.format(data?.kpis?.outstanding_fees ?? 0)}`}
            </div>
            <p className="mt-2 text-[11px] text-muted-foreground/60">{feeCount} students carry a balance</p>
            <Link href="/billing" className="mt-4 inline-flex items-center gap-1 text-[13px] font-semibold text-primary hover:underline">
              Open billing <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </WidgetCard>

        <WidgetCard
          title="Today's collections"
          icon={<TrendingUp className="h-4 w-4 text-primary" />}
          subtitle="Payments recorded today"
          loading={invoicesLoading}
          error={isError}
          onRetry={refetch}
        >
          <div className="space-y-4">
            <div className="flex items-end justify-between">
              <div className="text-3xl font-bold tracking-tight">{isLoading ? <Skeleton className="h-8 w-28" /> : `${currency} ${ngn.format(todayAmount)}`}</div>
              <Badge variant="success">{todayCount} payment{todayCount === 1 ? "" : "s"}</Badge>
            </div>
            <div className="flex items-center gap-2 rounded-xl border border-success/15 bg-success/[0.03] px-4 py-3 text-[12px]">
              <CheckCircle2 className="h-4 w-4 text-success" />
              <span className="text-muted-foreground/70">Collections are recorded against invoices.</span>
            </div>
          </div>
        </WidgetCard>

        <WidgetCard
          title="Financial reports"
          icon={<FileText className="h-4 w-4 text-primary" />}
          subtitle="Generate & export"
        >
          <ul className="space-y-2">
            {[
              { href: "/billing", label: "Fee statement", desc: "Per-student balances" },
              { href: "/payroll", label: "Payroll runs", desc: "Gross, tax & net" },
              { href: "/reports", label: "Report cards", desc: "Published results" },
            ].map((r) => (
              <li key={r.href}>
                <Link href={r.href} className="group flex items-center gap-3 rounded-xl border border-border/40 px-3.5 py-3 transition-all duration-150 hover:border-primary/20 hover:bg-accent/50">
                  <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-primary/10 text-primary">
                    <Banknote className="h-4 w-4" />
                  </span>
                  <div className="min-w-0">
                    <p className="text-[13px] font-semibold">{r.label}</p>
                    <p className="truncate text-[11px] text-muted-foreground/70">{r.desc}</p>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        </WidgetCard>
      </div>

      {/* Recent payments + activity */}
      <div className="grid gap-4 xl:grid-cols-3">
        <WidgetCard
          title="Recent payments"
          icon={<Wallet className="h-4 w-4 text-primary" />}
          subtitle="Latest recorded collections"
          loading={invoicesLoading}
          error={isError}
          onRetry={refetch}
          empty={!invoicesLoading && recent.length === 0}
          emptyHint="Recorded payments will appear here."
          className="xl:col-span-1"
          bodyClassName="pt-3"
        >
          <ul className="space-y-0.5">
            {recent.map((i) => (
              <li key={i.id}>
                <div className="flex items-center gap-3 rounded-lg px-2 py-2">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-success/10 text-success">
                    <Banknote className="h-4 w-4" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[13px] font-medium">{i.payment_method ?? "Payment"} · {i.reference_number}</p>
                    <p className="truncate text-[11px] text-muted-foreground/60">{i.paid_date ? relativeTime(i.paid_date) : ""}</p>
                  </div>
                  <span className="shrink-0 text-[13px] font-semibold text-success">
                    {currency} {ngn.format(i.total_amount)}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        </WidgetCard>

        <ActivityPanel items={data?.activity} loading={isLoading} error={isError} onRetry={refetch} className="xl:col-span-2" />
      </div>
    </div>
  );
}
