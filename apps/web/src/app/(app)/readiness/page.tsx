"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ReadinessBar } from "@/components/readiness-bar";
import { useReadiness, useSessions, useTerms } from "@/hooks/use-api";
import Link from "next/link";

export default function ReadinessPage() {
  const { data: sessions = [] } = useSessions();
  const current = sessions.find((s) => s.is_current) ?? sessions[0];
  const { data: terms = [] } = useTerms(current?.id ?? null);
  const term = terms.find((t) => t.is_current) ?? terms[0];
  const { data = [], isLoading } = useReadiness(term?.id ?? null);

  const grouped = new Map<string, typeof data>();
  data.forEach((r) => {
    const list = grouped.get(r.arm_name) ?? [];
    list.push(r);
    grouped.set(r.arm_name, list);
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Results readiness</h1>
        <p className="text-sm text-muted-foreground">
          {term ? `Term coverage for ${term.name}` : current ? `No terms yet for ${current.name}` : "Set up a session first"}
        </p>
      </div>

      {isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : grouped.size === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            No readiness data yet. Enroll students in a class and enter scores to see coverage.
          </CardContent>
        </Card>
      ) : (
        [...grouped.entries()].map(([armName, rows]) => {
          const armPct = Math.round(rows.reduce((acc, r) => acc + r.entered_pct, 0) / rows.length);
          return (
            <Card key={armName}>
              <CardHeader>
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <CardTitle>{armName}</CardTitle>
                    <CardDescription>{rows.length} subjects</CardDescription>
                  </div>
                  <div className="flex items-center gap-3">
                    <ReadinessBar value={armPct} size="lg" className="w-40" />
                    <span className="w-10 text-right text-sm font-semibold tabular-nums">
                      {armPct}%
                    </span>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-3 p-4">
                {rows.map((row) => {
                  const pct = Math.round(row.entered_pct);
                  const tone =
                    pct === 100 ? "success" : pct > 0 ? "warning" : "muted";
                  return (
                    <div key={`${row.arm_id}-${row.subject_id}`} className="flex items-center gap-3">
                      <Link
                        href={`/results/score?arm_id=${row.arm_id}&subject_id=${row.subject_id}&term_id=${term?.id}`}
                        className="w-40 shrink-0 truncate text-sm font-medium hover:text-primary"
                      >
                        {row.subject_name}
                      </Link>
                      <ReadinessBar value={pct} size="md" className="flex-1" />
                      <span className="w-10 text-right text-sm tabular-nums">{pct}%</span>
                      <Badge variant={tone}>
                        {row.entered}/{row.student_count} entered
                      </Badge>
                    </div>
                  );
                })}
              </CardContent>
            </Card>
          );
        })
      )}
    </div>
  );
}