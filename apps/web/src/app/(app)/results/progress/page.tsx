"use client";

import { ArrowDownRight, ArrowRight, ArrowUpRight, Minus, TrendingUp } from "lucide-react";
import { useMemo, useState } from "react";

import { PremiumLock } from "@/components/premium-lock";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Loader } from "@/components/ui/loader";
import { useArms, useMyAssignments, useProgress, useSessions } from "@/hooks/use-api";
import {
  deltaLabel,
  seriesFor,
  sparklinePoints,
  trendLabel,
  trendTone,
  type ProgressPayload,
  type StudentProgress,
  type SubjectProgress,
  type Trend,
} from "@/lib/progress";
import { useAuth } from "@/providers/auth-provider";
import { cn } from "@/lib/utils";

/**
 * Student Progress Tracking — a premium feature.
 *
 * The marks sheet says what a child scored; this says whether they are getting
 * better, by comparing each pupil with **their own** earlier work and never with
 * the class. The API decides the direction (two or more observations, a two-point
 * band, terms preferred over components); this page only has to show it honestly,
 * including saying "needs another mark" where there is nothing to compare.
 */

/** The same rule the API applies, restated for the reader. */
const LEGEND = "A move of 2 points or more counts as improving or falling.";

function trendIcon(tone: ReturnType<typeof trendTone>) {
  if (tone === "up") return ArrowUpRight;
  if (tone === "down") return ArrowDownRight;
  if (tone === "flat") return Minus;
  return ArrowRight;
}

function toneClass(tone: ReturnType<typeof trendTone>): string {
  if (tone === "up") return "text-emerald-600 dark:text-emerald-400";
  if (tone === "down") return "text-rose-600 dark:text-rose-400";
  if (tone === "flat") return "text-muted-foreground";
  return "text-muted-foreground/50";
}

function TrendBadge({ trend, compact = false }: { trend: Trend; compact?: boolean }) {
  const tone = trendTone(trend);
  const Icon = trendIcon(tone);
  return (
    <span
      className={cn("inline-flex items-center gap-1 font-semibold", toneClass(tone))}
      title={`${trendLabel(trend)}${trend.delta === null ? "" : ` (${deltaLabel(trend)} points)`} · ${LEGEND}`}
    >
      <Icon className={compact ? "h-3.5 w-3.5" : "h-4 w-4"} />
      {!compact && <span className="text-[12.5px]">{trendLabel(trend)}</span>}
      {trend.delta !== null && (
        <span className="text-[11px] font-medium tabular-nums opacity-80">{deltaLabel(trend)}</span>
      )}
    </span>
  );
}

function Sparkline({ values }: { values: number[] }) {
  if (values.length < 2) return null;
  return (
    <svg viewBox="0 0 72 24" className="h-6 w-[72px] overflow-visible" aria-hidden>
      <polyline
        points={sparklinePoints(values)}
        fill="none"
        stroke="currentColor"
        strokeWidth={1.75}
        strokeLinecap="round"
        strokeLinejoin="round"
        className="text-primary/70"
      />
    </svg>
  );
}

function SubjectCell({ subject }: { subject: SubjectProgress }) {
  const basis = subject.trend.basis === "components" ? "in this term" : "across terms";
  return (
    <div className="flex flex-col items-center gap-1">
      <span className="text-[13px] font-semibold tabular-nums text-foreground">
        {subject.latest === null ? "—" : `${Math.round(subject.latest * 10) / 10}%`}
      </span>
      <TrendBadge trend={subject.trend} compact />
      <span className="text-[9.5px] uppercase tracking-wide text-muted-foreground/70">{basis}</span>
    </div>
  );
}

function ProgressTable({ data }: { data: ProgressPayload }) {
  const subjects = data.subjects.filter((subject) =>
    data.students.some((student) => student.subjects.some((row) => row.subject_id === subject.id)),
  );

  return (
    <Card className="overflow-hidden">
      <div className="overflow-x-auto scrollbar-thin">
        <table className="w-full text-sm">
          <thead className="bg-muted/60">
            <tr>
              <th className="sticky left-0 z-10 bg-muted/60 px-3 py-2.5 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Pupil
              </th>
              {subjects.map((subject) => (
                <th
                  key={subject.id}
                  className="min-w-[104px] px-3 py-2.5 text-center text-xs font-medium text-muted-foreground"
                >
                  <span className="inline-flex items-center gap-1">
                    {subject.name}
                    {subject.is_core && <span className="h-1.5 w-1.5 rounded-full bg-primary" title="Core subject" />}
                  </span>
                </th>
              ))}
              <th className="px-3 py-2.5 text-center text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Overall
              </th>
            </tr>
          </thead>
          <tbody>
            {data.students.map((student) => (
              <StudentRow key={student.student_id} student={student} subjects={subjects} />
            ))}
            {data.students.length === 0 && (
              <tr className="border-t">
                <td colSpan={subjects.length + 2} className="px-3 py-10 text-center text-muted-foreground">
                  No pupils are enrolled in this class.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function StudentRow({
  student,
  subjects,
}: {
  student: StudentProgress;
  subjects: { id: string; name: string }[];
}) {
  const bySubject = new Map(student.subjects.map((row) => [row.subject_id, row]));
  return (
    <tr className="border-t align-top">
      <td className="sticky left-0 z-10 bg-background px-3 py-2">
        <p className="font-medium">{student.full_name}</p>
        <p className="font-mono text-[10px] text-muted-foreground">{student.admission_no}</p>
      </td>
      {subjects.map((subject) => {
        const row = bySubject.get(subject.id);
        return (
          <td key={subject.id} className="px-2 py-2 text-center">
            {row ? <SubjectCell subject={row} /> : <span className="text-muted-foreground/40">—</span>}
          </td>
        );
      })}
      <td className="px-3 py-2">
        <div className="flex flex-col items-center gap-1">
          <Sparkline values={student.overall.series.map((point) => point.value)} />
          <span className="inline-flex items-center gap-1">
            <TrendBadge trend={student.overall.trend} compact />
          </span>
        </div>
      </td>
    </tr>
  );
}

export default function ProgressPage() {
  const { activeSchool } = useAuth();
  const { data: sessions = [] } = useSessions();
  const currentSession = sessions.find((session) => session.is_current) ?? sessions[0];
  const { data: arms = [] } = useArms(currentSession?.id ?? null);
  const { data: myAssignments = [] } = useMyAssignments();

  const isTeacher =
    activeSchool?.role?.code === "teacher" || activeSchool?.role?.code === "homeroom_teacher";
  const visibleArms = isTeacher
    ? arms.filter((arm) => myAssignments.some((item) => item.arm_id === arm.id))
    : arms;

  const [armId, setArmId] = useState("");
  const { data, isLoading, error } = useProgress(armId || null, currentSession?.id ?? null);

  const premiumRefusal = (error as { status?: number } | null)?.status === 403;
  const selectedArm = useMemo(() => arms.find((arm) => arm.id === armId), [arms, armId]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
          Progress Tracking
          <Badge variant="warning">Premium</Badge>
        </h1>
        <p className="text-sm text-muted-foreground">
          Whether each pupil is improving in each subject — measured against their own earlier
          marks, never against the class.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Choose a class</CardTitle>
          <CardDescription>
            Pick the class whose progress you want to read. {LEGEND}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="max-w-sm space-y-2">
            <label htmlFor="progress-class" className="text-sm font-medium">
              Class
            </label>
            <select
              id="progress-class"
              className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
              value={armId}
              onChange={(event) => setArmId(event.target.value)}
              disabled={visibleArms.length === 0}
            >
              <option value="">
                {visibleArms.length === 0 ? "No classes available" : "Choose class..."}
              </option>
              {visibleArms.map((arm) => (
                <option key={arm.id} value={arm.id}>
                  {arm.full_name}
                </option>
              ))}
            </select>
          </div>
        </CardContent>
      </Card>

      {premiumRefusal && (
        <PremiumLock
          title="Student progress tracking is a premium feature"
          description="This plan tracks every pupil against their own earlier marks and shows who is improving, who is slipping and who needs another mark before it can say. Ask Clearis to enable it for your school and it turns on immediately."
        />
      )}

      {error && !premiumRefusal && (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            {error instanceof Error ? error.message : "Progress could not be loaded."}
          </CardContent>
        </Card>
      )}

      {isLoading && armId && (
        <div className="flex justify-center py-16">
          <Loader />
        </div>
      )}

      {data && armId && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-baseline gap-2">
            <h2 className="text-lg font-semibold tracking-tight">{selectedArm?.full_name ?? data.arm.full_name}</h2>
            <p className="text-sm text-muted-foreground">{data.session.name}</p>
          </div>

          {!data.core_configured && (
            <div className="rounded-xl border border-border/70 bg-muted/50 px-4 py-3 text-[13px] text-muted-foreground">
              No subjects are flagged as core, so the whole curriculum is tracked. Flag a subject as
              core in <strong>Subjects</strong> to narrow this view to the ones that matter most.
            </div>
          )}

          {data.students.length === 0 ? (
            <Card>
              <CardContent className="py-12 text-center text-muted-foreground">
                No pupils are enrolled in this class.
              </CardContent>
            </Card>
          ) : data.students.every((student) => student.subjects.length === 0) ? (
            <Card>
              <CardContent className="py-12 text-center text-muted-foreground">
                No marks have been entered for this class yet. Progress appears as soon as a first
                assessment is recorded.
              </CardContent>
            </Card>
          ) : (
            <ProgressTable data={data} />
          )}

          <p className="text-[12px] leading-relaxed text-muted-foreground/80">
            Improving or falling means the latest move is 2 points or more. Where a subject has only
            one term of marks, the trend is read from that term&apos;s assessment components
            (1st CA → 2nd CA → Exam). Marks are read at any stage, so a term still in draft is
            marked <strong>as it stands</strong>, not as final.
          </p>
        </div>
      )}

      {!armId && !premiumRefusal && (
        <Card>
          <CardContent className="flex flex-col items-center gap-2 py-14 text-center text-muted-foreground">
            <TrendingUp className="h-5 w-5 text-primary/70" />
            <p>Choose a class to see who is improving.</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}