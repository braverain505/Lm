"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@clearis/shared";
import { useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { NoAccess } from "@/components/access-denied";
import { REPORT_CARD_PERM } from "@/components/nav-config";
import { useActiveSchoolId, useSessions, useStudents } from "@/hooks/use-api";
import { useAuth } from "@/providers/auth-provider";

type Cumulative = {
  session: { id: string; name: string };
  subjects: { subject_id: string; subject_name: string; average: number | null; terms: { term_name: string; total: number | null }[] }[];
};

export default function CumulativeReportPage() {
  const { activeSchool } = useAuth();
  if (!(activeSchool?.permissions ?? []).includes(REPORT_CARD_PERM)) {
    return (
      <NoAccess
        title="Report cards are the Exam Office's desk"
        message="Only the Exam Officer and school leadership can open cumulative reports. You can still review your own scoresheets from Results."
        backHref="/results"
        backLabel="Go to Results"
      />
    );
  }
  return <CumulativeReportWorkspace />;
}

function CumulativeReportWorkspace() {
  const schoolId = useActiveSchoolId();
  const { data: sessions = [] } = useSessions();
  const { data: students = [] } = useStudents();
  const [studentId, setStudentId] = useState("");
  const [sessionId, setSessionId] = useState("");
  const { data, isLoading, error } = useQuery({
    queryKey: ["cumulative", schoolId, studentId, sessionId],
    enabled: !!schoolId && !!studentId && !!sessionId,
    queryFn: () => api.schoolFetch<Cumulative>(schoolId!, `/results/cumulative?student_id=${studentId}&session_id=${sessionId}`),
  });

  return (
    <div className="space-y-6">
      <div><h1 className="text-2xl font-semibold">Cumulative Broadsheet</h1><p className="text-sm text-muted-foreground">Review published subject averages across an academic session.</p></div>
      <Card><CardHeader><CardTitle>Choose student and session</CardTitle></CardHeader><CardContent className="grid gap-4 sm:grid-cols-2">
        <select className="h-9 rounded-md border px-3 text-sm" value={studentId} onChange={(event) => setStudentId(event.target.value)}><option value="">Choose student...</option>{students.map((student) => <option key={student.id} value={student.id}>{student.full_name} · {student.admission_no}</option>)}</select>
        <select className="h-9 rounded-md border px-3 text-sm" value={sessionId} onChange={(event) => setSessionId(event.target.value)}><option value="">Choose session...</option>{sessions.map((session) => <option key={session.id} value={session.id}>{session.name}</option>)}</select>
      </CardContent></Card>
      {isLoading && <p className="text-sm text-muted-foreground">Loading cumulative results...</p>}
      {error && <p className="text-sm text-destructive">Could not load cumulative results.</p>}
      {data && <Card><CardHeader><CardTitle>{data.session.name}</CardTitle></CardHeader><CardContent><div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="border-b text-left"><th className="p-2">Subject</th>{data.subjects[0]?.terms.map((term) => <th key={term.term_name} className="p-2 text-right">{term.term_name}</th>)}<th className="p-2 text-right">Average</th></tr></thead><tbody>{data.subjects.map((subject) => <tr key={subject.subject_id} className="border-b"><td className="p-2 font-medium">{subject.subject_name}</td>{subject.terms.map((term) => <td key={term.term_name} className="p-2 text-right">{term.total ?? "-"}</td>)}<td className="p-2 text-right font-semibold">{subject.average ?? "-"}</td></tr>)}</tbody></table></div></CardContent></Card>}
    </div>
  );
}