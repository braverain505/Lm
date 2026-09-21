"use client";

import {
  Check,
  Copy,
  Download,
  RefreshCw,
  Search,
  ShieldOff,
  Ticket,
} from "lucide-react";
import { useMemo, useRef, useState } from "react";

import type { StudentResultCode } from "@clearis/shared";

import { Badge } from "@/components/ui/badge";
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
 * Work happens one student at a time: the office picks a child, then issues,
 * reprints or withdraws *that* child's code. A school with a few thousand
 * students cannot be worked from a single scrolling list, and the office rarely
 * needs everyone at once — it needs the one parent standing at the desk. The
 * bulk paths (issue every missing code, download the whole sheet) stay as
 * one-click buttons next to the picker.
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
  const [picking, setPicking] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);

  const withCode = rows.filter((r) => r.active).length;

  // The picker only ever offers a short list: typing two letters already
  // narrows most schools to a handful of children.
  const needle = query.trim().toLowerCase();
  const hits = useMemo(
    () =>
      needle
        ? rows.filter(
            (r) =>
              r.student_name.toLowerCase().includes(needle) ||
              r.admission_no.toLowerCase().includes(needle),
          )
        : rows,
    [rows, needle],
  );
  const matches = hits.slice(0, 8);

  // Read from the query result rather than copying into state, so a regenerated
  // code appears on the panel the moment the mutation invalidates the cache.
  const selected: StudentResultCode | null =
    rows.find((r) => r.student_id === selectedId) ?? null;

  const pick = (row: StudentResultCode) => {
    setSelectedId(row.student_id);
    setQuery("");
    setPicking(false);
    setCopied(false);
    searchRef.current?.blur();
  };

  const copy = async (value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
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
    downloadCsv(`result-code-${row.admission_no}.csv`, [
      CSV_HEADER,
      [row.student_name, row.admission_no, row.code],
    ]);
    toast(`Result code downloaded for ${row.student_name}`);
  };

  const busyFor = (studentId: string) =>
    (generateOne.isPending && generateOne.variables === studentId) ||
    (revokeOne.isPending && revokeOne.variables === studentId);

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
            <p className="text-[13px] font-medium">No students on file yet</p>
            <p className="mx-auto mt-1 max-w-sm text-[12px] leading-relaxed text-muted-foreground">
              A result code is issued per student, so there is nothing to hand
              out until the school has students. This list fills up as soon as
              they are added on the Students desk.
            </p>
          </div>
        ) : (
          <>
            <div className="flex flex-wrap items-start gap-3">
              {/* Student picker — the card's primary control */}
              <div className="relative min-w-[240px] flex-1">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground/50" />
                <Input
                  ref={searchRef}
                  placeholder="Find a student by name or admission number…"
                  value={query}
                  onChange={(e) => {
                    setQuery(e.target.value);
                    setPicking(true);
                  }}
                  onFocus={() => setPicking(true)}
                  onBlur={() => window.setTimeout(() => setPicking(false), 120)}
                  onKeyDown={(e) => {
                    if (e.key === "Escape") setPicking(false);
                    if (e.key === "Enter" && matches.length > 0) {
                      e.preventDefault();
                      pick(matches[0]);
                    }
                  }}
                  autoComplete="off"
                  spellCheck={false}
                  role="combobox"
                  aria-expanded={picking}
                  aria-controls="result-code-picker-list"
                  className="h-10 pl-9"
                />

                {picking && (
                  <div
                    id="result-code-picker-list"
                    role="listbox"
                    className="absolute z-30 mt-1.5 max-h-72 w-full overflow-y-auto rounded-2xl border border-border/60 bg-card p-1.5 shadow-pop"
                  >
                    {matches.length === 0 ? (
                      <p className="px-3 py-4 text-center text-[12px] text-muted-foreground/60">
                        No student matches “{query.trim()}”.
                      </p>
                    ) : (
                      matches.map((row) => (
                        <button
                          key={row.student_id}
                          type="button"
                          role="option"
                          aria-selected={row.student_id === selectedId}
                          // onMouseDown, not onClick: the input's blur fires first
                          onMouseDown={(e) => {
                            e.preventDefault();
                            pick(row);
                          }}
                          className={`flex w-full items-center justify-between gap-3 rounded-xl px-3 py-2 text-left transition-colors hover:bg-accent ${
                            row.student_id === selectedId ? "bg-accent/60" : ""
                          }`}
                        >
                          <span className="min-w-0">
                            <span className="block truncate text-[13px] font-medium">
                              {row.student_name}
                            </span>
                            <span className="block font-mono text-[11px] text-muted-foreground/60">
                              {row.admission_no}
                            </span>
                          </span>
                          {row.active && row.code ? (
                            <Badge variant="success">code issued</Badge>
                          ) : (
                            <Badge variant="muted">not issued</Badge>
                          )}
                        </button>
                      ))
                    )}
                    {hits.length > matches.length && (
                      <p className="px-3 pb-1 pt-2 text-[11px] text-muted-foreground/60">
                        {hits.length} matches — showing the first {matches.length},
                        keep typing to narrow it down.
                      </p>
                    )}
                  </div>
                )}
              </div>

              <Button
                size="sm"
                className="h-10"
                onClick={onGenerateMissing}
                isLoading={generateMissing.isPending}
                disabled={withCode === rows.length}
              >
                <Ticket className="h-3.5 w-3.5" />
                Generate codes for all students
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="h-10"
                onClick={onDownloadAll}
              >
                <Download className="h-3.5 w-3.5" />
                Download all
              </Button>
            </div>

            <p className="text-[11.5px] text-muted-foreground/70">
              <strong className="font-semibold text-foreground">{withCode}</strong>{" "}
              of <strong className="font-semibold text-foreground">{rows.length}</strong>{" "}
              students have a live code.
            </p>

            {/* The chosen student and their code */}
            {selected ? (
              <div className="rounded-2xl border border-border/50 bg-muted/20 px-4 py-4">
                <div className="flex flex-wrap items-center gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[14px] font-semibold">
                      {selected.student_name}
                    </p>
                    <p className="font-mono text-[11px] text-muted-foreground/60">
                      {selected.admission_no}
                    </p>
                  </div>

                  {selected.active && selected.code ? (
                    <button
                      type="button"
                      onClick={() => copy(selected.code!)}
                      title="Copy code"
                      className="rounded-lg border border-primary/20 bg-primary/[0.04] px-3 py-1.5 font-mono text-[15px] font-bold tracking-[0.12em] text-primary transition-colors hover:bg-primary/10"
                    >
                      {selected.code}
                    </button>
                  ) : (
                    <Badge variant="muted">no live code</Badge>
                  )}
                </div>

                <div className="mt-3 flex flex-wrap items-center gap-2">
                  {selected.active && selected.code ? (
                    <>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => copy(selected.code!)}
                      >
                        {copied ? (
                          <Check className="h-3.5 w-3.5 text-success" />
                        ) : (
                          <Copy className="h-3.5 w-3.5" />
                        )}
                        {copied ? "Copied" : "Copy code"}
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => onDownloadOne(selected)}
                      >
                        <Download className="h-3.5 w-3.5" />
                        Download
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={busyFor(selected.student_id)}
                        onClick={() =>
                          onGenerateOne(
                            selected.student_id,
                            selected.student_name,
                            true,
                          )
                        }
                      >
                        <RefreshCw className="h-3.5 w-3.5" />
                        Regenerate
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={busyFor(selected.student_id)}
                        onClick={() =>
                          onRevokeOne(selected.student_id, selected.student_name)
                        }
                        className="text-destructive hover:text-destructive"
                      >
                        <ShieldOff className="h-3.5 w-3.5" />
                        Withdraw
                      </Button>
                    </>
                  ) : (
                    <Button
                      size="sm"
                      disabled={busyFor(selected.student_id)}
                      isLoading={
                        generateOne.isPending &&
                        generateOne.variables === selected.student_id
                      }
                      onClick={() =>
                        onGenerateOne(
                          selected.student_id,
                          selected.student_name,
                          false,
                        )
                      }
                    >
                      <Ticket className="h-3.5 w-3.5" />
                      Issue result code
                    </Button>
                  )}
                </div>
              </div>
            ) : (
              <div className="rounded-2xl border border-dashed border-border/70 bg-muted/20 px-5 py-6 text-center">
                <p className="text-[12.5px] text-muted-foreground">
                  Pick a student above to hand out their result code.
                </p>
              </div>
            )}
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
