"use client";

import { motion } from "framer-motion";
import {
  AlertTriangle,
  ArrowRight,
  Banknote,
  CheckCircle2,
  Clock,
  Landmark,
  Loader2,
  PieChart,
  Receipt,
  TrendingDown,
  TrendingUp,
  UserPlus,
  Users,
  Wallet,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useAccountingSummary,
  useAccountants,
  useCreateAccountant,
} from "@/hooks/use-api";
import { useAuth } from "@/providers/auth-provider";
import { useSessionTerm } from "@/providers/session-context";
import { formatMoney } from "@/lib/utils";

const ease = [0.25, 0.46, 0.45, 0.94] as const;

function Kpi({
  label,
  value,
  hint,
  tone = "default",
  icon: Icon,
  delay,
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "default" | "good" | "bad";
  icon: React.ComponentType<{ className?: string }>;
  delay: number;
}) {
  const toneClass =
    tone === "good" ? "text-success" : tone === "bad" ? "text-destructive" : "text-foreground";
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, delay, ease }}
    >
      <Card className="premium-card h-full">
        <CardContent className="p-5">
          <div className="flex items-start justify-between">
            <p className="text-[10.5px] font-semibold uppercase tracking-[0.1em] text-muted-foreground/60">
              {label}
            </p>
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <Icon className="h-4 w-4" />
            </div>
          </div>
          <p className={`mt-3 text-2xl font-bold tabular-nums tracking-tight ${toneClass}`}>
            {value}
          </p>
          {hint && <p className="mt-1 text-[11.5px] text-muted-foreground/70">{hint}</p>}
        </CardContent>
      </Card>
    </motion.div>
  );
}

export default function AccountingOverviewPage() {
  const { activeSchool, user } = useAuth();
  const { term } = useSessionTerm();
  const { data: summary, isLoading } = useAccountingSummary(term?.id);
  const { data: accountants = [], isLoading: accountantsLoading } = useAccountants();
  const createAccountant = useCreateAccountant();

  const canProvision =
    (activeSchool?.permissions?.includes("users.manage") ?? false) || (user?.is_superadmin ?? false);

  const [form, setForm] = useState({ full_name: "", email: "", password: "" });
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<string | null>(null);

  const currency = summary?.currency ?? "NGN";

  function submit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setCreated(null);
    createAccountant.mutate(form, {
      onSuccess: (accountant) => {
        setCreated(`Login created for ${accountant.full_name} (${accountant.email}).`);
        setForm({ full_name: "", email: "", password: "" });
      },
      onError: (err) =>
        setError(err instanceof Error ? err.message : "Could not create the login."),
    });
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-[22px] font-bold tracking-tight text-foreground">
            Accountant&apos;s Desk
          </h1>
          <p className="mt-1 text-[13px] text-muted-foreground">
            The ledger for {activeSchool?.school_name}
            {term ? ` · ${term.name}` : ""}. Only this school&apos;s Accountant sees this.
          </p>
        </div>
        <div className="flex gap-2">
          <Button asChild variant="outline" size="sm">
            <Link href="/accounting/expenses" className="gap-1.5">
              <Receipt className="h-4 w-4" /> Record expense
            </Link>
          </Button>
          <Button asChild size="sm">
            <Link href="/accounting/cashbook" className="gap-1.5">
              <Banknote className="h-4 w-4" /> Open cashbook
            </Link>
          </Button>
        </div>
      </div>

      {/* Headline numbers */}
      {isLoading || !summary ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-[112px] rounded-2xl" />
          ))}
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Kpi
            label="Outstanding fees"
            value={formatMoney(summary.outstanding_fees, currency)}
            hint="Owed by students, not yet collected"
            tone={summary.outstanding_fees > 0 ? "bad" : "good"}
            icon={Wallet}
            delay={0.02}
          />
          <Kpi
            label="Collected this term"
            value={formatMoney(summary.collected_this_term, currency)}
            hint="Fees received into the books"
            tone="good"
            icon={TrendingUp}
            delay={0.05}
          />
          <Kpi
            label="Expenses this term"
            value={formatMoney(summary.expenses_this_term, currency)}
            hint="Paid out of the school's accounts"
            icon={TrendingDown}
            delay={0.08}
          />
          <Kpi
            label={summary.surplus_this_term >= 0 ? "Surplus this term" : "Deficit this term"}
            value={formatMoney(Math.abs(summary.surplus_this_term), currency)}
            hint="Collected minus expenses paid"
            tone={summary.surplus_this_term >= 0 ? "good" : "bad"}
            icon={PieChart}
            delay={0.11}
          />
          <Kpi
            label="Cash & bank position"
            value={formatMoney(summary.cash_position, currency)}
            hint="Across every cash and bank account"
            icon={Landmark}
            delay={0.14}
          />
          <Kpi
            label="Debtors over 90 days"
            value={formatMoney(summary.debtors_over_90_days, currency)}
            hint="Long-overdue fees worth chasing"
            tone={summary.debtors_over_90_days > 0 ? "bad" : "good"}
            icon={AlertTriangle}
            delay={0.17}
          />
        </div>
      )}

      {/* Work queue */}
      <Card className="premium-card">
        <CardHeader>
          <CardTitle>Needs the accountant</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[
            {
              label: "Expenses awaiting approval",
              value: summary?.pending_expense_approvals ?? 0,
              href: "/accounting/expenses",
              icon: Clock,
            },
            {
              label: "Refunds to action",
              value: summary?.pending_refunds ?? 0,
              href: "/accounting/concessions",
              icon: Banknote,
            },
            {
              label: "Open credit notes",
              value: summary?.open_credit_notes ?? 0,
              href: "/accounting/concessions",
              icon: Receipt,
            },
            {
              label: "Unreconciled entries",
              value: summary?.unreconciled_cashbook_entries ?? 0,
              href: "/accounting/cashbook",
              icon: CheckCircle2,
            },
          ].map((item) => (
            <Link
              key={item.label}
              href={item.href}
              className="group flex items-center justify-between rounded-xl border border-border/50 bg-muted/20 px-4 py-3 transition-colors hover:border-primary/30 hover:bg-accent/40"
            >
              <div className="min-w-0">
                <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground/70">
                  {item.label}
                </p>
                <p className="mt-0.5 text-xl font-bold tabular-nums">
                  {isLoading ? "…" : item.value}
                </p>
              </div>
              <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground/40 transition-transform group-hover:translate-x-0.5" />
            </Link>
          ))}
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Quick links */}
        <Card className="premium-card">
          <CardHeader>
            <CardTitle>Where to go</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {[
              {
                href: "/accounting/expenses",
                title: "Expenses & petty cash",
                body: "Record what the school spends and clear approvals.",
              },
              {
                href: "/accounting/cashbook",
                title: "Cashbook & bank reconciliation",
                body: "Every movement in and out, matched to the bank statement.",
              },
              {
                href: "/accounting/debtors",
                title: "Debtors & aging",
                body: "Who owes what, how overdue, and a reminder to send.",
              },
              {
                href: "/accounting/concessions",
                title: "Discounts, credit notes & refunds",
                body: "Scholarships, waivers, and money paid back out.",
              },
              {
                href: "/accounting/reports",
                title: "Financial reports",
                body: "Income & expenditure, collection and cash position.",
              },
            ].map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="flex items-start gap-3 rounded-xl px-3 py-2.5 transition-colors hover:bg-accent/40"
              >
                <div className="mt-0.5 min-w-0 flex-1">
                  <p className="text-[13px] font-semibold">{item.title}</p>
                  <p className="text-[12px] text-muted-foreground">{item.body}</p>
                </div>
                <ArrowRight className="mt-1 h-4 w-4 shrink-0 text-muted-foreground/40" />
              </Link>
            ))}
          </CardContent>
        </Card>

        {/* Who can keep the books */}
        <Card className="premium-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Users className="h-4 w-4 text-primary" /> Who holds the Accountant role
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {accountantsLoading ? (
              <Skeleton className="h-16 w-full" />
            ) : accountants.length === 0 ? (
              <p className="text-[13px] text-muted-foreground">
                Nobody holds the Accountant role in this school yet.
              </p>
            ) : (
              <ul className="divide-y divide-border/40">
                {accountants.map((a) => (
                  <li key={a.user_id} className="flex items-center justify-between py-2.5">
                    <div className="min-w-0">
                      <p className="truncate text-[13px] font-medium">{a.full_name}</p>
                      <p className="truncate text-[11.5px] text-muted-foreground">{a.email}</p>
                    </div>
                    <span className="shrink-0 rounded-full bg-primary/10 px-2 py-0.5 text-[10.5px] font-semibold text-primary">
                      {a.role_name}
                    </span>
                  </li>
                ))}
              </ul>
            )}

            <p className="rounded-lg border border-border/50 bg-muted/25 p-3 text-[12px] text-muted-foreground">
              Each accountant signs in with their <strong>own email and password</strong> and can
              only act on this school. School admins give someone the Accountant role from{" "}
              <Link href="/teachers" className="font-medium text-primary hover:underline">
                Teachers &amp; Staff → Account
              </Link>
              .
            </p>

            {canProvision && (
              <form onSubmit={submit} className="space-y-3 rounded-xl border border-border/50 p-4">
                <div className="flex items-center gap-2">
                  <UserPlus className="h-4 w-4 text-primary" />
                  <p className="text-[13px] font-semibold">Create an accountant login</p>
                </div>
                <div className="grid gap-3 sm:grid-cols-3">
                  <div className="space-y-1.5">
                    <Label className="text-[11px]">Full name</Label>
                    <Input
                      value={form.full_name}
                      onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                      placeholder="Ada Bursar"
                      required
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-[11px]">Email</Label>
                    <Input
                      type="email"
                      value={form.email}
                      onChange={(e) => setForm({ ...form, email: e.target.value })}
                      placeholder="accountant@school.edu"
                      required
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-[11px]">Password</Label>
                    <Input
                      type="password"
                      value={form.password}
                      onChange={(e) => setForm({ ...form, password: e.target.value })}
                      placeholder="Min. 8 characters"
                      minLength={8}
                      required
                    />
                  </div>
                </div>
                {error && <p className="text-[11.5px] text-destructive">{error}</p>}
                {created && <p className="text-[11.5px] text-success">{created}</p>}
                <Button type="submit" size="sm" disabled={createAccountant.isPending}>
                  {createAccountant.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                  Create login
                </Button>
              </form>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
