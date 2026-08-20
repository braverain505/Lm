"use client";

import { ClipboardList, FileText, ListChecks } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { useArms, useAssignments, useMyAssignments, useReadiness, useSessions, useSubjects, useTerms } from "@/hooks/use-api";
import { useAuth } from "@/providers/auth-provider";

export default function ResultsPage() {
  const { activeSchool } = useAuth();
  const role = activeSchool?.role?.code ?? "";
  const isTeacherRole = role === "teacher" || role === "homeroom_teacher";
  const { data: sessions = [] } = useSessions();
  const current = sessions.find((s) => s.is_current) ?? sessions[0];
  const { data: terms = [] } = useTerms(current?.id ?? null);
  const term = terms.find((t) => t.is_current) ?? terms[0];
  const { data: arms = [] } = useArms(current?.id ?? null);
  const { data: myAssignments = [] } = useMyAssignments();

  // Teachers only enter scores for their assigned arms × subjects.
  const myArmIds = new Set(myAssignments.map((a) => a.arm_id));
  const mySubjectIds = new Set(myAssignments.map((a) => a.subject_id));
  const visibleArms = isTeacherRole
    ? arms.filter((a) => myArmIds.has(a.id))
    : arms;
  const visibleSubjectIds = isTeacherRole ? mySubjectIds : null;

  // For the demo grid we let the user pick an arm, then any subject offering.
  const [armId, setArmId] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const { data: assignments = [] } = useAssignments(armId || null);
  const { data: readiness = [] } = useReadiness(term?.id ?? null);
  const { data: subjects = [] } = useSubjects();

  // Subject options = the school's subject catalog, intersected with the
  // offering for the selected arm (via assignments) and/or readiness rows.
  const subjectOptions = useMemo(() => {
    const nameById = new Map(subjects.map((s) => [s.id, s.name]));
    readiness.forEach((r) => nameById.set(r.subject_id, r.subject_name));
    const wanted =
      readiness.length > 0
        ? new Set([...readiness.map((r) => r.subject_id), ...assignments.map((a) => a.subject_id)])
        : new Set(assignments.map((a) => a.subject_id));
    if (armId && wanted.size === 0) return [];
    let options = [...nameById.entries()]
      .filter(([id]) => !armId || wanted.has(id))
      .map(([id, name]) => ({ id, name }))
      .sort((a, b) => a.name.localeCompare(b.name));
    if (visibleSubjectIds) {
      options = options.filter((s) => visibleSubjectIds.has(s.id));
    }
    return options;
  }, [subjects, readiness, assignments, armId, visibleSubjectIds]);

  // Couple of quick links: for each arm pick the first subject to open a grid.
  const quick = useMemo(() => {
    const out: { armName: string; subjectName: string; url: string }[] = [];
    const byArm = new Map<string, typeof readiness>();
    readiness
      .filter((r) => !isTeacherRole || myArmIds.has(r.arm_id))
      .forEach((r) => {
        const list = byArm.get(r.arm_id) ?? [];
        list.push(r);
        byArm.set(r.arm_id, list);
      });
    byArm.forEach((rows, arm_id) => {
      if (rows.length) {
        const first = rows[0];
        out.push({
          armName: first.arm_name,
          subjectName: first.subject_name,
          url: `/results/score?arm_id=${arm_id}&subject_id=${first.subject_id}&term_id=${term?.id}`,
        });
      }
    });
    return out.slice(0, 6);
  }, [readiness, term?.id, isTeacherRole, myArmIds]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Results</h1>
        <p className="text-sm text-muted-foreground">
          {current ? `Session: ${current.name}` : "Set up a session first"}
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Score entry</CardTitle>
            <CardDescription>Open a score grid for an arm × subject.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Class arm</Label>
              <select
                className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
                value={armId}
                onChange={(e) => setArmId(e.target.value)}
              >
                <option value="">Choose arm…</option>
                {visibleArms.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.full_name}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <Label>Subject</Label>
              <select
                className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
                value={subjectId}
                onChange={(e) => setSubjectId(e.target.value)}
                disabled={!armId}
              >
                <option value="">Choose subject…</option>
                {subjectOptions.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </div>
            <Button
              className="w-full"
              disabled={!armId || !subjectId || !current}
              asChild
            >
              <Link href={`/results/score?arm_id=${armId}&subject_id=${subjectId}&term_id=${current?.id}`}>
                <ClipboardList className="h-4 w-4" /> Open grid
              </Link>
            </Button>
          </CardContent>
        </Card>

        <div className="lg:col-span-2 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Ready to enter</CardTitle>
              <CardDescription>A few grids you can open today.</CardDescription>
            </CardHeader>
            <CardContent>
              {quick.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No readiness rows yet. Enter your scores after assigning components to a term.
                </p>
              ) : (
                <div className="grid gap-2 sm:grid-cols-2">
                  {quick.map((g) => (
                    <Link key={g.url} href={g.url} className="rounded-md border px-3 py-2 text-sm transition-colors hover:bg-accent">
                      <span className="font-medium">{g.armName}</span> · {g.subjectName}
                    </Link>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Approvals</CardTitle>
              <CardDescription>Verify → approve → publish submitted results.</CardDescription>
            </CardHeader>
            <CardContent>
              <Button asChild>
                <Link href="/approvals">
                  <ListChecks className="h-4 w-4" /> Open approval workbench
                </Link>
              </Button>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Report cards</CardTitle>
              <CardDescription>Print term reports from published results.</CardDescription>
            </CardHeader>
            <CardContent>
              <Button asChild>
                <Link href="/reports">
                  <FileText className="h-4 w-4" /> Open report cards
                </Link>
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}