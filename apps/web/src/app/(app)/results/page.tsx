"use client";

import { ClipboardList, FileText, ListChecks } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { useArms, useAssignments, useMyAssignments, useReadiness, useSessions, useSubjects, useTerms } from "@/hooks/use-api";
import { useAuth } from "@/providers/auth-provider";

export default function ResultsPage() {
  const { activeSchool } = useAuth();
  const role = activeSchool?.role?.code ?? "";
  const isTeacherRole = role === "teacher" || role === "homeroom_teacher";
  const isHomeroomTeacher = role === "homeroom_teacher";
  const canComment = role === "principal" || role === "vp_academics" || role === "homeroom_teacher";
  const isSupervisor = !isTeacherRole;

  const { data: sessions = [] } = useSessions();
  const current = sessions.find((s) => s.is_current) ?? sessions[0];
  const { data: terms = [] } = useTerms(current?.id ?? null);
  const { data: arms = [] } = useArms(current?.id ?? null);
  const { data: myAssignments = [] } = useMyAssignments();

  const myArmIds = useMemo(() => new Set(myAssignments.map((a) => a.arm_id)), [myAssignments]);
  const mySubjectIds = useMemo(() => new Set(myAssignments.map((a) => a.subject_id)), [myAssignments]);
  const visibleArms = isTeacherRole ? arms.filter((a) => myArmIds.has(a.id)) : arms;
  const visibleSubjectIds = isTeacherRole ? mySubjectIds : null;

  const [armId, setArmId] = useState("");
  const [subjectId, setSubjectId] = useState("");

  const [termId, setTermId] = useState<string | null>(null);
  useEffect(() => {
    if (terms.length > 0 && termId === null) {
      const currentTerm = terms.find((t) => t.is_current);
      setTermId(currentTerm?.id ?? terms[0]?.id ?? null);
    }
  }, [terms, termId]);

  useEffect(() => {
    if (isTeacherRole && visibleArms.length > 0 && !armId) {
      setArmId(visibleArms[0].id);
    }
  }, [isTeacherRole, visibleArms, armId]);

  const { data: assignments = [] } = useAssignments(armId || null);
  const { data: readiness = [] } = useReadiness(termId);
  const { data: subjects = [] } = useSubjects();

  const subjectOptions = useMemo(() => {
    let options = (isTeacherRole
      ? subjects.filter((s) => readiness.some((r) => r.subject_id === s.id))
      : subjects
    ).map((s) => ({ id: s.id, name: s.name }));
    if (visibleSubjectIds) {
      options = options.filter((s) => visibleSubjectIds.has(s.id));
    }
    if (armId) {
      const wanted = new Set(assignments.map((a) => a.subject_id));
      options = options.filter((s) => wanted.has(s.id));
    }
    return options.sort((a, b) => a.name.localeCompare(b.name));
  }, [subjects, readiness, assignments, armId, visibleSubjectIds]);

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
          url: `/results/score?arm_id=${arm_id}&subject_id=${first.subject_id}&term_id=${termId}`,
        });
      }
    });
    return out.slice(0, 6);
  }, [readiness, termId, isTeacherRole, myArmIds]);

  return (
    <div className="space-y-5">
      <div className="min-w-0">
        <h1 className="text-[22px] font-bold tracking-tight text-foreground">Results</h1>
        <p className="mt-1 text-[13px] text-muted-foreground">
          {current ? `Session: ${current.name}` : "Set up a session first"}
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        {/* Score entry card */}
        <Card className="premium-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-[15px]">Score entry</CardTitle>
            <CardDescription>Open a score grid for an arm × subject.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <Label>Term</Label>
              <select
                className="flex h-9 w-full rounded-xl border border-border/80 bg-background/50 px-3 text-[13px] shadow-sm transition-all"
                value={termId ?? ""}
                onChange={(e) => setTermId(e.target.value || null)}
              >
                <option value="">Choose term…</option>
                {terms.map((t) => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <Label>Class arm</Label>
              <select
                className="flex h-9 w-full rounded-xl border border-border/80 bg-background/50 px-3 text-[13px] shadow-sm transition-all"
                value={armId}
                onChange={(e) => setArmId(e.target.value)}
              >
                <option value="">Choose arm…</option>
                {visibleArms.map((a) => (
                  <option key={a.id} value={a.id}>{a.full_name}</option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <Label>Subject</Label>
              <select
                className="flex h-9 w-full rounded-xl border border-border/80 bg-background/50 px-3 text-[13px] shadow-sm transition-all"
                value={subjectId}
                onChange={(e) => setSubjectId(e.target.value)}
                disabled={!armId}
              >
                <option value="">Choose subject…</option>
                {subjectOptions.map((s) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            </div>
            <Button className="w-full" asChild disabled={!armId || !subjectId || !termId}>
              <Link href={`/results/score?arm_id=${armId}&subject_id=${subjectId}&term_id=${termId}`}>
                <ClipboardList className="h-4 w-4" /> Open grid
              </Link>
            </Button>
          </CardContent>
        </Card>

        {/* Homeroom comments card */}
        {canComment && (
          <Card className="premium-card">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-[15px]">Add comments</CardTitle>
              <CardDescription>Add homeroom comments for your class.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-1.5">
                <Label>Term</Label>
                <select
                  className="flex h-9 w-full rounded-xl border border-border/80 bg-background/50 px-3 text-[13px] shadow-sm transition-all"
                  value={termId ?? ""}
                  onChange={(e) => setTermId(e.target.value || null)}
                >
                  <option value="">Choose term…</option>
                  {terms.map((t) => (
                    <option key={t.id} value={t.id}>{t.name}</option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5">
                <Label>Class arm</Label>
                <select
                  className="flex h-9 w-full rounded-xl border border-border/80 bg-background/50 px-3 text-[13px] shadow-sm transition-all"
                  value={armId}
                  onChange={(e) => setArmId(e.target.value)}
                >
                  <option value="">Choose arm…</option>
                  {visibleArms.map((a) => (
                    <option key={a.id} value={a.id}>{a.full_name}</option>
                  ))}
                </select>
              </div>
              <Button className="w-full" asChild disabled={!armId || !termId}>
                <Link href={`/results/comments?arm_id=${armId}&term_id=${termId}`}>
                  <FileText className="h-4 w-4" /> Add comments
                </Link>
              </Button>
            </CardContent>
          </Card>
        )}

        <div className="lg:col-span-2 space-y-4">
          {/* Quick links */}
          <Card className="premium-card">
            <CardHeader>
              <CardTitle className="text-[15px]">Ready to enter</CardTitle>
              <CardDescription>A few grids you can open today.</CardDescription>
            </CardHeader>
            <CardContent>
              {quick.length === 0 ? (
                <p className="text-[13px] text-muted-foreground/70">
                  No readiness rows yet. Enter your scores after assigning components to a term.
                </p>
              ) : (
                <div className="grid gap-2 sm:grid-cols-2">
                  {quick.map((g) => (
                    <Link key={g.url} href={g.url} className="rounded-xl border border-border/40 px-3.5 py-2.5 text-[13px] transition-all duration-150 hover:border-primary/20 hover:bg-accent/50">
                      <span className="font-medium">{g.armName}</span> <span className="text-muted-foreground">· {g.subjectName}</span>
                    </Link>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Approvals */}
          {isSupervisor && (
            <Card className="premium-card">
              <CardHeader>
                <CardTitle className="text-[15px]">Approvals</CardTitle>
                <CardDescription>Verify → approve → publish submitted results.</CardDescription>
              </CardHeader>
              <CardContent>
                <Button asChild>
                  <Link href="/approvals" className="gap-1.5">
                    <ListChecks className="h-4 w-4" /> Open approval workbench
                  </Link>
                </Button>
              </CardContent>
            </Card>
          )}

          {/* Report cards */}
          {isSupervisor && (
            <Card className="premium-card">
              <CardHeader>
                <CardTitle className="text-[15px]">Report cards</CardTitle>
                <CardDescription>Print term reports from published results.</CardDescription>
              </CardHeader>
              <CardContent>
                <Button asChild>
                  <Link href="/reports" className="gap-1.5">
                    <FileText className="h-4 w-4" /> Open report cards
                  </Link>
                </Button>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
