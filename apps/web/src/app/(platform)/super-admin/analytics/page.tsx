"use client";

import { EmptyState, Panel, PanelSkeleton, StatCard, fmtNum, titleCase } from "@/components/platform-utils";
import { useSaEngagement, useSaGeo } from "@/hooks/use-superadmin";

export default function SuperAdminAnalyticsPage() {
  const eng = useSaEngagement();
  const geo = useSaGeo();
  const isLoading = eng.isLoading || geo.isLoading;

  const active = (eng.data?.active ?? {}) as Record<string, number>;
  const logins = (eng.data?.logins ?? {}) as Record<string, number>;
  const mostActive = (eng.data?.most_active ?? []) as Array<{ school_id: string; school_name: string; activity: number; rank: number }>;
  const atRisk = (eng.data?.at_risk ?? []) as Array<{ school_id: string; school_name: string; days_inactive: number; reason: string }>;
  const inactive = (eng.data?.inactive_7d ?? []) as Array<{ school_id: string; school_name: string; days_inactive: number }>;
  const geoItems = (geo.data?.items ?? []) as Array<{ country: string; state: string; schools: number; students: number; teachers: number }>;

  return (
    <div className="space-y-6">
      {isLoading ? (
        <PanelSkeleton rows={6} />
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Daily active users" value={fmtNum(active.dau)} />
            <StatCard label="Weekly active users" value={fmtNum(active.wau)} />
            <StatCard label="Monthly active users" value={fmtNum(active.mau)} />
            <StatCard label="Schools active today" value={fmtNum(eng.data?.schools_active_today)} sub={`${fmtNum(eng.data?.schools_inactive_7d)} inactive 7d`} />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Panel title="Logins by role" subtitle="Audited sign-ins this month">
              <div className="grid grid-cols-3 gap-3">
                <LoginStat label="Teachers" value={logins.teacher} />
                <LoginStat label="Parents" value={logins.parent} />
                <LoginStat label="Admins" value={logins.admin} />
                <LoginStat label="Today" value={logins.today} />
                <LoginStat label="This week" value={logins.week} />
                <LoginStat label="This month" value={logins.month} />
              </div>
            </Panel>

            <Panel title="Most active schools">
              {mostActive.length === 0 ? (
                <EmptyState message="No activity recorded yet." />
              ) : (
                <div className="divide-y">
                  {mostActive.map((s) => (
                    <div key={s.school_id} className="flex items-center justify-between gap-3 py-2.5 text-sm">
                      <div className="flex min-w-0 items-center gap-3">
                        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-primary/10 text-[11px] font-bold text-primary">
                          {s.rank}
                        </span>
                        <p className="truncate font-medium">{s.school_name}</p>
                      </div>
                      <span className="text-xs text-muted-foreground">{fmtNum(s.activity)} events</span>
                    </div>
                  ))}
                </div>
              )}
            </Panel>

            <Panel title="At-risk schools" subtitle="No activity for 14+ days">
              {atRisk.length === 0 ? (
                <EmptyState message="No at-risk schools." />
              ) : (
                <div className="divide-y">
                  {atRisk.map((s) => (
                    <div key={s.school_id} className="flex items-center justify-between gap-3 py-2.5 text-sm">
                      <div className="min-w-0">
                        <p className="truncate font-medium">{s.school_name}</p>
                        <p className="text-xs text-muted-foreground">{s.reason}</p>
                      </div>
                      <span className="shrink-0 text-xs font-semibold text-destructive">{s.days_inactive}d</span>
                    </div>
                  ))}
                </div>
              )}
            </Panel>

            <Panel title="Geographic distribution" subtitle="Schools and users by state">
              {geoItems.length === 0 ? (
                <EmptyState message="No geographic data yet." />
              ) : (
                <div className="divide-y">
                  {geoItems.map((g) => (
                    <div key={`${g.country}-${g.state}`} className="flex items-center justify-between gap-3 py-2.5 text-sm">
                      <div className="min-w-0">
                        <p className="truncate font-medium">{g.state}</p>
                        <p className="text-xs text-muted-foreground">{g.country}</p>
                      </div>
                      <div className="flex shrink-0 items-center gap-4 text-xs text-muted-foreground">
                        <span>{fmtNum(g.schools)} schools</span>
                        <span>{fmtNum(g.students)} students</span>
                        <span>{fmtNum(g.teachers)} teachers</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Panel>

            <Panel title="Recently inactive" subtitle="No activity for 7+ days" className="lg:col-span-2">
              {inactive.length === 0 ? (
                <EmptyState message="No inactive schools." />
              ) : (
                <div className="divide-y">
                  {inactive.map((s) => (
                    <div key={s.school_id} className="flex items-center justify-between gap-3 py-2.5 text-sm">
                      <p className="truncate font-medium">{s.school_name}</p>
                      <span className="shrink-0 text-xs text-muted-foreground">{s.days_inactive} days inactive</span>
                    </div>
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

function LoginStat({ label, value }: { label: string; value: number | undefined }) {
  return (
    <div className="rounded-xl border bg-muted/30 p-3">
      <p className="text-xl font-bold">{fmtNum(value)}</p>
      <p className="text-[11px] text-muted-foreground">{titleCase(label)}</p>
    </div>
  );
}