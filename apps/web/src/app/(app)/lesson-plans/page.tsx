"use client";

import { Sparkles } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useCanComment, useArms, useGenerateLessonPlan, useLessonPlan, useOfferings, useSchoolMe, useSessions, useSubjects, useTerms } from "@/hooks/use-api";
import { cn } from "@/lib/utils";
import { PremiumLock, useAiEnabled } from "@/components/premium-lock";

export default function LessonPlansPage() {
  const aiEnabled = useAiEnabled();
  const { data: school } = useSchoolMe();
  const { data: sessions = [] } = useSessions();
  const current = sessions.find((s) => s.is_current) ?? sessions[0];
  const { data: terms = [] } = useTerms(current?.id ?? null);
  const { data: arms = [] } = useArms(current?.id ?? null);
  const { data: subjects = [] } = useSubjects();

  const [activeTermId, setActiveTermId] = useState<string | null>(null);
  const term = terms.find((t) => t.id === activeTermId) ?? terms.find((t) => t.is_current) ?? terms[0];
  const [armId, setArmId] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [topic, setTopic] = useState("");
  const [periods, setPeriods] = useState(2);

  const { data: offerings = [] } = useOfferings(armId || null);
  const offered = useMemo(
    () => offerings.map((o) => subjects.find((s) => s.id === o.subject_id)).filter(Boolean),
    [offerings, subjects],
  );
  const subjectName = subjects.find((s) => s.id === subjectId)?.name ?? "";
  const armName = arms.find((a) => a.id === armId)?.full_name ?? "";

  const canComment = useCanComment();
  const generate = useGenerateLessonPlan();

  const cellReady = !!term && !!armId && !!subjectId && topic.trim().length > 0;
  // Auto-load an existing plan for the current cell so regenerating is one click.
  const { data: savedPlan, isLoading: planLoading } = useLessonPlan(
    subjectId || null,
    armId || null,
    term?.id ?? null,
    cellReady ? topic.trim() : null,
  );
  const planExists = !!savedPlan;

  const handleGenerate = () => {
    if (!term) return;
    generate.mutate({
      term_id: term.id,
      subject_id: subjectId,
      class_arm_id: armId,
      topic: topic.trim(),
      periods,
    });
  };

  const plan = savedPlan?.plan;

  if (!aiEnabled) {
    return (
      <div className="space-y-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Lesson plans</h1>
            <p className="text-sm text-muted-foreground">
              AI-generated lesson plans composed from your school&apos;s own subject, class and term —
              each generation is metered, exactly like result remarks.
            </p>
          </div>
        </div>
        <PremiumLock />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Lesson plans</h1>
          <p className="text-sm text-muted-foreground">
            AI-generated lesson plans composed from your school&apos;s own subject, class and term —
            each generation is metered, exactly like result remarks.
          </p>
        </div>
      </div>

      {/* Term + class + subject + topic controls */}
      <div className="flex flex-wrap items-end gap-4">
        {terms.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm text-muted-foreground">Term</span>
            {terms.map((t) => (
              <button
                key={t.id}
                onClick={() => setActiveTermId(t.id)}
                className={cn(
                  "rounded-md border px-3 py-1.5 text-sm font-medium transition-colors",
                  t.id === term?.id
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-input text-muted-foreground hover:bg-accent",
                )}
              >
                {t.name}
              </button>
            ))}
          </div>
        )}
        <div className="space-y-1">
          <Label htmlFor="class">Class</Label>
          <select
            id="class"
            className="h-9 w-48 rounded-md border border-input bg-transparent px-3 text-sm"
            value={armId}
            onChange={(e) => {
              setArmId(e.target.value);
              setSubjectId("");
            }}
          >
            <option value="">Choose class…</option>
            {arms.map((a) => (
              <option key={a.id} value={a.id}>
                {a.full_name}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1">
          <Label htmlFor="subject">Subject</Label>
          <select
            id="subject"
            className="h-9 w-52 rounded-md border border-input bg-transparent px-3 text-sm"
            value={subjectId}
            onChange={(e) => setSubjectId(e.target.value)}
            disabled={!armId}
          >
            <option value="">{armId ? "Choose subject…" : "Pick a class first"}</option>
            {offered.map((s) => (
              <option key={s!.id} value={s!.id}>
                {s!.name}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1">
          <Label htmlFor="topic">Topic</Label>
          <input
            id="topic"
            className="h-9 w-64 rounded-md border border-input bg-transparent px-3 text-sm"
            placeholder="e.g. Linear Equations"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="periods">Periods</Label>
          <input
            id="periods"
            type="number"
            min={1}
            max={10}
            className="h-9 w-20 rounded-md border border-input bg-transparent px-3 text-sm"
            value={periods}
            onChange={(e) => setPeriods(Number(e.target.value) || 1)}
          />
        </div>
        {canComment && (
          <Button onClick={handleGenerate} disabled={!cellReady || generate.isPending}>
            <Sparkles className="h-4 w-4" />
            {generate.isPending
              ? "Generating…"
              : planExists
                ? "Regenerate plan"
                : "Generate plan"}
          </Button>
        )}
      </div>

      {!canComment && cellReady && (
        <p className="text-sm text-muted-foreground">
          Your role can view lesson plans but not generate them.
        </p>
      )}

      {/* The plan */}
      {planLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : !plan ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            {cellReady
              ? "No plan for this cell yet — generate one above."
              : "Pick a term, class, subject and topic to draft a lesson plan."}
          </CardContent>
        </Card>
      ) : (
        <div className="mx-auto max-w-3xl">
          <Card>
            <CardHeader>
              <CardTitle>{plan.title}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-5">
              {/* Overview */}
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <Badge variant="muted">{plan.periods} period{plan.periods === 1 ? "" : "s"}</Badge>
                <Badge variant="muted">{plan.duration_minutes} min</Badge>
                <Badge variant="muted">{plan.subject}</Badge>
                <Badge variant="muted">{plan.class_level}</Badge>
                {school && <span className="text-xs text-muted-foreground">{school.name}</span>}
              </div>

              {/* Objectives */}
              <div>
                <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Objectives
                </p>
                <ul className="list-inside list-disc space-y-1 text-sm">
                  {plan.objectives.map((o) => (
                    <li key={o}>{o}</li>
                  ))}
                </ul>
              </div>

              {/* Materials */}
              <div>
                <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Materials
                </p>
                <p className="text-sm">{plan.materials.join(" · ")}</p>
              </div>

              {/* Procedure */}
              <div>
                <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Procedure
                </p>
                <ol className="space-y-2">
                  {plan.procedure.map((step) => (
                    <li key={step.step} className="rounded-lg border px-3 py-2 text-sm">
                      <span className="font-medium">
                        {step.phase}
                        <span className="ml-2 text-xs font-normal text-muted-foreground">
                          {step.minutes} min
                        </span>
                      </span>
                      <p className="text-muted-foreground">{step.activity}</p>
                    </li>
                  ))}
                </ol>
              </div>

              <div>
                <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Homework
                </p>
                <p className="text-sm">{plan.homework}</p>
              </div>

              <div>
                <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Teacher note
                </p>
                <p className="text-sm text-muted-foreground">{plan.teacher_note}</p>
              </div>

              <p className="border-t pt-3 text-xs text-muted-foreground">
                AI-generated lesson plan · revision {savedPlan!.revision} · generated for {term?.name} ·{" "}
                {school?.name ?? "this school"}
              </p>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}