"use client";

// Best in Subjects — the school's honours list. For each class arm it shows who
// holds the top score in every subject, term by term, and who leads each subject
// across the whole session (the mean of their published term totals).
//
// Results are read through the report-card permission because this is the exam
// office's leadership view of published results; the API enforces the same code.

import { useState } from "react";

import { NoAccess } from "@/components/access-denied";
import { REPORT_CARD_PERM } from "@/components/nav-config";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  useArms,
  useBestInSubjectsBreakdown,
  useSessions,
} from "@/hooks/use-api";
import { useAuth } from "@/providers/auth-provider";

export default function BestInSubjectsPage() {
  const { activeSchool } = useAuth();
  if (!(activeSchool?.permissions ?? []).includes(REPORT_CARD_PERM)) {
    return (
      <NoAccess
        title="Report cards are the Exam Office's desk"
        message="Only the Exam Officer and school leadership can open the best-in-subject report. You can still enter and review your own scoresheets from Results."
        backHref="/results"
        backLabel="Go to Results"
      />
    );
  }
  return <BestInSubjectsWorkspace />;
}

/** A winner's name(s) plus the mark that won it. */
function Leaders({ names, value }: { names: string[]; value: number }) {
  return (
    <div className="space-y-0.5">
      <p className="font-medium">{names.join(" & ")}</p>
      <p className="text-[11px] text-muted-foreground/75">{value}</p>
    </div>
  );
}

function BestInSubjectsWorkspace() {
  const { data: sessions = [] } = useSessions();
  const [sessionId, setSessionId] = useState("");
  const session =
    sessions.find((s) => s.id === sessionId) ??
    sessions.find((s) => s.is_current) ??
    sessions[0];

  const { data: arms = [] } = useArms(session?.id ?? null);
  const [armChoice, setArmChoice] = useState("");
  const arm = arms.find((a) => a.id === armChoice) ?? arms[0];

  const { data, isLoading, error } = useBestInSubjectsBreakdown(
    arm?.id ?? null,
    session?.id ?? null,
  );

  const terms = data?.terms ?? [];
  const subjects = data?.session_subjects ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Best in Subjects</h1>
        <p className="text-sm text-muted-foreground/75">
          Who topped each subject in every term, and across the session. Ties are
          shown together. Only published results count.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Choose session and class</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <label className="space-y-1.5 text-[13px] font-medium">
            <span>Session</span>
            <select
              className="h-9 w-full rounded-md border bg-background px-3 text-sm"
              value={session?.id ?? ""}
              onChange={(e) => {
                setSessionId(e.target.value);
                setArmChoice("");
              }}
            >
              {sessions.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
          <label className="space-y-1.5 text-[13px] font-medium">
            <span>Class</span>
            <select
              className="h-9 w-full rounded-md border bg-background px-3 text-sm"
              value={arm?.id ?? ""}
              onChange={(e) => setArmChoice(e.target.value)}
            >
              {arms.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.full_name}
                </option>
              ))}
            </select>
          </label>
        </CardContent>
      </Card>

      {!session || !arm ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground/75">
            {sessions.length === 0
              ? "Create an academic session and class first."
              : "Pick a class to see its subject leaders."}
          </CardContent>
        </Card>
      ) : isLoading ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground/75">
            Loading subject leaders…
          </CardContent>
        </Card>
      ) : error ? (
        <Card>
          <CardContent className="py-12 text-center text-destructive">
            Could not load the best-in-subject report.
          </CardContent>
        </Card>
      ) : subjects.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground/75">
            No published results for this class in this session yet. Publish a
            term&apos;s results and the leaders appear here.
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>
              {data?.arm.full_name} · {data?.session.name}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left align-bottom">
                    <th className="p-2">Subject</th>
                    {terms.map((term) => (
                      <th key={term.term_id} className="p-2">
                        {term.term_name}
                      </th>
                    ))}
                    <th className="p-2">Session</th>
                  </tr>
                </thead>
                <tbody>
                  {subjects.map((subject) => (
                    <tr key={subject.subject_id} className="border-b align-top">
                      <td className="p-2 font-medium">{subject.subject_name}</td>
                      {terms.map((term) => {
                        const row = term.subjects.find(
                          (item) => item.subject_id === subject.subject_id,
                        );
                        return (
                          <td key={term.term_id} className="p-2">
                            {row ? (
                              <Leaders names={row.leaders} value={row.top_score} />
                            ) : (
                              <span className="text-muted-foreground/60">—</span>
                            )}
                          </td>
                        );
                      })}
                      <td className="p-2">
                        <Leaders
                          names={subject.leaders}
                          value={subject.top_average}
                        />
                        <p className="mt-0.5 text-[11px] text-muted-foreground/60">
                          {subject.term_count} term
                          {subject.term_count === 1 ? "" : "s"} averaged
                        </p>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-4 text-[12px] text-muted-foreground/70">
              A term cell is the top published total in that subject. The session
              cell is the highest mean of a student&apos;s published term totals,
              so a term with no published result neither helps nor penalises
              anyone.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
