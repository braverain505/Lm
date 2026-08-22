"use client";

import { useQuery } from "@tanstack/react-query";
import { api, type ReportCard } from "@schoolos/shared";
import { Printer } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useActiveSchoolId, useArms, useSessions, useTerms } from "@/hooks/use-api";

export default function BroadsheetPage() {
  const schoolId = useActiveSchoolId();
  const { data: sessions = [] } = useSessions();
  const session = sessions.find((item) => item.is_current) ?? sessions[0];
  const { data: terms = [] } = useTerms(session?.id ?? null);
  const { data: arms = [] } = useArms(session?.id ?? null);
  const [termId, setTermId] = useState("");
  const [armId, setArmId] = useState("");
  const { data: cards = [], isLoading, error } = useQuery({
    queryKey: ["broadsheet", schoolId, armId, termId],
    enabled: !!schoolId && !!armId && !!termId,
    queryFn: () => api.schoolFetch<ReportCard[]>(schoolId!, `/results/broadsheet?arm_id=${armId}&term_id=${termId}`),
  });
  const subjects = cards[0]?.subjects ?? [];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3"><div><h1 className="text-2xl font-semibold">Broadsheet</h1><p className="text-sm text-muted-foreground">Review published results for a whole class.</p></div><Button variant="outline" onClick={() => window.print()} disabled={!cards.length}><Printer className="h-4 w-4" /> Print</Button></div>
      <Card><CardHeader><CardTitle>Choose term and class</CardTitle></CardHeader><CardContent className="grid gap-4 sm:grid-cols-2"><select className="h-9 rounded-md border px-3 text-sm" value={termId} onChange={(event) => setTermId(event.target.value)}><option value="">Choose term...</option>{terms.map((term) => <option key={term.id} value={term.id}>{term.name}</option>)}</select><select className="h-9 rounded-md border px-3 text-sm" value={armId} onChange={(event) => setArmId(event.target.value)}><option value="">Choose class...</option>{arms.map((arm) => <option key={arm.id} value={arm.id}>{arm.full_name}</option>)}</select></CardContent></Card>
      {isLoading && <p className="text-sm text-muted-foreground">Loading broadsheet...</p>}
      {error && <p className="text-sm text-destructive">Could not load the broadsheet.</p>}
      {cards.length > 0 && <Card><CardHeader><CardTitle>{cards[0].class_arm.full_name} · {cards[0].term.name}</CardTitle></CardHeader><CardContent><div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="border-b text-left"><th className="p-2">Student</th>{subjects.map((subject) => <th key={subject.subject_id} className="p-2 text-right">{subject.subject_name}</th>)}<th className="p-2 text-right">Average</th></tr></thead><tbody>{cards.map((card) => <tr key={card.enrollment_id} className="border-b"><td className="p-2 font-medium">{card.student.full_name}</td>{subjects.map((subject) => { const current = card.subjects.find((item) => item.subject_id === subject.subject_id); return <td key={subject.subject_id} className="p-2 text-right">{current?.total ?? "-"}</td>; })}<td className="p-2 text-right font-semibold">{card.summary.average ?? "-"}</td></tr>)}</tbody></table></div></CardContent></Card>}
      {!isLoading && armId && termId && cards.length === 0 && <p className="text-sm text-muted-foreground">No published results are available for this class and term.</p>}
    </div>
  );
}