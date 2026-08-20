"use client";

import { AlertTriangle, ArrowRight, Banknote, BellRing, Building2, Cpu, Sparkles, Users } from "lucide-react";
import Link from "next/link";

import { StatCard, Panel, PanelSkeleton, StatusBadge, fmtCurrency, fmtNum, titleCase } from "@/components/platform-utils";
import { Badge } from "@/components/ui/badge";
import { useSaOverview } from "@/hooks/use-superadmin";
import { useAuth } from "@/providers/auth-provider";

interface Kpis {
  total_schools?: number;
  active_schools?: number;
  suspended_schools?: number;
  trial_schools?: number;
  past_due_schools?: number;
  expired_schools?: number;
  students?: number;
  teachers?: number;
  parents?: number;
  mrr?: number;
  arr?: number;
  revenue_month?: number;
  revenue_today?: number;
  ai_requests_month?: number;
  ai_requests_today?: number;
  ai_credits_month?: number;
  ai_cost?: number;
  ai_revenue?: number;
  ai_margin?: number;
  active_users_today?: number;
  new_schools_month?: number;
  new_schools_week?: number;
  new_schools_today?: number;
  total_schools_delta_pct?: number | null;
  students_delta_pct?: number | null;
  mrr_delta_pct?: number | null;
}

function Delta({ pct }: { pct: number | null | undefined }) {
  if (pct == null) return null;
  const up = pct >= 0;
  return (
    <span className={up ? "text-success" : "text-destructive"}>
      {up ? "▲" : "▼"} {Math.abs(pct).toFixed(1)}%
    </span>
  );
}

export default function SuperAdminOverviewPage() {
  const { user } = useAuth();
  const { data, isLoading } = useSaOverview();
  const k = (data?.kpis ?? {}) as Kpis;

  return (
    <div className="space-y-6">
      {/* Hero */}
      <div className="relative overflow-hidden rounded-2xl border bg-gradient-to-br from-amber-500 via-orange-500 to-rose-500 p-6 text-white sm:p-8">
        <div className="pointer-events-none absolute -right-16 -top-16 h-56 w-56 rounded-full bg-white/10 blur-2xl" />
        <div className="pointer-events-none absolute -bottom-20 right-24 h-40 w-40 rounded-full bg-white/10 blur-xl" />
        <div className="relative space-y-3">
          <Badge className="gap-1 border-white/20 bg-white/10 text-white">
            <Sparkles className="h-3 w-3" /> Lumo Platform Command Center
          </Badge>
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Welcome back, {user?.full_name}</h1>
          <p className="max-w-2xl text-sm text-white/85">
            Every school, subscription and AI credit across Lumo — run the platform from one place.
          </p>
          <div className="flex flex-wrap gap-3 pt-1">
            <HeroStat label="Schools" value={fmtNum(k.total_schools)} />
            <HeroStat label="Active" value={fmtNum(k.active_schools)} />
            <HeroStat label="Students" value={fmtNum(k.students)} />
            <HeroStat label="MRR" value={fmtCurrency(k.mrr)} />
          </div>
        </div>
      </div>

      {/* Alerts */}
      {!isLoading && (data?.alerts?.length ?? 0) > 0 && (
        <div className="flex flex-wrap gap-2">
          {data!.alerts!.map((a) => (
            <Link
              key={a.kind}
              href={a.href ?? "#"}
              className="flex items-center gap-2 rounded-xl border px-3.5 py-2 text-[13px] font-medium shadow-card transition-colors hover:bg-accent"
            >
              <AlertTriangle
                className={
                  a.severity === "critical" ? "h-4 w-4 text-destructive" : a.severity === "warning" ? "h-4 w-4 text-warning" : "h-4 w-4 text-info"
                }
              />
              <span>{a.count} {a.label}</span>
              <ArrowRight className="h-3.5 w-3.5 text-muted-foreground" />
            </Link>
          ))}
        </div>
      )}

      {/* KPI grid */}
      {isLoading ? (
        <PanelSkeleton rows={2} />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            label="Schools"
            value={fmtNum(k.total_schools)}
            sub={
              <span className="flex items-center gap-2">
                <Delta pct={k.total_schools_delta_pct} /> · {fmtNum(k.new_schools_month)} new this month
              </span>
            }
            accent="text-primary"
          />
          <StatCard
            label="Students"
            value={fmtNum(k.students)}
            sub={
              <span className="flex items-center gap-2">
                <Delta pct={k.students_delta_pct} /> · {fmtNum(k.teachers)} teachers
              </span>
            }
            accent="text-primary"
          />
          <StatCard
            label="Monthly recurring revenue"
            value={fmtCurrency(k.mrr)}
            sub={
              <span className="flex items-center gap-2">
                <Delta pct={k.mrr_delta_pct} /> · {fmtCurrency(k.arr)} ARR
              </span>
            }
            accent="text-success"
          />
          <StatCard
            label="Active users today"
            value={fmtNum(k.active_users_today)}
            sub={`${fmtNum(k.ai_requests_today)} AI requests today`}
            accent="text-amber-600 dark:text-amber-400"
          />
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Alerts panel */}
        <Panel
          title="Priority alerts"
          subtitle="Derived from live platform state"
          action={
            <Link href="/super-admin/issues" className="text-xs font-medium text-primary hover:underline">
              All issues →
            </Link>
          }
          className="lg:col-span-1"
        >
          {isLoading ? (
            <PanelSkeleton rows={3} />
          ) : (data?.alerts?.length ?? 0) === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">All clear — no alerts right now.</p>
          ) : (
            <div className="space-y-2.5">
              {data!.alerts!.map((a) => (
                <div key={a.kind} className="flex items-start justify-between gap-3 rounded-xl border bg-muted/30 p-3">
                  <div className="min-w-0">
                    <p className="text-[13px] font-medium capitalize leading-snug">{a.label}</p>
                    <p className="text-xs text-muted-foreground">{titleCase(a.kind)}</p>
                  </div>
                  <StatusBadge status={a.severity} />
                </div>
              ))}
            </div>
          )}
        </Panel>

        {/* Platform health snapshot */}
        <Panel
          title="Health snapshot"
          subtitle="System status across services"
          action={
            <Link href="/super-admin/system" className="text-xs font-medium text-primary hover:underline">
              Details →
            </Link>
          }
        >
          {isLoading ? (
            <PanelSkeleton rows={3} />
          ) : (
            <div className="space-y-2.5">
              <div className="flex items-center justify-between rounded-xl border bg-muted/30 px-4 py-3">
                <span className="text-[13px] font-medium">Payments</span>
                <StatusBadge status={(k.past_due_schools ?? 0) > 0 ? "degraded" : "operational"} />
              </div>
              <div className="flex items-center justify-between rounded-xl border bg-muted/30 px-4 py-3">
                <span className="text-[13px] font-medium">Subscriptions</span>
                <StatusBadge status={(k.past_due_schools ?? 0) > 0 ? "degraded" : "operational"} />
              </div>
              <div className="flex items-center justify-between rounded-xl border bg-muted/30 px-4 py-3">
                <span className="text-[13px] font-medium">AI provider</span>
                <StatusBadge status={(k.ai_cost ?? 0) > 0 ? "operational" : "operational"} />
              </div>
            </div>
          )}
        </Panel>

        {/* Notifications */}
        <Panel
          title="Platform notifications"
          subtitle="Latest system messages"
          action={
            <Link href="/super-admin/audit" className="text-xs font-medium text-primary hover:underline">
              Audit log →
            </Link>
          }
        >
          {isLoading ? (
            <PanelSkeleton rows={3} />
          ) : (data?.notifications?.length ?? 0) === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">No notifications yet.</p>
          ) : (
            <div className="space-y-2">
              {data!.notifications!.slice(0, 5).map((n) => (
                <div key={n.id} className="flex items-start gap-2.5 rounded-xl border bg-muted/30 p-3">
                  <BellRing className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                  <div className="min-w-0">
                    <p className="text-[13px] font-medium leading-snug">{n.title}</p>
                    {n.body && <p className="truncate text-xs text-muted-foreground">{n.body}</p>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>

      {/* Quick links */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <QuickLink href="/super-admin/schools" icon={<Building2 className="h-4 w-4" />} label="Schools" sub={`${fmtNum(k.total_schools)} total · ${fmtNum(k.suspended_schools)} suspended`} />
        <QuickLink href="/super-admin/subscriptions" icon={<Banknote className="h-4 w-4" />} label="Subscriptions" sub={`${fmtNum(k.trial_schools)} trials · ${fmtNum(k.past_due_schools)} past due`} />
        <QuickLink href="/super-admin/ai" icon={<Cpu className="h-4 w-4" />} label="AI usage" sub={`${fmtNum(k.ai_requests_month)} requests this month`} />
        <QuickLink href="/super-admin/users" icon={<Users className="h-4 w-4" />} label="Users" sub={`${fmtNum(k.teachers)} teachers · ${fmtNum(k.parents)} parents`} />
      </div>
    </div>
  );
}

function HeroStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-white/20 bg-white/10 px-4 py-2 backdrop-blur">
      <p className="text-lg font-semibold leading-none">{value}</p>
      <p className="mt-0.5 text-[11px] uppercase tracking-wide text-white/70">{label}</p>
    </div>
  );
}

function QuickLink({ href, icon, label, sub }: { href: string; icon: React.ReactNode; label: string; sub: string }) {
  return (
    <Link
      href={href}
      className="group flex items-center gap-3 rounded-xl border bg-card p-4 shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-md"
    >
      <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">{icon}</span>
      <span className="min-w-0">
        <span className="block text-[13px] font-semibold">{label}</span>
        <span className="block truncate text-xs text-muted-foreground">{sub}</span>
      </span>
      <ArrowRight className="ml-auto h-4 w-4 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
    </Link>
  );
}