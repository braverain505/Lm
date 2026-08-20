"use client";

import Link from "next/link";

import { EmptyState, Panel, PanelSkeleton, ProgressBar, StatCard, StatusBadge, fmtDate, fmtNum, titleCase } from "@/components/platform-utils";
import { useSaSubscriptions } from "@/hooks/use-superadmin";

interface SubListRow {
  school_id: string;
  school_name: string;
  plan: string;
  ends_at?: string | null;
  since?: string | null;
  ai_used?: number;
  ai_total?: number;
  pct?: number;
}

export default function SuperAdminSubscriptionsPage() {
  const { data, isLoading } = useSaSubscriptions();

  const summary = (data?.summary ?? {}) as Record<string, number>;
  const distribution = (data?.distribution ?? []) as Array<{ plan: string; code: string; schools: number; mrr: number; pct: number }>;
  const trialsEnding = (data?.trials_ending_soon ?? []) as unknown as SubListRow[];
  const expired = (data?.expired ?? []) as unknown as SubListRow[];
  const failed = (data?.failed ?? []) as unknown as SubListRow[];
  const nearing = (data?.nearing_limits ?? []) as unknown as SubListRow[];

  return (
    <div className="space-y-6">
      {isLoading ? (
        <PanelSkeleton rows={6} />
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <StatCard label="Active" value={fmtNum(summary.active)} />
            <StatCard label="Trials" value={fmtNum(summary.trial)} />
            <StatCard label="Past due" value={fmtNum(summary.past_due)} />
            <StatCard label="Expired" value={fmtNum(summary.expired)} />
            <StatCard label="Pending" value={fmtNum(summary.pending)} />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Panel title="Plan distribution" subtitle="Schools on each plan">
              {distribution.length === 0 ? (
                <EmptyState message="No subscriptions yet." />
              ) : (
                <div className="space-y-3">
                  {distribution.map((d) => (
                    <div key={d.code} className="flex items-center justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between text-sm">
                          <span className="font-medium">{titleCase(d.plan)}</span>
                          <span className="text-muted-foreground">
                            {fmtNum(d.schools)} schools · {fmtNum(d.mrr)} MRR
                          </span>
                        </div>
                        <ProgressBar pct={d.pct} className="mt-1.5" />
                      </div>
                      <span className="w-12 text-right text-sm font-semibold">{d.pct}%</span>
                    </div>
                  ))}
                </div>
              )}
            </Panel>

            <Panel title="Trials ending soon" subtitle="Within 3 days">
              {trialsEnding.length === 0 ? (
                <EmptyState message="No trials ending soon." />
              ) : (
                <div className="divide-y">
                  {trialsEnding.map((s) => (
                    <SchoolLinkRow key={s.school_id} s={s} label={`Ends ${fmtDate(s.ends_at)}`} />
                  ))}
                </div>
              )}
            </Panel>

            <Panel title="Past due" subtitle="Failed subscription payments">
              {failed.length === 0 ? (
                <EmptyState message="No failed payments." />
              ) : (
                <div className="divide-y">
                  {failed.map((s) => (
                    <SchoolLinkRow key={s.school_id} s={s} label={`Since ${fmtDate(s.since)}`} />
                  ))}
                </div>
              )}
            </Panel>

            <Panel title="Expired" subtitle="Subscriptions that lapsed">
              {expired.length === 0 ? (
                <EmptyState message="No expired subscriptions." />
              ) : (
                <div className="divide-y">
                  {expired.map((s) => (
                    <SchoolLinkRow key={s.school_id} s={s} label={`Ended ${fmtDate(s.ends_at)}`} />
                  ))}
                </div>
              )}
            </Panel>

            <Panel title="Nearing AI limits" subtitle="At least 80% of credits used" className="lg:col-span-2">
              {nearing.length === 0 ? (
                <EmptyState message="No schools near their AI limits." />
              ) : (
                <div className="divide-y">
                  {nearing.map((s) => (
                    <Link
                      key={s.school_id}
                      href={`/super-admin/schools/${s.school_id}`}
                      className="flex items-center justify-between gap-3 py-2.5 text-sm transition-colors hover:bg-accent/50"
                    >
                      <div className="min-w-0">
                        <p className="truncate font-medium">{s.school_name}</p>
                        <p className="text-xs text-muted-foreground">
                          {fmtNum(s.ai_used)} / {fmtNum(s.ai_total)} credits
                        </p>
                      </div>
                      <div className="flex w-40 items-center gap-2">
                        <ProgressBar pct={s.pct ?? 0} className="flex-1" />
                        <span className="w-10 text-right text-xs font-semibold">{s.pct}%</span>
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </Panel>
          </div>
        </>
      )}
    </div>
  );
}

function SchoolLinkRow({ s, label }: { s: SubListRow; label: string }) {
  return (
    <Link
      href={`/super-admin/schools/${s.school_id}`}
      className="flex items-center justify-between gap-3 py-2.5 text-sm transition-colors hover:bg-accent/50"
    >
      <div className="min-w-0">
        <p className="truncate font-medium">{s.school_name}</p>
        <p className="text-xs text-muted-foreground">{titleCase(s.plan)}</p>
      </div>
      <span className="shrink-0 text-xs text-muted-foreground">{label}</span>
    </Link>
  );
}