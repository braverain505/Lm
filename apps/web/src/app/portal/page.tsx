"use client";

// Public result portal: look up your school, check in with admission no + PIN,
// and view your published report card. No login, no tenant header — this page
// talks only to the /api/public/* endpoints.
import { Printer, ShieldCheck } from "lucide-react";
import { useState } from "react";

import { api, publicReportCard } from "@schoolos/shared";
import type { PinCheckOut, ReportCard, SchoolBrief } from "@schoolos/shared";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";

function componentColumns(card: ReportCard): string[] {
  const names = new Set<string>();
  card.subjects.forEach((s) => s.components.forEach((c) => names.add(c.name)));
  return [...names];
}

function scoreFor(card: ReportCard, subjectName: string, column: string): number | null {
  const subject = card.subjects.find((s) => s.subject_name === subjectName);
  return subject?.components.find((c) => c.name === column)?.score ?? null;
}

export default function PortalPage() {
  const [schools, setSchools] = useState<SchoolBrief[]>([]);
  const [schoolsLoading, setSchoolsLoading] = useState(true);
  const [selected, setSelected] = useState("");
  const [admissionNo, setAdmissionNo] = useState("");
  const [pin, setPin] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [session, setSession] = useState<PinCheckOut | null>(null);
  const [card, setCard] = useState<ReportCard | null>(null);
  const [cardLoading, setCardLoading] = useState(false);

  // Lazily load the public school list on first interaction (keeps the portal
  // page fast and the list fresh enough for a check-in form).
  const loadSchools = async () => {
    if (schools.length > 0 || schoolsLoading) return;
    setSchoolsLoading(true);
    try {
      setSchools(await api.publicSchools());
    } catch {
      setSchools([]);
    } finally {
      setSchoolsLoading(false);
    }
  };

  const checkIn = async () => {
    setError(null);
    setCard(null);
    if (!selected || !admissionNo.trim() || !pin.trim()) {
      setError("Pick your school, then enter your admission number and PIN.");
      return;
    }
    setBusy(true);
    try {
      const res = await api.pinCheck({
        school_slug: selected,
        admission_no: admissionNo.trim(),
        pin: pin.trim(),
      });
      setSession(res);
      setCardLoading(true);
      try {
        setCard(await publicReportCard(res.token));
      } catch (e) {
        setError(apiErrorMessage(e, "No published results for this PIN yet."));
      } finally {
        setCardLoading(false);
      }
    } catch (e) {
      setError(apiErrorMessage(e, "Check-in failed. Verify your details and try again."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="flex min-h-screen items-center justify-center bg-gradient-to-br from-primary/10 via-background to-background p-4"
      onClick={loadSchools}
    >
      <div className="w-full max-w-3xl">
        <div className="mb-6 text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10">
            <ShieldCheck className="h-6 w-6 text-primary" />
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">Results portal</h1>
          <p className="text-sm text-muted-foreground">
            View your officially published report card. Only schools that publish results appear here.
          </p>
        </div>

        {error && (
          <Card className="mb-4 border-destructive/40">
            <CardContent className="py-3 text-sm text-destructive">{error}</CardContent>
          </Card>
        )}

        {/* Check-in form */}
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>Check in</CardTitle>
            <CardDescription>
              Your PIN is issued by the school and unlocks your published results only.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-3">
            <div className="space-y-2">
              <Label>School</Label>
              {schoolsLoading && schools.length === 0 ? (
                <Skeleton className="h-9 w-full" />
              ) : (
                <select
                  className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
                  value={selected}
                  onChange={(e) => setSelected(e.target.value)}
                >
                  <option value="">Choose your school…</option>
                  {schools.map((s) => (
                    <option key={s.id} value={s.slug}>
                      {s.name}
                    </option>
                  ))}
                </select>
              )}
            </div>
            <div className="space-y-2">
              <Label>Admission no.</Label>
              <Input
                value={admissionNo}
                onChange={(e) => setAdmissionNo(e.target.value)}
                placeholder="STU-001"
              />
            </div>
            <div className="space-y-2">
              <Label>PIN</Label>
              <Input
                value={pin}
                onChange={(e) => setPin(e.target.value)}
                inputMode="numeric"
                maxLength={6}
                placeholder="••••"
              />
            </div>
            <div className="sm:col-span-3">
              <Button onClick={checkIn} disabled={busy} className="w-full">
                {busy ? "Checking…" : "View my report"}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Report card */}
        {session && (
          <div className="print:flex print:min-h-screen print:items-center print:justify-center">
            <div className="rounded-xl border bg-card p-6 shadow-sm print:border-0 print:shadow-none">
              {/* Header */}
              <div className="mb-4 flex items-start justify-between gap-2 border-b pb-4">
                <div>
                  <p className="font-semibold">{session.student.full_name}</p>
                  <p className="text-sm text-muted-foreground">
                    Admission No: {session.student.admission_no}
                  </p>
                </div>
                <button
                  onClick={() => window.print()}
                  disabled={!card}
                  className="inline-flex items-center gap-2 rounded-md border border-input px-3 py-1.5 text-sm font-medium transition-colors hover:bg-accent"
                >
                  <Printer className="h-4 w-4" /> Print
                </button>
              </div>

              {cardLoading ? (
                <Skeleton className="h-64 w-full" />
              ) : card ? (
                <div>
                  <div className="mb-4 text-center">
                    <h2 className="text-lg font-semibold">
                      {card.term.name} Term Report · Session {card.session.name} ·{" "}
                      {card.class_arm.full_name}
                    </h2>
                    <p className="text-sm text-muted-foreground">
                      Position: {card.summary.class_rank ?? "—"} of {card.summary.class_size} ·{" "}
                      Average: {card.summary.average} · Grade: {card.summary.grade_letter ?? "—"}
                    </p>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                          <th className="py-2 pr-2">Subject</th>
                          {componentColumns(card).map((c) => (
                            <th key={c} className="py-2 pr-2 text-right">
                              {c}
                            </th>
                          ))}
                          <th className="py-2 pr-2 text-right">Total</th>
                          <th className="py-2 pr-2 text-center">Grade</th>
                          <th className="py-2 pr-2 text-center">Pos</th>
                          <th className="py-2">Remark</th>
                        </tr>
                      </thead>
                      <tbody>
                        {card.subjects.map((s) => (
                          <tr key={s.subject_id} className="border-b last:border-0">
                            <td className="py-2 pr-2 font-medium">{s.subject_name}</td>
                            {componentColumns(card).map((c) => (
                              <td key={c} className="py-2 pr-2 text-right tabular-nums">
                                {scoreFor(card, s.subject_name, c) ?? ""}
                              </td>
                            ))}
                            <td className="py-2 pr-2 text-right font-semibold tabular-nums">
                              {s.total ?? ""}
                            </td>
                            <td className="py-2 pr-2 text-center">{s.grade_letter ?? "—"}</td>
                            <td className="py-2 pr-2 text-center tabular-nums">{s.position ?? "—"}</td>
                            <td className="py-2 text-xs">{s.remark ?? "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  <div className="mt-4 flex items-center justify-between border-t pt-3 text-sm text-muted-foreground">
                    <span>
                      Total <strong className="text-foreground tabular-nums">{card.summary.total}</strong>
                    </span>
                    <span className="inline-flex items-center gap-1">
                      <ShieldCheck className="h-3.5 w-3.5" /> Verified · {card.term.name}
                    </span>
                  </div>
                </div>
              ) : (
                <p className="py-10 text-center text-sm text-muted-foreground">
                  No published results available yet.
                </p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function apiErrorMessage(e: unknown, fallback: string): string {
  if (e instanceof Error && e.message) return e.message;
  return fallback;
}