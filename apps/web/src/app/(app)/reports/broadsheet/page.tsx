"use client";

import { useQuery } from "@tanstack/react-query";
import { api, type ReportCard } from "@clearis/shared";
import { Download, Printer } from "lucide-react";
import { useMemo, useState } from "react";

import { downloadCsv, slug } from "@/lib/csv";
import { broadsheetRows, broadsheetSubjects } from "@/lib/exports";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { NoAccess } from "@/components/access-denied";
import { REPORT_CARD_PERM } from "@/components/nav-config";
import { useActiveSchoolId, useArms, useSessions, useTerms } from "@/hooks/use-api";
import { useAuth } from "@/providers/auth-provider";

export default function BroadsheetPage() {
  const { activeSchool } = useAuth();
  if (!(activeSchool?.permissions ?? []).includes(REPORT_CARD_PERM)) {
    return (
      <NoAccess
        title="The broadsheet is the Exam Office's desk"
        message="Only the Exam Officer and school leadership can open the class broadsheet. You can still review your own scoresheets from Results."
        backHref="/results"
        backLabel="Go to Results"
      />
    );
  }
  return <BroadsheetWorkspace />;
}

/** Where a sheet's subject set comes from: one class, or every class in a group. */
type Sheet = { kind: "arm" | "group"; value: string };

function BroadsheetWorkspace() {
  const schoolId = useActiveSchoolId();
  const { data: sessions = [] } = useSessions();
  const session = sessions.find((item) => item.is_current) ?? sessions[0];
  const { data: terms = [] } = useTerms(session?.id ?? null);
  const { data: arms = [] } = useArms(session?.id ?? null);
  const [termId, setTermId] = useState("");
  const [target, setTarget] = useState("");
  const [sheet, setSheet] = useState<Sheet | null>(null);

  /**
   * Groups first, then the classes inside them — the same list a school reads
   * off the printed sheet. A class in no group is offered on its own.
   */
  const groups = useMemo(
    () =>
      [...new Set(arms.map((arm) => arm.group_name).filter((g): g is string => !!g))].sort(
        (a, b) => a.localeCompare(b),
      ),
    [arms],
  );

  const { data: cards = [], isLoading, error } = useQuery({
    queryKey: ["broadsheet", schoolId, sheet?.kind ?? "", sheet?.value ?? "", termId],
    enabled: !!schoolId && !!sheet && !!termId,
    queryFn: () => {
      const query =
        sheet!.kind === "group"
          ? `group_name=${encodeURIComponent(sheet!.value)}&session_id=${session!.id}&term_id=${termId}`
          : `arm_id=${sheet!.value}&term_id=${termId}`;
      return api.schoolFetch<ReportCard[]>(schoolId!, `/results/broadsheet?${query}`);
    },
  });

  const subjects = useMemo(() => broadsheetSubjects(cards), [cards]);
  const title =
    sheet?.kind === "group" ? sheet.value : cards[0]?.class_arm.full_name ?? "";

  /**
   * The broadsheet as a spreadsheet, one row per student and one column per
   * subject, with each student's average on the end — the same grid the exam
   * office sees, ready for a moderation meeting or the school's own analysis.
   */
  const downloadSpreadsheet = () => {
    if (!cards.length) return;
    downloadCsv(
      `broadsheet-${slug(title)}-${slug(cards[0].term.name)}.csv`,
      broadsheetRows(cards),
    );
  };

  const choose = (value: string) => {
    setTarget(value);
    if (!value) {
      setSheet(null);
      return;
    }
    const [kind, ...rest] = value.split(":");
    setSheet({ kind: kind as "arm" | "group", value: rest.join(":") });
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3"><div><h1 className="text-2xl font-semibold">Broadsheet</h1><p className="text-sm text-muted-foreground">Review published results for a whole class or class group.</p></div><div className="flex items-center gap-2"><Button variant="outline" onClick={downloadSpreadsheet} disabled={!cards.length}><Download className="h-4 w-4" /> Download spreadsheet</Button><Button variant="outline" onClick={() => window.print()} disabled={!cards.length}><Printer className="h-4 w-4" /> Print</Button></div></div>
      <Card><CardHeader><CardTitle>Choose term and sheet</CardTitle></CardHeader><CardContent className="grid gap-4 sm:grid-cols-2"><select className="h-9 rounded-md border px-3 text-sm" value={termId} onChange={(event) => setTermId(event.target.value)}><option value="">Choose term...</option>{terms.map((term) => <option key={term.id} value={term.id}>{term.name}</option>)}</select><select className="h-9 rounded-md border px-3 text-sm" value={target} onChange={(event) => choose(event.target.value)}><option value="">Choose class or group...</option>{groups.length > 0 && <optgroup label="Class groups">{groups.map((group) => <option key={`group:${group}`} value={`group:${group}`}>{group} — every class in the group</option>)}</optgroup>}<optgroup label="Single classes">{arms.map((arm) => <option key={arm.id} value={`arm:${arm.id}`}>{arm.full_name}</option>)}</optgroup></select></CardContent></Card>
      {isLoading && <p className="text-sm text-muted-foreground">Loading broadsheet...</p>}
      {error && <p className="text-sm text-destructive">Could not load the broadsheet.</p>}
      {cards.length > 0 && <Card><CardHeader><CardTitle>{title} · {cards[0].term.name}</CardTitle></CardHeader><CardContent><div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="border-b text-left"><th className="p-2">Student</th>{sheet?.kind === "group" && <th className="p-2">Class</th>}<th className="p-2 text-right">Position</th>{subjects.map((subject) => <th key={subject.subject_id} className="p-2 text-right">{subject.subject_name}</th>)}<th className="p-2 text-right">Average</th></tr></thead><tbody>{cards.map((card) => <tr key={card.enrollment_id} className="border-b"><td className="p-2 font-medium">{card.student.full_name}</td>{sheet?.kind === "group" && <td className="p-2 text-muted-foreground">{card.class_arm.full_name}</td>}<td className="p-2 text-right">{card.summary.class_rank ?? "-"}<span className="text-muted-foreground">/{card.summary.class_size}</span></td>{subjects.map((subject) => { const current = card.subjects.find((item) => item.subject_id === subject.subject_id); return <td key={subject.subject_id} className="p-2 text-right">{current?.total ?? "-"}</td>; })}<td className="p-2 text-right font-semibold">{card.summary.average ?? "-"}</td></tr>)}</tbody></table></div></CardContent></Card>}
      {!isLoading && sheet && termId && cards.length === 0 && <p className="text-sm text-muted-foreground">No published results are available for this selection and term.</p>}
    </div>
  );
}
