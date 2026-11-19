"use client";

import type { MyAssignment } from "@clearis/shared";
import { Download, Eye } from "lucide-react";
import { useMemo, useState } from "react";

import { useToast } from "@/components/toast";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Loader } from "@/components/ui/loader";
import { useMyAssignments, useScoreCard, useSessions, useTerms } from "@/hooks/use-api";
import { useStudentSort } from "@/hooks/use-student-sort";
import { downloadCsv, slug } from "@/lib/csv";
import { scoresheetRows } from "@/lib/exports";
import {
  assignedClasses,
  assignedSubjects,
  defaultTermId,
  isUnmarked,
  markText,
  sheetProgress,
} from "@/lib/scoresheet-view";

/**
 * The marks a teacher has entered, read back.
 *
 * Entering scores and checking them are different jobs: the entry grid is a form
 * that saves on a button, and a teacher who wants to know whether last night's
 * marks actually landed — or what a child's CA came to — should not have to open
 * that form and read it carefully to be sure nothing is an unsaved edit. This
 * page shows the saved record and nothing else: no inputs, no Save, so what is
 * on screen is what is in the database.
 *
 * The teacher picks a class and sees every subject they teach there, for one
 * term, one grid each. The API serves a grid only to the teacher assigned to it,
 * so the classes offered here are the teacher's own assignments rather than the
 * school's whole list of arms.
 */
export default function ViewScoresheetPage() {
  const { data: sessions = [] } = useSessions();
  const currentSession = sessions.find((s) => s.is_current) ?? sessions[0];
  const { data: terms = [], isLoading: loadingTerms } = useTerms(currentSession?.id ?? null);
  const { data: myAssignments = [], isLoading: loadingAssignments } = useMyAssignments();

  const [chosenTermId, setChosenTermId] = useState("");
  const [armId, setArmId] = useState("");

  // Default to the term open for entry — the one the teacher is working in —
  // unless they pick another to look back at a finished one.
  const termId = chosenTermId || defaultTermId(terms);

  const classes = useMemo(() => assignedClasses(myAssignments), [myAssignments]);
  const subjects = useMemo(() => assignedSubjects(myAssignments, armId), [myAssignments, armId]);
  const selectedClass = classes.find((c) => c.arm_id === armId);
  const selectedTerm = terms.find((t) => t.id === termId);

  const context = (
    <div className="grid gap-4 sm:grid-cols-2">
      <div className="space-y-2">
        <label htmlFor="scoresheet-term" className="text-sm font-medium">
          Term
        </label>
        <select
          id="scoresheet-term"
          className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
          value={termId}
          onChange={(e) => setChosenTermId(e.target.value)}
          disabled={loadingTerms}
        >
          {terms.length === 0 && <option value="">No terms this session</option>}
          {terms.map((term) => (
            <option key={term.id} value={term.id}>
              {term.name}
              {term.status === "closed" ? " (closed)" : term.status === "open" ? "" : " (not activated)"}
            </option>
          ))}
        </select>
      </div>
      <div className="space-y-2">
        <label htmlFor="scoresheet-class" className="text-sm font-medium">
          Class
        </label>
        <select
          id="scoresheet-class"
          className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
          value={armId}
          onChange={(e) => setArmId(e.target.value)}
          disabled={loadingAssignments || classes.length === 0}
        >
          <option value="">
            {classes.length === 0 ? "No classes assigned to you" : "Choose class..."}
          </option>
          {classes.map((cls) => (
            <option key={cls.arm_id} value={cls.arm_id}>
              {cls.arm_name}
            </option>
          ))}
        </select>
      </div>
    </div>
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">View Scoresheet</h1>
        <p className="text-sm text-muted-foreground">
          The marks you have entered, as they are saved. Choose a class to see the subjects you
          teach there.
        </p>
      </div>

      <div className="flex items-center gap-3 rounded-xl border border-border/80 bg-muted/60 px-4 py-3 text-[13px] text-muted-foreground">
        <Eye className="h-4 w-4 shrink-0" />
        <span>
          This page only reads. To change a mark, open <strong>Enter Scores</strong> for that class
          and subject.
        </span>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Choose a class</CardTitle>
          <CardDescription>Pick the term and the class whose marks you want to see.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">{context}</CardContent>
      </Card>

      {!armId && (
        <Card>
          <CardContent className="flex flex-col items-center gap-2 py-12 text-center text-muted-foreground">
            {loadingAssignments ? (
              <Loader />
            ) : classes.length === 0 ? (
              <>
                <p>You have no classes assigned for this session.</p>
                <p className="text-[13px]">
                  A school admin assigns subjects to teachers — ask them to assign you a class and
                  subject, and it will appear here.
                </p>
              </>
            ) : (
              <p>Choose a class above to see the scores you have entered.</p>
            )}
          </CardContent>
        </Card>
      )}

      {armId && termId && (
        <div className="space-y-5">
          <div className="flex items-baseline gap-2">
            <h2 className="text-lg font-semibold tracking-tight">{selectedClass?.arm_name}</h2>
            <p className="text-sm text-muted-foreground">{selectedTerm?.name}</p>
          </div>
          {subjects.map((assignment) => (
            <SubjectSheet
              key={assignment.subject_id}
              assignment={assignment}
              armId={armId}
              termId={termId}
              armName={selectedClass?.arm_name ?? ""}
              termName={selectedTerm?.name ?? ""}
            />
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * One subject's grid for the chosen class, read-only.
 *
 * The values are the ones the API returns — including the total and the grade it
 * computed — so the screen never disagrees with the record a report card is
 * built from.
 */
function SubjectSheet({
  assignment,
  armId,
  termId,
  armName,
  termName,
}: {
  assignment: MyAssignment;
  armId: string;
  termId: string;
  armName: string;
  termName: string;
}) {
  const { toast } = useToast();
  const [sort] = useStudentSort();
  const { data: card, isLoading, error } = useScoreCard(armId, assignment.subject_id, termId, sort);

  if (isLoading) {
    return (
      <Card>
        <CardContent className="flex justify-center py-10">
          <Loader />
        </CardContent>
      </Card>
    );
  }

  if (error || !card) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{assignment.subject_name}</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          {error instanceof Error
            ? error.message
            : "This scoresheet could not be opened. Check with your school admin that you are assigned to this subject."}
        </CardContent>
      </Card>
    );
  }

  const progress = sheetProgress(card);
  const noComponents = card.components.length === 0;

  const download = () => {
    downloadCsv(
      `scoresheet-${slug(armName)}-${slug(card.subject.name)}-${slug(termName)}.csv`,
      scoresheetRows(
        card,
        (enrollmentId, componentId) => {
          const row = card.students.find((s) => s.enrollment_id === enrollmentId);
          return markText(row?.scores[componentId]);
        },
        (enrollmentId) => card.students.find((s) => s.enrollment_id === enrollmentId)?.total ?? null,
        (enrollmentId) =>
          card.students.find((s) => s.enrollment_id === enrollmentId)?.grade_letter ?? null,
      ),
    );
    toast("Scoresheet downloaded");
  };

  return (
    <Card className="overflow-hidden">
      <CardHeader className="flex-row items-start justify-between gap-3 space-y-0">
        <div>
          <CardTitle>{card.subject.name}</CardTitle>
          <CardDescription className="mt-1">
            {noComponents ? (
              "Your school has not set up its assessment structure for this term yet."
            ) : isUnmarked(progress) ? (
              "Nothing entered for this class yet."
            ) : progress.complete === progress.pupils ? (
              `Every mark entered — ${progress.pupils} pupil${progress.pupils === 1 ? "" : "s"}.`
            ) : (
              `${progress.scored} of ${progress.pupils} pupils marked, ${progress.complete} complete.`
            )}
          </CardDescription>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <ProgressBadge progress={progress} noComponents={noComponents} />
          <Button
            variant="outline"
            onClick={download}
            disabled={card.students.length === 0}
            title="Download these marks as a spreadsheet"
          >
            <Download className="h-4 w-4" />
            Spreadsheet
          </Button>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <div className="overflow-x-auto scrollbar-thin">
          <table className="w-full text-sm">
            <thead className="bg-muted/70">
              <tr>
                <th className="sticky left-0 bg-muted/70 px-3 py-2 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Student
                </th>
                {card.components.map((component) => (
                  <th
                    key={component.id}
                    className="px-3 py-2 text-center text-xs font-medium text-muted-foreground"
                  >
                    {component.name}
                    <span className="block font-normal text-[10px] text-muted-foreground/90">
                      /{component.max_score} · {component.weight}%
                    </span>
                  </th>
                ))}
                <th className="px-3 py-2 text-center text-xs font-medium text-muted-foreground">Total</th>
                <th className="px-3 py-2 text-center text-xs font-medium text-muted-foreground">Grade</th>
              </tr>
            </thead>
            <tbody>
              {card.students.length === 0 && (
                <tr className="border-t">
                  <td colSpan={card.components.length + 3} className="px-3 py-8 text-center text-muted-foreground">
                    No pupils are enrolled in this class.
                  </td>
                </tr>
              )}
              {card.students.map((row) => (
                <tr key={row.enrollment_id} className="border-t">
                  <td className="sticky left-0 bg-background px-3 py-2">
                    <p className="font-medium">{row.full_name}</p>
                    <p className="font-mono text-[10px] text-muted-foreground">{row.admission_no}</p>
                  </td>
                  {card.components.map((component) => (
                    <td
                      key={component.id}
                      className="px-3 py-2 text-center tabular-nums text-muted-foreground"
                    >
                      {markText(row.scores[component.id]) || "—"}
                    </td>
                  ))}
                  <td className="px-3 py-2 text-center font-semibold tabular-nums">
                    {row.total === null || row.total === undefined ? "—" : row.total}
                  </td>
                  <td className="px-3 py-2 text-center">
                    {row.grade_letter ? (
                      <Badge variant="default">{row.grade_letter}</Badge>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

function ProgressBadge({
  progress,
  noComponents,
}: {
  progress: { pupils: number; scored: number; complete: number };
  noComponents: boolean;
}) {
  if (noComponents) return <Badge variant="outline">No components</Badge>;
  if (isUnmarked(progress)) return <Badge variant="outline">Not started</Badge>;
  if (progress.pupils > 0 && progress.complete === progress.pupils) {
    return <Badge variant="success">Complete</Badge>;
  }
  return <Badge variant="warning">In progress</Badge>;
}
