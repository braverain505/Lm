"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";

import { api } from "@schoolos/shared";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Loader } from "@/components/ui/loader";
import { useActiveSchoolId, useComponents, useGradeBands, useScoreCard } from "@/hooks/use-api";

function ScoreGrid() {
  const searchParams = useSearchParams();
  const armId = searchParams.get("arm_id");
  const subjectId = searchParams.get("subject_id");
  const termId = searchParams.get("term_id");
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();

  const { data: card, isLoading } = useScoreCard(armId, subjectId, termId);
  const { data: components = [] } = useComponents(termId, armId);
  const { data: gradeBands = [] } = useGradeBands(termId);

  // Local draft edits: enrollmentId -> componentId -> string value.
  const [draft, setDraft] = useState<Record<string, Record<string, string>>>({});
  useEffect(() => {
    setDraft({});
  }, [armId, subjectId, termId]);

  const setCell = (enrollmentId: string, componentId: string, value: string) => {
    setDraft((prev) => ({
      ...prev,
      [enrollmentId]: { ...(prev[enrollmentId] ?? {}), [componentId]: value },
    }));
  };

  const cellValue = (enrollmentId: string, componentId: string): string => {
    const manual = draft[enrollmentId]?.[componentId];
    if (manual !== undefined) return manual;
    const row = card?.students.find((s) => s.enrollment_id === enrollmentId);
    const v = row?.scores[componentId];
    return v === null || v === undefined ? "" : String(v);
  };

  /** Weighted 0-100 total for a row, live over draft + saved cells:
   *  contribution = (score / max_score) * weight, exactly as the server
   *  computes it at publish. */
  const liveTotal = (enrollmentId: string): number | null => {
    const row = card?.students.find((s) => s.enrollment_id === enrollmentId);
    let anyValue = false;
    let total = 0;
    for (const c of card?.components ?? []) {
      const raw = cellValue(enrollmentId, c.id);
      if (raw === "") continue;
      const value = Number(raw);
      if (Number.isNaN(value)) continue;
      anyValue = true;
      total += (value / c.max_score) * c.weight;
    }
    if (!anyValue) return row?.total ?? null;
    return Math.round(total * 100) / 100;
  };

  const liveGrade = (enrollmentId: string): string | null => {
    const total = liveTotal(enrollmentId);
    if (total === null) return null;
    const band = gradeBands.find((b) => total >= b.min_score && total <= b.max_score);
    return band?.letter ?? null;
  };

  const save = useMutation({
    mutationFn: async () => {
      if (!schoolId || !armId || !subjectId || !termId) throw new Error("Missing grid params");
      const entries = (card?.students ?? []).map((row) => ({
        student_enrollment_id: row.enrollment_id,
        scores: components
          .filter((c) => draft[row.enrollment_id]?.[c.id] !== undefined)
          .map((c) => ({
            assessment_component_id: c.id,
            score: draft[row.enrollment_id][c.id] === "" ? null : Number(draft[row.enrollment_id][c.id]),
          })),
      }));
      return api.schoolFetch(schoolId, "/results/scorecard", {
        method: "PUT",
        body: JSON.stringify({ arm_id: armId, subject_id: subjectId, term_id: termId, entries }),
      });
    },
    onSuccess: () => {
      setDraft({});
      void queryClient.invalidateQueries({ queryKey: ["scorecard"] });
      void queryClient.invalidateQueries({ queryKey: ["readiness"] });
    },
  });

  const submit = useMutation({
    mutationFn: async () => {
      if (!schoolId || !armId || !subjectId || !termId) throw new Error("Missing params");
      return api.schoolFetch(schoolId, "/results/submit", {
        method: "POST",
        body: JSON.stringify({ arm_id: armId, subject_id: subjectId, term_id: termId }),
      });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["scorecard"] });
      void queryClient.invalidateQueries({ queryKey: ["readiness"] });
    },
  });

  const dirtyCount = useMemo(
    () => Object.values(draft).reduce((n, cells) => n + Object.keys(cells).length, 0),
    [draft],
  );

  if (isLoading) {
    return (
      <div className="flex justify-center py-20">
        <Loader />
      </div>
    );
  }

  if (!card) {
    return (
      <Card>
        <CardContent className="py-12 text-center text-muted-foreground">
          Choose an arm, subject, and term to open a score grid.
        </CardContent>
      </Card>
    );
  }

  const gradeBadge = (letter: string | null) =>
    letter ? <Badge variant="default">{letter}</Badge> : <span className="text-muted-foreground">—</span>;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            {card.arm.full_name} · {card.subject.name}
          </h1>
          <p className="text-sm text-muted-foreground">{card.term.name}</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => submit.mutate()} disabled={submit.isPending}>
            {submit.isPending ? "Submitting…" : "Submit verified"}
          </Button>
          <Button onClick={() => save.mutate()} disabled={dirtyCount === 0 || save.isPending}>
            Save {dirtyCount > 0 ? `(${dirtyCount})` : ""}
          </Button>
        </div>
      </div>

      <Card className="overflow-hidden">
        <div className="overflow-x-auto scrollbar-thin">
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                <th className="sticky left-0 bg-muted/50 px-3 py-2 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Student
                </th>
                {card.components.map((c) => (
                  <th key={c.id} className="px-3 py-2 text-center text-xs font-medium text-muted-foreground">
                    {c.name}
                    <span className="block font-normal text-[10px] text-muted-foreground/70">
                      /{c.max_score} · {c.weight}%
                    </span>
                  </th>
                ))}
                <th className="px-3 py-2 text-center text-xs font-medium text-muted-foreground">Total</th>
                <th className="px-3 py-2 text-center text-xs font-medium text-muted-foreground">Grade</th>
              </tr>
            </thead>
            <tbody>
              {card.students.map((row) => (
                <tr key={row.enrollment_id} className="border-t">
                  <td className="sticky left-0 bg-background px-3 py-2">
                    <p className="font-medium">{row.full_name}</p>
                    <p className="font-mono text-[10px] text-muted-foreground">{row.admission_no}</p>
                  </td>
                  {card.components.map((c) => (
                    <td key={c.id} className="px-2 py-1.5 text-center">
                      <Input
                        type="number"
                        min={0}
                        max={c.max_score}
                        className="h-8 w-20 text-center"
                        value={cellValue(row.enrollment_id, c.id)}
                        onChange={(e) => setCell(row.enrollment_id, c.id, e.target.value)}
                      />
                    </td>
                  ))}
                  <td className="px-3 py-2 text-center font-semibold">
                    {liveTotal(row.enrollment_id) === null
                      ? "—"
                      : liveTotal(row.enrollment_id)}
                  </td>
                  <td className="px-3 py-2 text-center">
                    {gradeBadge(liveGrade(row.enrollment_id) ?? row.grade_letter)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

export default function ScorePage() {
  return (
    <Suspense fallback={<Loader className="mx-auto my-20" />}>
      <ScoreGrid />
    </Suspense>
  );
}