"use client";

import { Check, Copy, Download, RefreshCw, Search, ShieldOff, Ticket } from "lucide-react";
import { useState } from "react";

import type { StudentResultCode } from "@clearis/shared";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/toast";
import { downloadCsv } from "@/lib/csv";
import {
  useGenerateMissingStudentResultCodes,
  useGenerateStudentResultCode,
  useRevokeStudentResultCode,
  useStudentResultCodes,
} from "@/hooks/use-api";

/**
 * The result codes parents use: one per student, each carrying the school's
 * initials (e.g. ``GVS-7K42Q``).
 *
 * Because a code names the child, the login screen asks for the code alone — no
 * admission number. Issuing the code is the Exam Office's job, the same
 * ``results.report_card`` capability that gates report cards, so this card
 * lives on the Report Cards page rather than in School Settings.
 *
 * Codes are shown in full (not masked) because the exam office has to be able
 * to reprint them; see the model docstring for why a distributable code is
 * stored as issued rather than hashed.
 */
export function ResultCodeCard() {
  const { data: rows = [], isLoading } = useStudentResultCodes();
  const generateMissing = useGenerateMissingStudentResultCodes();
  const generateOne = useGenerateStudentResultCode();
  const revokeOne = useRevokeStudentResultCode();
  const { toast } = useToast();
  const [query, setQuery] = useState("");
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const withCode = rows.filter((r) => r.active).length;

  const needle = query.trim().toLowerCase();
  const filtered = needle
    ? rows.filter(
        (r) =>
          r.student_name.toLowerCase().includes(needle) ||
          r.admission_no.toLowerCase().includes(needle),
      )
    : rows;

  const copy = async (rowId: string, value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setCopiedId(rowId);
      window.setTimeout(
        () => setCopiedId((c) => (c === rowId ? null : c)),
        1800,
      );
      toast("Result code copied");
    } catch {
      toast("Could not copy — select the code and copy it manually", "error");
    }
  };

  const onGenerateMissing = async () => {
    if (
      !window.confirm(
        "Generate a result code for every student who does not have one?\n\nExisting codes are left untouched.",
      )
    ) {
      return;
    }
    try {
      const result = await generateMissing.mutateAsync();
      toast(
        result.issued === 0
          ? "Every student already has a code"
          : `Issued ${result.issued} result code${result.issued === 1 ? "" : "s"}`,
      );
    } catch (e) {
      toast(e instanceof Error ? e.message : "Failed to generate codes", "error");
    }
  };

  const onGenerateOne = async (studentId: string, name: string, hasCode: boolean) => {
    if (
      hasCode &&
      !window.confirm(
        `Replace the result code for ${name}?\n\nTheir current code stops working immediately.`,
      )
    ) {
      return;
    }
    try {
      const row = await generateOne.mutateAsync(studentId);
      toast(`Code ${row.code} is now live for ${name}`);
    } catch (e) {
      toast(e instanceof Error ? e.message : "Failed to generate the code", "error");
    }
  };

  const onRevokeOne = async (studentId: string, name: string) => {
    if (
      !window.confirm(
        `Withdraw the result code for ${name}?\n\nIt will no longer open their result.`,
      )
    ) {
      return;
    }
    try {
      await revokeOne.mutateAsync(studentId);
      toast(`Code withdrawn for ${name}`);
    } catch (e) {
      toast(e instanceof Error ? e.message : "Failed to withdraw the code", "error");
    }
  };

  // The header row every export shares, so a downloaded sheet reads the same
  // whether it holds one student or the whole school.
  const CSV_HEADER = ["Student", "Admission No", "Result Code"];

  const onDownloadAll = () => {
    if (rows.length === 0) return;
    const stamp = new Date().toISOString().slice(0, 10);
    downloadCsv(`result-codes-${stamp}.csv`, [
      CSV_HEADER,
      ...rows.map((r) => [
        r.student_name,
        r.admission_no,
        r.active && r.code ? r.code : "Not issued",
      ]),
    ]);
    toast(`${rows.length} result code${rows.length === 1 ? "" : "s"} downloaded`);
  };

  const onDownloadOne = (row: StudentResultCode) => {
    if (!row.code) return;
    downloadCsv(
      `result-code-${row.admission_no}.csv`,
      [CSV_HEADER, [row.student_name, row.admission_no, row.code]],
    );
    toast(`Result code downloaded for ${row.student_name}`);
  };

  return (
    <Card className="premium-card">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-[15px]">
          <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-primary/10">
            <Ticket className="h-4 w-4 text-primary" />
          </span>
          Results portal codes
        </CardTitle>
        <CardDescription>
          Every student has their own code. A parent enters it on the login
          screen to open that student&apos;s published report card — no
          admission number needed.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoading ? (
          <Skeleton className="h-48 w-full" />
        ) : rows.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border/70 bg-muted/20 px-5 py-8 text-center">
            <p className="text-[13px] font-medium">No students yet</p>
            <p className="mx-auto mt-1 max-w-sm text-[12px] leading-relaxed text-muted-foreground">
              Add students first, then issue each of them a result code.
            </p>
          </div>
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-3">
              <div className="relative min-w-0 flex-1">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground/50" />
                <Input
                  placeholder="Search by name or admission number…"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  className="h-10 pl-9"
                />
              </div>
              <Button
                size="sm"
                onClick={onGenerateMissing}
                isLoading={generateMissing.isPending}
                disabled={withCode === rows.length}
              >
                <Ticket className="h-3.5 w-3.5" />
                Generate codes for all students
              </Button>
              <Button variant="outline" size="sm" onClick={onDownloadAll}>
                <Download className="h-3.5 w-3.5" />
                Download all
              </Button>
            </div>

            <p className="text-[11.5px] text-muted-foreground/70">
              <strong className="font-semibold text-foreground">{withCode}</strong>{" "}
              of <strong className="font-semibold text-foreground">{rows.length}</strong>{" "}
              students have a live code.
            </p>

            <div className="max-h-[440px] space-y-2 overflow-y-auto pr-1">
              {filtered.length === 0 ? (
                <p className="py-8 text-center text-[12.5px] text-muted-foreground/60">
                  No students match “{query.trim()}”.
                </p>
              ) : (
                filtered.map((row) => {
                  const busy =
                    (generateOne.isPending &&
                      generateOne.variables === row.student_id) ||
                    (revokeOne.isPending && revokeOne.variables === row.student_id);
                  return (
                    <div
                      key={row.student_id}
                      className="flex flex-wrap items-center gap-3 rounded-2xl border border-border/50 bg-muted/20 px-4 py-3"
                    >
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-[13px] font-semibold">
                          {row.student_name}
                        </p>
                        <p className="font-mono text-[11px] text-muted-foreground/60">
                          {row.admission_no}
                        </p>
                      </div>

                      {row.active && row.code ? (
                        <>
                          <button
                            type="button"
                            onClick={() => copy(row.student_id, row.code!)}
                            title="Copy code"
                            className="rounded-lg border border-primary/20 bg-primary/[0.04] px-3 py-1.5 font-mono text-[14px] font-bold tracking-[0.12em] text-primary transition-colors hover:bg-primary/10"
                          >
                            {row.code}
                          </button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => copy(row.student_id, row.code!)}
                            aria-label="Copy code"
                            title="Copy code"
                          >
                            {copiedId === row.student_id ? (
                              <Check className="h-3.5 w-3.5 text-success" />
                            ) : (
                              <Copy className="h-3.5 w-3.5" />
                            )}
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => onDownloadOne(row)}
                            aria-label="Download code"
                            title="Download code"
                          >
                            <Download className="h-3.5 w-3.5" />
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={busy}
                            onClick={() =>
                              onGenerateOne(row.student_id, row.student_name, true)
                            }
                          >
                            <RefreshCw className="h-3.5 w-3.5" />
                            Regenerate
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={busy}
                            onClick={() => onRevokeOne(row.student_id, row.student_name)}
                            className="text-destructive hover:text-destructive"
                          >
                            <ShieldOff className="h-3.5 w-3.5" />
                            Withdraw
                          </Button>
                        </>
                      ) : (
                        <>
                          <span className="text-[11.5px] text-muted-foreground/60">
                            Not issued
                          </span>
                          <Button
                            size="sm"
                            disabled={busy}
                            isLoading={
                              generateOne.isPending &&
                              generateOne.variables === row.student_id
                            }
                            onClick={() =>
                              onGenerateOne(row.student_id, row.student_name, false)
                            }
                          >
                            <Ticket className="h-3.5 w-3.5" />
                            Generate
                          </Button>
                        </>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </>
        )}

        <p className="text-[11.5px] leading-relaxed text-muted-foreground/70">
          A code identifies one student, so it only ever opens that student&apos;s
          published result. Regenerating invalidates the old code immediately;
          withdrawn codes stop working at once and a new one can be issued later.
        </p>
      </CardContent>
    </Card>
  );
}
