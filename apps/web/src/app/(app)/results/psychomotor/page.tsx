"use client";

import { useEffect, useMemo, useState } from "react";

import { NoAccess } from "@/components/access-denied";
import { PsychomotorEditor } from "@/components/psychomotor-editor";
import { Card, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useArms,
  useCanEnterResults,
  useMyAssignments,
  useRoster,
} from "@/hooks/use-api";
import { useAuth } from "@/providers/auth-provider";
import { useSessionTerm } from "@/providers/session-context";

/**
 * Psychomotor & affective ratings — the class teacher's own record of a
 * student's skills, practical ability and conduct.
 *
 * This used to sit inside the Report Cards page, which is the Exam Office's
 * desk, so the only people who could reach it were the ones who least needed to
 * write it. It is its own page now: score-entry roles and a student's homeroom
 * teacher can keep the record up to date, and the Exam Office reads the result
 * on the printed card.
 *
 * The API applies the same rule per request (``results.enter`` or the student's
 * homeroom teacher), so this page's gate is a convenience, not the control.
 */
export default function PsychomotorPage() {
  const { activeSchool } = useAuth();
  const role = activeSchool?.role?.code ?? "";
  const canEnter = useCanEnterResults();
  const isHomeroomTeacher = role === "homeroom_teacher";
  const canEdit = canEnter || isHomeroomTeacher;

  const { session, term, loadingTerms } = useSessionTerm();
  const { data: arms = [] } = useArms(session?.id ?? null);
  const { data: myAssignments = [] } = useMyAssignments();

  const isTeacherRole = role === "teacher" || isHomeroomTeacher;
  const visibleArms = useMemo(
    () =>
      isTeacherRole
        ? arms.filter((a) => myAssignments.some((m) => m.arm_id === a.id))
        : arms,
    [arms, isTeacherRole, myAssignments],
  );

  const [armId, setArmId] = useState("");
  const [studentId, setStudentId] = useState("");

  // Teachers land on a class they actually teach instead of an empty picker.
  useEffect(() => {
    if (isTeacherRole && visibleArms.length > 0 && !armId) {
      setArmId(visibleArms[0].id);
    }
  }, [isTeacherRole, visibleArms, armId]);

  const { data: roster = [], isLoading: rosterLoading } = useRoster(armId || null);

  if (!canEdit) {
    return (
      <NoAccess
        title="Psychomotor is the class teacher's record"
        message="Only score-entry roles and a student's homeroom teacher keep this record. You can still review published report cards from the Report Cards page."
        backHref="/results"
        backLabel="Go to Results"
      />
    );
  }

  return (
    <div className="space-y-5">
      <div className="min-w-0">
        <h1 className="text-[22px] font-bold tracking-tight text-foreground">
          Psychomotor &amp; affective
        </h1>
        <p className="mt-1 text-[13px] text-muted-foreground">
          {term
            ? `${term.name} · record a student's skills, practical ability and conduct.`
            : "Pick a term to begin."}
        </p>
      </div>

      <Card className="premium-card">
        <CardContent className="grid gap-4 py-5 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="arm">Class arm</Label>
            <select
              id="arm"
              className="flex h-9 w-full rounded-xl border border-border/80 bg-background/50 px-3 text-[13px] shadow-sm transition-all"
              value={armId}
              onChange={(e) => {
                setArmId(e.target.value);
                setStudentId("");
              }}
            >
              <option value="">Choose arm…</option>
              {visibleArms.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.full_name}
                </option>
              ))}
            </select>
            {isTeacherRole && visibleArms.length === 0 && (
              <p className="text-[12px] text-muted-foreground">
                You have no classes assigned yet — ask an administrator to assign
                you a subject.
              </p>
            )}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="student">Student</Label>
            <select
              id="student"
              className="flex h-9 w-full rounded-xl border border-border/80 bg-background/50 px-3 text-[13px] shadow-sm transition-all"
              value={studentId}
              onChange={(e) => setStudentId(e.target.value)}
              disabled={!armId}
            >
              <option value="">Choose student…</option>
              {roster.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.full_name} · {s.admission_no}
                </option>
              ))}
            </select>
          </div>
        </CardContent>
      </Card>

      {rosterLoading && armId ? (
        <Skeleton className="h-40 w-full" />
      ) : !studentId || !term ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            {!term
              ? loadingTerms
                ? "Loading terms…"
                : "No active term — ask an administrator to activate one."
              : "Pick a class and a student to open their psychomotor record."}
          </CardContent>
        </Card>
      ) : roster.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            No students are enrolled in this class yet.
          </CardContent>
        </Card>
      ) : (
        <PsychomotorEditor studentId={studentId} termId={term.id} allowed />
      )}
    </div>
  );
}
