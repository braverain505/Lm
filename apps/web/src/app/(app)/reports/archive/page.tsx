"use client";

import type { ReportLayout } from "@clearis/shared";
import { Archive, Eye, Printer } from "lucide-react";
import { useState } from "react";

import { NoAccess } from "@/components/access-denied";
import { REPORT_CARD_PERM } from "@/components/nav-config";
import { ReportCardDocument } from "@/components/report-card-document";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useSessions, useTermArchive, useTermArchives } from "@/hooks/use-api";
import { useAuth } from "@/providers/auth-provider";
import "@/app/report-card.css";
import "@/app/report-card-templates.css";

function fmtDate(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function ResultArchivePage() {
  const { activeSchool } = useAuth();
  if (!(activeSchool?.permissions ?? []).includes(REPORT_CARD_PERM)) {
    return (
      <NoAccess
        title="The result archive is the Exam Office's desk"
        message="Only the Exam Officer and school leadership can read archived report cards. You can still review your own scoresheets from Results."
        backHref="/results"
        backLabel="Go to Results"
      />
    );
  }
  return <ResultArchiveWorkspace />;
}

function ResultArchiveWorkspace() {
  const { data: sessions = [] } = useSessions();
  const [sessionId, setSessionId] = useState("");
  const { data: archives = [], isLoading } = useTermArchives(
    sessionId ? { sessionId } : {},
  );
  const [archiveId, setArchiveId] = useState<string | null>(null);
  const [studentId, setStudentId] = useState<string | null>(null);
  const { data: detail, isLoading: loadingDetail } = useTermArchive(archiveId);

  const selected = archives.find((row) => row.id === archiveId) ?? null;
  const cards = detail?.payload.students ?? [];
  const card =
    cards.find((row) => row.student.student_id === studentId) ?? cards[0] ?? null;
  const layout = (detail?.payload.layout ?? null) as ReportLayout | null;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-[22px] font-bold tracking-tight text-foreground">
            <Archive className="h-5 w-5 text-primary" />
            Result archive
          </h1>
          <p className="mt-1 max-w-2xl text-[13px] text-muted-foreground">
            Every time a term is closed, the report cards that were live at that
            moment are frozen here. Correcting a closed term leaves the old
            version intact, so the document a parent received can always be read
            again.
          </p>
        </div>
        {card && (
          <Button variant="outline" onClick={() => window.print()}>
            <Printer className="h-4 w-4" /> Print this card
          </Button>
        )}
      </div>

      <div className="grid gap-5 lg:grid-cols-[340px_1fr]">
        {/* Archive versions */}
        <Card className="premium-card">
          <CardHeader>
            <CardTitle className="text-[15px]">Archived versions</CardTitle>
            <CardDescription>Newest first, one row per reopen.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <select
              className="flex h-9 w-full rounded-xl border border-border/90 bg-background/70 px-3 text-[13px] shadow-sm transition-all"
              value={sessionId}
              onChange={(e) => {
                setSessionId(e.target.value);
                setArchiveId(null);
                setStudentId(null);
              }}
            >
              <option value="">All sessions</option>
              {sessions.map((session) => (
                <option key={session.id} value={session.id}>
                  {session.name}
                </option>
              ))}
            </select>

            {isLoading ? (
              <div className="space-y-2">
                <Skeleton className="h-16 w-full" />
                <Skeleton className="h-16 w-full" />
              </div>
            ) : archives.length === 0 ? (
              <div className="rounded-xl border border-dashed border-border/70 px-4 py-8 text-center">
                <Archive className="mx-auto h-8 w-8 text-muted-foreground/60" />
                <p className="mt-2 text-[13px] font-medium">No archived cards yet</p>
                <p className="mt-1 text-[11.5px] leading-relaxed text-muted-foreground/90">
                  Closing a term archives its published report cards here, and a
                  reopened term adds a new version when it is closed again.
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {archives.map((row) => (
                  <button
                    key={row.id}
                    type="button"
                    onClick={() => {
                      setArchiveId(row.id);
                      setStudentId(null);
                    }}
                    className={`w-full rounded-xl border px-3.5 py-3 text-left transition-all duration-150 hover:border-primary/35 hover:bg-accent/70 ${
                      row.id === archiveId
                        ? "border-primary/45 bg-accent/80"
                        : "border-border/60"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-[13px] font-semibold">
                        {row.term_name ?? "Term"} · v{row.version}
                      </p>
                      <Badge variant="outline">{row.student_count} cards</Badge>
                    </div>
                    <p className="mt-0.5 text-[11px] text-muted-foreground/85">
                      {row.session_name ?? "Session"} · {fmtDate(row.archived_at)}
                    </p>
                    <p className="mt-1 line-clamp-2 text-[11.5px] text-muted-foreground/90">
                      {row.reason}
                    </p>
                  </button>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Frozen card viewer */}
        <Card className="premium-card min-w-0">
          <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-3">
            <div>
              <CardTitle className="text-[15px]">
                {selected
                  ? `${selected.term_name ?? "Term"} — archived version ${selected.version}`
                  : "Choose an archived version"}
              </CardTitle>
              <CardDescription>
                {selected
                  ? `Archived ${fmtDate(selected.archived_at)}${
                      selected.archived_by_name
                        ? ` by ${selected.archived_by_name}`
                        : ""
                    } · ${selected.class_count} class${
                      selected.class_count === 1 ? "" : "es"
                    }`
                  : "The card renders exactly as it was published."}
              </CardDescription>
            </div>
            {cards.length > 0 && (
              <select
                className="h-9 max-w-64 rounded-xl border border-border/90 bg-background/70 px-3 text-[13px] shadow-sm transition-all"
                value={card?.student.student_id ?? ""}
                onChange={(e) => setStudentId(e.target.value)}
              >
                {cards.map((row) => (
                  <option key={row.student.student_id} value={row.student.student_id}>
                    {row.student.full_name} · {row.class_arm.full_name}
                  </option>
                ))}
              </select>
            )}
          </CardHeader>
          <CardContent>
            {!selected ? (
              <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-border/70 px-6 py-16 text-center">
                <Eye className="h-8 w-8 text-muted-foreground/60" />
                <p className="text-[13px] font-medium">Select an archived version</p>
                <p className="max-w-sm text-[11.5px] text-muted-foreground/90">
                  The frozen cards include totals, grades, comments, psychomotor
                  rows and the layout they were printed with.
                </p>
              </div>
            ) : loadingDetail ? (
              <Skeleton className="h-[520px] w-full" />
            ) : card ? (
              <ReportCardDocument card={card} layout={layout} />
            ) : (
              <p className="py-10 text-center text-[13px] text-muted-foreground">
                This archived version has no readable cards.
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
