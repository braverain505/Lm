"use client";

import { CheckCircle2, Sparkles } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useCanComment, useArms, useGenerateQuestionBank, useOfferings, useQuestionBank, useSchoolMe, useSessions, useSubjects, useTerms } from "@/hooks/use-api";
import { cn } from "@/lib/utils";
import { PremiumLock, useAiEnabled } from "@/components/premium-lock";

export default function QuestionBanksPage() {
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
  const [count, setCount] = useState(5);

  const { data: offerings = [] } = useOfferings(armId || null);
  const offered = useMemo(
    () => offerings.map((o) => subjects.find((s) => s.id === o.subject_id)).filter(Boolean),
    [offerings, subjects],
  );

  const canComment = useCanComment();
  const generate = useGenerateQuestionBank();

  const cellReady = !!term && !!armId && !!subjectId && topic.trim().length > 0;
  // Auto-load an existing bank for the current cell so regenerating is one click.
  const { data: saved, isLoading: bankLoading } = useQuestionBank(
    subjectId || null,
    armId || null,
    term?.id ?? null,
    cellReady ? topic.trim() : null,
  );
  const bankExists = !!saved;

  const handleGenerate = () => {
    if (!term) return;
    generate.mutate({
      term_id: term.id,
      subject_id: subjectId,
      class_arm_id: armId,
      topic: topic.trim(),
      count,
    });
  };

  const bank = saved?.bank;

  if (!aiEnabled) {
    return (
      <div className="space-y-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Question bank</h1>
            <p className="text-sm text-muted-foreground">
              AI-generated practice questions composed from your school&apos;s own subject, class and term —
              every bank is marked with answers and metered, exactly like lesson plans and remarks.
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
          <h1 className="text-2xl font-semibold tracking-tight">Question bank</h1>
          <p className="text-sm text-muted-foreground">
            AI-generated practice questions composed from your school&apos;s own subject, class and term —
            every bank is marked with answers and metered, exactly like lesson plans and remarks.
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
          <Label htmlFor="count">Questions</Label>
          <input
            id="count"
            type="number"
            min={1}
            max={10}
            className="h-9 w-20 rounded-md border border-input bg-transparent px-3 text-sm"
            value={count}
            onChange={(e) => setCount(Number(e.target.value) || 5)}
          />
        </div>
        {canComment && (
          <Button onClick={handleGenerate} disabled={!cellReady || generate.isPending}>
            <Sparkles className="h-4 w-4" />
            {generate.isPending
              ? "Generating…"
              : bankExists
                ? "Regenerate bank"
                : "Generate bank"}
          </Button>
        )}
      </div>

      {!canComment && cellReady && (
        <p className="text-sm text-muted-foreground">
          Your role can view question banks but not generate them.
        </p>
      )}

      {/* The bank */}
      {bankLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : !bank ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            {cellReady
              ? "No bank for this cell yet — generate one above."
              : "Pick a term, class, subject and topic to draft practice questions."}
          </CardContent>
        </Card>
      ) : (
        <div className="mx-auto max-w-3xl space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>{bank.title}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-5">
              {/* Overview */}
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <Badge variant="muted">{bank.count} questions</Badge>
                <Badge variant="muted">{bank.subject}</Badge>
                <Badge variant="muted">{bank.class_level}</Badge>
                {school && <span className="text-xs text-muted-foreground">{school.name}</span>}
              </div>

              {/* Questions */}
              <div className="space-y-4">
                {bank.questions.map((q) => (
                  <div key={q.n} className="rounded-lg border p-4">
                    <p className="text-sm font-medium">
                      <span className="mr-2 text-xs font-normal text-muted-foreground">
                        Q{q.n}
                      </span>
                      {q.stem}
                    </p>
                    <ul className="mt-3 space-y-1.5">
                      {q.options.map((opt, i) => {
                        const isAnswer = i === q.answer;
                        return (
                          <li
                            key={i}
                            className={cn(
                              "flex items-start gap-2 rounded-md px-2.5 py-1.5 text-sm",
                              isAnswer
                                ? "bg-primary/10 font-medium text-primary"
                                : "text-muted-foreground",
                            )}
                          >
                            <span className="w-5 shrink-0 text-xs">
                              {String.fromCharCode(65 + i)}.
                            </span>
                            <span>{opt}</span>
                            {isAnswer && (
                              <CheckCircle2 className="ml-auto h-4 w-4 shrink-0 self-center" />
                            )}
                          </li>
                        );
                      })}
                    </ul>
                    <p className="mt-2 text-xs text-muted-foreground">{q.rationale}</p>
                  </div>
                ))}
              </div>

              <p className="border-t pt-3 text-xs text-muted-foreground">
                AI-generated question bank · revision {saved!.revision} · generated for {term?.name} ·{" "}
                {school?.name ?? "this school"}
              </p>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}