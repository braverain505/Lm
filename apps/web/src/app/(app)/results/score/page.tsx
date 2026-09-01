"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Lock } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useRouter } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";

import { api } from "@schoolos/shared";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Loader } from "@/components/ui/loader";
import {
  useActiveSchoolId,
  useArms,
  useComponents,
  useGradeBands,
  useMyAssignments,
  useScoreCard,
  useSessions,
  useSubjects,
  useTerms,
} from "@/hooks/use-api";
import { useAuth } from "@/providers/auth-provider";
import { useToast } from "@/components/toast";

function ScoreContextPicker() {
  const router = useRouter();
  const { data: sessions = [] } = useSessions();
  const currentSession = sessions.find((s) => s.is_current) ?? sessions[0];
  const { data: terms = [] } = useTerms(currentSession?.id ?? null);
  const { data: arms = [] } = useArms(currentSession?.id ?? null);
  const { data: subjects = [] } = useSubjects();
  const { data: myAssignments = [] } = useMyAssignments();
  const { activeSchool } = useAuth();
  const isTeacher = activeSchool?.role?.code === "teacher" || activeSchool?.role?.code === "homeroom_teacher";
  const [termId, setTermId] = useState("");
  const [armId, setArmId] = useState("");
  const [subjectId, setSubjectId] = useState("");

  const visibleArms = isTeacher
    ? arms.filter((arm) => myAssignments.some((item) => item.arm_id === arm.id))
    : arms;
  const visibleSubjects = useMemo(() => {
    const allowed = isTeacher
      ? new Set(myAssignments.filter((item) => item.arm_id === armId).map((item) => item.subject_id))
      : null;
    return subjects.filter((subject) => !allowed || allowed.has(subject.id));
  }, [armId, isTeacher, myAssignments, subjects]);

  const selectedTerm = terms.find((t) => t.id === termId);
  const isTermClosed = selectedTerm?.status === "closed";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Score Entry</h1>
        <p className="text-sm text-muted-foreground">Select a class, subject, and term to enter scores.</p>
      </div>

      {isTermClosed && (
        <div className="flex items-center gap-3 rounded-xl border border-warning/20 bg-warning/5 px-4 py-3 text-[13px] text-warning">
          <Lock className="h-4 w-4 shrink-0" />
          <span>
            The <strong>{selectedTerm?.name}</strong> term is closed. Score entry is disabled — results are read-only.
          </span>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Open a score grid</CardTitle>
          <CardDescription>Pick the context below to start entering scores.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="space-y-2">
              <label className="text-sm font-medium">Term</label>
              <select
                className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
                value={termId}
                onChange={(e) => setTermId(e.target.value)}
              >
                <option value="">Choose term…</option>
                {terms.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}{t.status === "closed" ? " (closed)" : ""}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Class arm</label>
              <select
                className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
                value={armId}
                onChange={(e) => setArmId(e.target.value)}
                disabled={!termId}
              >
                <option value="">Choose arm…</option>
                {visibleArms.map((a) => (
                  <option key={a.id} value={a.id}>{a.full_name}</option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Subject</label>
              <select
                className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
                value={subjectId}
                onChange={(e) => setSubjectId(e.target.value)}
                disabled={!armId}
              >
                <option value="">Choose subject…</option>
                {visibleSubjects.map((s) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            </div>
          </div>
          <Button
            disabled={!armId || !subjectId || !termId || isTermClosed}
            onClick={() =>
              router.push(`/results/score?arm_id=${armId}&subject_id=${subjectId}&term_id=${termId}`)
            }
          >
            Open grid
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

function componentLabel(name: string): string {
  // Strip leading "CA" / "Exam" prefix abbreviations and clean up.
  const n = name.trim();
  if (/^CA\s*\d*/i.test(n)) return n.replace(/^CA\s*/i, "CA ");
  return name;
}

function ScoreGrid() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const initialArmId = searchParams.get("arm_id");
  const initialSubjectId = searchParams.get("subject_id");
  const initialTermId = searchParams.get("term_id");
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();

  // Allow switching context from within the grid
  const [armId, setArmId] = useState(initialArmId);
  const [subjectId, setSubjectId] = useState(initialSubjectId);
  const [termId, setTermId] = useState(initialTermId);

  // Sync from URL on first load
  useEffect(() => {
    if (initialArmId) setArmId(initialArmId);
    if (initialSubjectId) setSubjectId(initialSubjectId);
    if (initialTermId) setTermId(initialTermId);
  }, [initialArmId, initialSubjectId, initialTermId]);

  const { data: sessions = [] } = useSessions();
  const currentSession = sessions.find((s) => s.is_current) ?? sessions[0];
  const { data: terms = [] } = useTerms(currentSession?.id ?? null);
  const { data: arms = [] } = useArms(currentSession?.id ?? null);
  const { data: subjects = [] } = useSubjects();
  const { data: myAssignments = [] } = useMyAssignments();
  const { activeSchool } = useAuth();
  const isTeacher = activeSchool?.role?.code === "teacher" || activeSchool?.role?.code === "homeroom_teacher";

  const visibleArms = isTeacher
    ? arms.filter((arm) => myAssignments.some((item) => item.arm_id === arm.id))
    : arms;
  const visibleSubjects = useMemo(() => {
    const allowed = isTeacher
      ? new Set(myAssignments.filter((item) => item.arm_id === armId).map((item) => item.subject_id))
      : null;
    return subjects.filter((subject) => !allowed || allowed.has(subject.id));
  }, [armId, isTeacher, myAssignments, subjects]);

  const { data: card, isLoading } = useScoreCard(armId, subjectId, termId);
  const { data: components = [] } = useComponents(termId, armId);
  const { data: gradeBands = [] } = useGradeBands(termId);

  const activeTerm = terms.find((t) => t.id === termId);
  const isTermClosed = activeTerm?.status === "closed";

  // Local draft edits: enrollmentId -> componentId -> string value.
  const [draft, setDraft] = useState<Record<string, Record<string, string>>>({});
  useEffect(() => {
    setDraft({});
  }, [armId, subjectId, termId]);

  const setCell = (enrollmentId: string, componentId: string, value: string) => {
    if (isTermClosed) return; // Block edits on closed terms
    // Score threshold: validate the value doesn't exceed max_score
    const component = components.find((c) => c.id === componentId);
    if (component && value !== "") {
      const num = Number(value);
      if (!Number.isNaN(num) && num > component.max_score) {
        toast(`Score cannot exceed ${component.max_score}`, "error");
        return;
      }
      if (!Number.isNaN(num) && num < 0) {
        toast("Score cannot be negative", "error");
        return;
      }
    }
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
    // Try configured grade bands first
    if (gradeBands.length > 0) {
      const band = gradeBands.find((b) => total >= b.min_score && total <= b.max_score);
      if (band) return band.letter;
    }
    // Fallback: default grading scale
    if (total >= 70) return "A";
    if (total >= 60) return "B";
    if (total >= 50) return "C";
    if (total >= 40) return "D";
    return "F";
  };

  const { toast } = useToast();

  const save = useMutation({
    mutationFn: async () => {
      if (!schoolId || !armId || !subjectId || !termId) throw new Error("Missing grid params");
      if (isTermClosed) throw new Error("This term is closed — scores cannot be saved");
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
      toast("Scores saved successfully");
    },
    onError: () => {
      toast("Failed to save scores", "error");
    },
  });

  const submit = useMutation({
    mutationFn: async () => {
      if (!schoolId || !armId || !subjectId || !termId) throw new Error("Missing params");
      if (isTermClosed) throw new Error("This term is closed — scores cannot be submitted");
      return api.schoolFetch(schoolId, "/results/submit", {
        method: "POST",
        body: JSON.stringify({ arm_id: armId, subject_id: subjectId, term_id: termId }),
      });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["scorecard"] });
      void queryClient.invalidateQueries({ queryKey: ["readiness"] });
      toast("Results submitted for review");
    },
    onError: () => {
      toast("Failed to submit results", "error");
    },
  });

  const dirtyCount = useMemo(
    () => Object.values(draft).reduce((n, cells) => n + Object.keys(cells).length, 0),
    [draft],
  );

  if (!armId || !subjectId || !termId) return <ScoreContextPicker />;

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

  // Quick-switch handlers
  const switchSubject = (newSubjectId: string) => {
    setSubjectId(newSubjectId);
    setDraft({});
    router.replace(`/results/score?arm_id=${armId}&subject_id=${newSubjectId}&term_id=${termId}`);
  };

  const switchArm = (newArmId: string) => {
    setArmId(newArmId);
    setSubjectId("");
    setDraft({});
  };

  const switchTerm = (newTermId: string) => {
    setTermId(newTermId);
    setDraft({});
  };

  return (
    <div className="space-y-6">
      {/* Closed term warning */}
      {isTermClosed && (
        <div className="flex items-center gap-3 rounded-xl border border-warning/20 bg-warning/5 px-4 py-3 text-[13px] text-warning">
          <Lock className="h-4 w-4 shrink-0" />
          <span>
            The <strong>{activeTerm?.name}</strong> term is closed. This grid is read-only — score changes are disabled.
          </span>
        </div>
      )}

      {/* Quick-switch selectors */}
      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-border/60 bg-muted/30 p-3">
        <div className="space-y-1">
          <label className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/60">Term</label>
          <select
            className="h-8 rounded-lg border border-border/60 bg-background px-2 text-[12px]"
            value={termId ?? ""}
            onChange={(e) => switchTerm(e.target.value)}
          >
            {terms.map((t) => (
              <option key={t.id} value={t.id}>{t.name}</option>
            ))}
          </select>
        </div>
        <div className="space-y-1">
          <label className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/60">Class</label>
          <select
            className="h-8 rounded-lg border border-border/60 bg-background px-2 text-[12px]"
            value={armId ?? ""}
            onChange={(e) => switchArm(e.target.value)}
          >
            {visibleArms.map((a) => (
              <option key={a.id} value={a.id}>{a.full_name}</option>
            ))}
          </select>
        </div>
        <div className="space-y-1">
          <label className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/60">Subject</label>
          <select
            className="h-8 rounded-lg border border-border/60 bg-background px-2 text-[12px]"
            value={subjectId ?? ""}
            onChange={(e) => switchSubject(e.target.value)}
          >
            {visibleSubjects.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            {card.arm.full_name} · {card.subject.name}
          </h1>
          <p className="text-sm text-muted-foreground">{card.term.name}</p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={() => submit.mutate()}
            disabled={submit.isPending || isTermClosed}
            isLoading={submit.isPending}
          >
            {submit.isPending ? "Submitting…" : "Submit verified"}
          </Button>
          <Button
            onClick={() => save.mutate()}
            disabled={dirtyCount === 0 || save.isPending || isTermClosed}
            isLoading={save.isPending}
          >
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
                    {componentLabel(c.name)}
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
                        className={`h-8 w-20 text-center ${isTermClosed ? "opacity-60 cursor-not-allowed" : ""}`}
                        value={cellValue(row.enrollment_id, c.id)}
                        onChange={(e) => setCell(row.enrollment_id, c.id, e.target.value)}
                        disabled={isTermClosed}
                        readOnly={isTermClosed}
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
