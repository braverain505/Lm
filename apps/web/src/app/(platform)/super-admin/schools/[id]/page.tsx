"use client";

import { ArrowLeft, Eye, KeyRound, Mail, MapPin, Pencil, Phone, RefreshCw, ShieldAlert, Sparkles, UserX } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import { EmptyState, Panel, PanelSkeleton, ProgressBar, StatusBadge, fmtCurrency, fmtDate, fmtDateTime, fmtNum, titleCase } from "@/components/platform-utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useSetSchoolAi, useSetSchoolSuspended } from "@/hooks/use-api";
import {
  useImpersonateEnter,
  useSaResetAdmin,
  useSaSchool,
  useSaUpdateSubscription,
} from "@/hooks/use-superadmin";
import { useAuth } from "@/providers/auth-provider";
import { api } from "@schoolos/shared";
import { useQueryClient } from "@tanstack/react-query";

export default function SchoolDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const schoolId = params.id;
  const { data, isLoading } = useSaSchool(schoolId);
  const { refreshMe } = useAuth();
  const queryClient = useQueryClient();

  const toggleAi = useSetSchoolAi();
  const toggleSuspended = useSetSchoolSuspended();
  const resetAdmin = useSaResetAdmin();
  const impersonateStart = useImpersonateEnter();
  const updateSub = useSaUpdateSubscription(schoolId);

  const [plan, setPlan] = useState<string>("");
  const [status, setStatus] = useState<string>("");
  const [aiCredits, setAiCredits] = useState<string>("");
  const [resetResult, setResetResult] = useState<{ email: string; temp_password: string } | null>(null);
  const [impersonating, setImpersonating] = useState(false);

  if (isLoading || !data) {
    return (
      <div className="space-y-4">
        <Link href="/super-admin/schools" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" /> Schools
        </Link>
        <PanelSkeleton rows={8} />
      </div>
    );
  }

  const p = data.profile;
  const sub = data.subscription as Record<string, unknown>;
  const usage = data.usage as Record<string, unknown>;
  const admins = (data.members?.school_admins ?? []) as Array<{
    user_id: string; full_name: string; email: string; phone: string | null; role_code: string; status: string;
  }>;
  const billingEvents = data.billing_events ?? [];
  const aiPct = (sub.ai_allowance_total as number) > 0 ? ((sub.ai_allowance_used as number) / (sub.ai_allowance_total as number)) * 100 : 0;

  const profileActions = (data: unknown) => queryClient.invalidateQueries({ queryKey: ["sa", "school", schoolId] });

  async function handleImpersonate() {
    setImpersonating(true);
    try {
      const session = await api.superAdminImpersonate(schoolId);
      await impersonateStart.mutateAsync(session.token);
      await refreshMe();
      try {
        localStorage.setItem("schoolos.impersonating", "1");
      } catch {
        /* ignore */
      }
      router.push("/dashboard");
    } finally {
      setImpersonating(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <Link href="/super-admin/schools" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" /> Schools
        </Link>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            disabled={toggleAi.isPending}
            onClick={() =>
              toggleAi.mutate({ schoolId, enabled: !p.ai_enabled }, { onSuccess: () => profileActions(data) })
            }
          >
            <Sparkles className="h-3.5 w-3.5" />
            {p.ai_enabled ? "Disable AI" : "Enable AI"}
          </Button>
          <Button
            size="sm"
            variant={p.suspended ? "default" : "outline"}
            disabled={toggleSuspended.isPending}
            onClick={() =>
              toggleSuspended.mutate({ schoolId, suspended: !p.suspended }, { onSuccess: () => profileActions(data) })
            }
          >
            <UserX className="h-3.5 w-3.5" />
            {p.suspended ? "Re-enable school" : "Disable school"}
          </Button>
          <Button size="sm" onClick={handleImpersonate} disabled={impersonating || p.suspended}>
            <Eye className="h-3.5 w-3.5" />
            {impersonating ? "Entering…" : "View as admin"}
          </Button>
        </div>
      </div>

      {/* Profile header */}
      <div className="relative overflow-hidden rounded-2xl border bg-gradient-to-br from-primary via-primary/80 to-primary/40 p-6 text-primary-foreground">
        <div className="pointer-events-none absolute -right-16 -top-16 h-56 w-56 rounded-full bg-white/10 blur-2xl" />
        <div className="relative space-y-3">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-white/15 text-2xl font-bold backdrop-blur">
              {p.name.charAt(0)}
            </div>
            <div className="min-w-0">
              <h1 className="truncate text-xl font-semibold tracking-tight sm:text-2xl">{p.name}</h1>
              <p className="text-sm text-primary-foreground/80">
                {p.slug} · {titleCase(p.school_type)} · registered {fmtDate(p.registration_date)}
              </p>
            </div>
            <div className="ml-auto flex flex-wrap gap-2">
              <Badge className="border-white/20 bg-white/10 text-primary-foreground">
                {titleCase(String(sub.plan_name ?? "Trial"))} plan
              </Badge>
              <Badge className="border-white/20 bg-white/10 text-primary-foreground">
                {titleCase(String(sub.status ?? "pending"))}
              </Badge>
              {p.ai_enabled && (
                <Badge className="gap-1 border-white/20 bg-white/10 text-primary-foreground">
                  <Sparkles className="h-3 w-3" /> AI enabled
                </Badge>
              )}
              {p.suspended && <Badge className="gap-1 border-white/20 bg-white/10 text-primary-foreground">Suspended</Badge>}
            </div>
          </div>
          <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-primary-foreground/85">
            {p.state && (
              <span className="flex items-center gap-1.5">
                <MapPin className="h-3.5 w-3.5" /> {p.state}, {p.country}
              </span>
            )}
            {p.email && (
              <span className="flex items-center gap-1.5">
                <Mail className="h-3.5 w-3.5" /> {p.email}
              </span>
            )}
            {p.phone && (
              <span className="flex items-center gap-1.5">
                <Phone className="h-3.5 w-3.5" /> {p.phone}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Usage stats */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <UsageStat label="Students" value={fmtNum(usage.students as number)} />
        <UsageStat label="Teachers" value={fmtNum(usage.teachers as number)} />
        <UsageStat label="Parents" value={fmtNum(usage.parents as number)} />
        <UsageStat label="Active users (7d)" value={fmtNum(usage.active_users_7d as number)} />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Subscription management */}
        <Panel
          title="Subscription"
          subtitle={`${sub.plan_name as string} · ${fmtCurrency(sub.price_monthly as number)} / month`}
          className="lg:col-span-1"
        >
          <div className="space-y-4">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Renewal</span>
              <span className="font-medium">{fmtDate(sub.ends_at as string | null)}</span>
            </div>
            <div>
              <div className="mb-1 flex items-center justify-between text-sm">
                <span className="text-muted-foreground">AI credits</span>
                <span className="font-medium">
                  {fmtNum(sub.ai_allowance_used as number)} / {fmtNum(sub.ai_allowance_total as number)}
                </span>
              </div>
              <ProgressBar pct={aiPct} />
            </div>

            <form
              className="space-y-3 rounded-xl border bg-muted/30 p-3"
              onSubmit={(e) => {
                e.preventDefault();
                updateSub.mutate({
                  plan_code: plan || undefined,
                  status: status || undefined,
                  ai_credits_total: aiCredits ? Number(aiCredits) : undefined,
                });
                setPlan("");
                setStatus("");
                setAiCredits("");
              }}
            >
              <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                <Pencil className="h-3.5 w-3.5" /> Adjust plan
              </p>
              <div className="space-y-1">
                <Label className="text-xs">Plan</Label>
                <Select value={plan} onValueChange={setPlan}>
                  <SelectTrigger className="h-9 w-full">
                    <SelectValue placeholder={String(sub.plan_name ?? "Trial")} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="trial">Trial</SelectItem>
                    <SelectItem value="starter">Starter</SelectItem>
                    <SelectItem value="professional">Professional</SelectItem>
                    <SelectItem value="enterprise">Enterprise</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Status</Label>
                <Select value={status} onValueChange={setStatus}>
                  <SelectTrigger className="h-9 w-full">
                    <SelectValue placeholder={titleCase(String(sub.status ?? "pending"))} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="active">Active</SelectItem>
                    <SelectItem value="trial">Trial</SelectItem>
                    <SelectItem value="past_due">Past due</SelectItem>
                    <SelectItem value="expired">Expired</SelectItem>
                    <SelectItem value="cancelled">Cancelled</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1">
                <Label className="text-xs">AI credits total</Label>
                <Input
                  className="h-9"
                  type="number"
                  min={0}
                  value={aiCredits}
                  onChange={(e) => setAiCredits(e.target.value)}
                  placeholder={fmtNum(sub.ai_allowance_total as number)}
                />
              </div>
              <Button size="sm" className="w-full" disabled={updateSub.isPending || (!plan && !status && !aiCredits)}>
                {updateSub.isPending ? "Saving…" : "Save changes"}
              </Button>
            </form>

            <div className="space-y-2">
              <Button
                size="sm"
                variant="outline"
                className="w-full"
                disabled={resetAdmin.isPending}
                onClick={() =>
                  resetAdmin.mutate(schoolId, { onSuccess: (res) => setResetResult(res) })
                }
              >
                <KeyRound className="h-3.5 w-3.5" /> Reset admin password
              </Button>
              {resetResult && (
                <div className="space-y-1.5 rounded-lg bg-amber-500/10 px-3 py-2 text-xs">
                  <p className="font-semibold text-amber-700 dark:text-amber-300">Temporary credentials for {resetResult.email}</p>
                  <p className="rounded bg-amber-500/10 px-2 py-1 font-mono font-semibold text-amber-700 dark:text-amber-300">
                    {resetResult.temp_password}
                  </p>
                  <p className="text-muted-foreground">Share once — the old password is gone.</p>
                </div>
              )}
            </div>
          </div>
        </Panel>

        {/* Admins + billing */}
        <div className="space-y-6 lg:col-span-2">
          <Panel title="School admins" subtitle={`${admins.length} super admin account(s)`}>
            {admins.length === 0 ? (
              <EmptyState message="No admin accounts for this school." />
            ) : (
              <div className="divide-y">
                {admins.map((a) => (
                  <div key={a.user_id} className="flex flex-wrap items-center justify-between gap-2 py-2.5 text-sm">
                    <div className="min-w-0">
                      <p className="font-medium">{a.full_name}</p>
                      <p className="truncate text-xs text-muted-foreground">
                        {a.email} {a.phone ? `· ${a.phone}` : ""}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant="outline">Super admin</Badge>
                      <StatusBadge status={a.status} />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Panel>

          <Panel title="Recent billing events">
            {billingEvents.length === 0 ? (
              <EmptyState message="No billing events recorded." />
            ) : (
              <div className="divide-y">
                {billingEvents.map((e) => {
                  const ev = e as { id: string; event_type: string; amount: number | null; status: string; created_at: string };
                  return (
                    <div key={ev.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5 text-sm">
                      <div className="min-w-0">
                        <p className="font-medium capitalize">{titleCase(ev.event_type)}</p>
                        <p className="text-xs text-muted-foreground">{fmtDateTime(ev.created_at)}</p>
                      </div>
                      <div className="flex items-center gap-3">
                        {ev.amount != null && ev.amount > 0 && (
                          <span className="font-semibold">{fmtCurrency(ev.amount)}</span>
                        )}
                        <StatusBadge status={ev.status} />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </Panel>

          <Panel title="Recent activity">
            {(data.activity?.length ?? 0) === 0 ? (
              <EmptyState message="No activity yet." />
            ) : (
              <div className="divide-y">
                {data.activity!.slice(0, 12).map((a) => {
                  const row = a as { id: string; ts: string; action: string; entity_type: string; details?: string; actor: string; kind: string };
                  return (
                    <div key={row.id} className="flex items-start gap-3 py-2.5">
                      <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-primary" />
                      <div className="min-w-0 flex-1">
                        <p className="text-[13px] font-medium capitalize leading-snug">
                          {titleCase(row.action)} <span className="text-muted-foreground">{row.entity_type}</span>
                        </p>
                        {row.details && <p className="truncate text-xs text-muted-foreground">{row.details}</p>}
                      </div>
                      <div className="shrink-0 text-right">
                        <p className="text-xs text-muted-foreground">{row.actor}</p>
                        <p className="text-[11px] text-muted-foreground/70">{fmtDateTime(row.ts)}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}

function UsageStat({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <div className="space-y-1 p-4">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>
        <p className="text-2xl font-bold tracking-tight">{value}</p>
      </div>
    </Card>
  );
}