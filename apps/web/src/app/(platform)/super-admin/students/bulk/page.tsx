"use client";

import { AlertTriangle, ArrowLeft, Building2, CheckCircle2, Plus, Search, Trash2, UserPlus, X } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useRef, useState, type FormEvent } from "react";

import { EmptyState, Panel, PanelSkeleton, fmtNum } from "@/components/platform-utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  useSaBulkAddStudents,
  useSaCreateSchoolClass,
  useSaSchoolClasses,
  useSaSchools,
} from "@/hooks/use-superadmin";
import type { SaBulkStudentResult, SaSchoolClassCreated, SaSessionWithArms } from "@clearis/shared";

const MAX_ROWS = 1000;

type Gender = "unspecified" | "male" | "female";

interface Row {
  key: string;
  name: string;
  armId: string;
  gender: Gender;
}

export default function BulkStudentsPage() {
  return (
    <Suspense fallback={<PanelSkeleton rows={8} />}>
      <BulkStudentsWorkspace />
    </Suspense>
  );
}

function BulkStudentsWorkspace() {
  const searchParams = useSearchParams();
  const [schoolId, setSchoolId] = useState<string | null>(searchParams.get("school"));

  if (!schoolId) {
    return <SchoolPicker onSelect={setSchoolId} />;
  }

  return <BulkIntake schoolId={schoolId} onChangeSchool={() => setSchoolId(null)} />;
}

/* ---------------------------------------------------------------- school picker */

function SchoolPicker({ onSelect }: { onSelect: (id: string) => void }) {
  const [q, setQ] = useState("");
  const { data, isLoading } = useSaSchools({ q: q || undefined, per_page: 20 });
  const items = data?.items ?? [];

  return (
    <div className="space-y-5">
      <div>
        <Link
          href="/super-admin/schools"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" /> Schools
        </Link>
        <h1 className="mt-3 flex items-center gap-2 text-xl font-semibold tracking-tight">
          <UserPlus className="h-5 w-5 text-primary" /> Add students in bulk
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Choose the school that will receive the students. You will pick a class for each child on the next step.
        </p>
      </div>

      <Panel title="Choose a school">
        <div className="space-y-3">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search by school name, slug or email..."
              className="h-10 pl-9"
              autoFocus
            />
          </div>

          {isLoading ? (
            <PanelSkeleton rows={4} />
          ) : items.length === 0 ? (
            <EmptyState message="No schools match that search." />
          ) : (
            <div className="divide-y rounded-xl border">
              {items.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => onSelect(s.id)}
                  className="flex w-full items-center gap-3 px-3 py-3 text-left transition-colors hover:bg-accent"
                >
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/15 font-semibold text-primary">
                    {s.name.charAt(0)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{s.name}</p>
                    <p className="truncate text-xs text-muted-foreground">
                      {s.slug} · {fmtNum(s.students)} student{s.students === 1 ? "" : "s"} · {s.state ?? s.country}
                    </p>
                  </div>
                  <Building2 className="h-4 w-4 shrink-0 text-muted-foreground" />
                </button>
              ))}
            </div>
          )}
          {(data?.total ?? 0) > items.length && (
            <p className="text-xs text-muted-foreground">
              Showing {items.length} of {fmtNum(data!.total)} schools. Search to narrow the list.
            </p>
          )}
        </div>
      </Panel>
    </div>
  );
}

/* ------------------------------------------------------------------- bulk intake */

function BulkIntake({ schoolId, onChangeSchool }: { schoolId: string; onChangeSchool: () => void }) {
  const { data, isLoading, isError } = useSaSchoolClasses(schoolId);
  const bulkAdd = useSaBulkAddStudents(schoolId);

  const [sessionId, setSessionId] = useState("");
  const [rows, setRows] = useState<Row[]>([]);
  const [pasteText, setPasteText] = useState("");
  const [defaultArm, setDefaultArm] = useState("");
  const [problem, setProblem] = useState("");
  const [result, setResult] = useState<SaBulkStudentResult | null>(null);
  const [showNewClass, setShowNewClass] = useState(false);
  const [classNotice, setClassNotice] = useState("");
  const keyRef = useRef(0);

  const sessions = useMemo(() => data?.sessions ?? [], [data]);
  const activeSession = useMemo(
    () => sessions.find((s) => s.id === sessionId) ?? null,
    [sessions, sessionId],
  );
  const arms = useMemo(() => activeSession?.arms ?? [], [activeSession]);

  // Default to the current session once the school loads — but if that session
  // has no classes, prefer one that does, so the class list is never empty
  // just because the school keeps its classes on another session.
  useEffect(() => {
    if (!sessions.length) return;
    setSessionId((prev) => {
      if (prev && sessions.some((s) => s.id === prev)) return prev;
      const preferred =
        sessions.find((s) => s.is_current && s.arms.length > 0) ??
        sessions.find((s) => s.arms.length > 0) ??
        sessions.find((s) => s.is_current) ??
        sessions[0];
      return preferred.id;
    });
  }, [sessions]);

  // Keep class selections valid when the session changes. Returning the same
  // state when nothing is stale keeps this from looping while classes load.
  useEffect(() => {
    setRows((prev) => {
      let changed = false;
      const next = prev.map((row) => {
        if (row.armId && !arms.some((arm) => arm.id === row.armId)) {
          changed = true;
          return { ...row, armId: "" };
        }
        return row;
      });
      return changed ? next : prev;
    });
    setDefaultArm((prev) => (prev && !arms.some((arm) => arm.id === prev) ? "" : prev));
  }, [arms]);

  function nextKey() {
    keyRef.current += 1;
    return `row-${keyRef.current}`;
  }

  function parsePastedNames() {
    const names = pasteText
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);
    if (!names.length) {
      setProblem("Paste one child's name per line first.");
      return;
    }
    if (names.length > MAX_ROWS) {
      setProblem(`That is ${fmtNum(names.length)} names. The limit is ${fmtNum(MAX_ROWS)} per submission.`);
      return;
    }
    const initialArm = defaultArm || (arms.length === 1 ? arms[0].id : "");
    setRows((prev) => [
      ...prev,
      ...names.map((name) => ({ key: nextKey(), name, armId: initialArm, gender: "unspecified" as Gender })),
    ]);
    setPasteText("");
    setProblem("");
    setResult(null);
  }

  function updateRow(key: string, patch: Partial<Row>) {
    setRows((prev) => prev.map((row) => (row.key === key ? { ...row, ...patch } : row)));
  }

  function applyDefaultArm(armId: string) {
    setDefaultArm(armId);
    setRows((prev) => prev.map((row) => ({ ...row, armId })));
  }

  function handleClassCreated(created: SaSchoolClassCreated) {
    setSessionId(created.session.id);
    setDefaultArm(created.class_arm.id);
    // Children already in the list who have no class yet fall into the new one.
    setRows((prev) => prev.map((row) => (row.armId ? row : { ...row, armId: created.class_arm.id })));
    setClassNotice(
      created.created
        ? `Class ${created.class_arm.full_name} created in ${created.session.name}.`
        : `${created.class_arm.full_name} already exists in ${created.session.name}, so it was selected instead.`,
    );
    setShowNewClass(false);
    setProblem("");
  }

  function submit() {
    setProblem("");
    if (!activeSession) {
      setProblem("Choose an academic session first.");
      return;
    }
    if (!rows.length) {
      setProblem("Add at least one child's name.");
      return;
    }
    if (rows.length > MAX_ROWS) {
      setProblem(`The limit is ${fmtNum(MAX_ROWS)} students per submission.`);
      return;
    }
    const incomplete = rows.find((row) => !row.name.trim() || row.name.trim().split(/\s+/).length < 2);
    if (incomplete) {
      setProblem(`"${incomplete.name || "An empty row"}" needs a first name and a surname.`);
      return;
    }
    const unassigned = rows.find((row) => !row.armId);
    if (unassigned) {
      setProblem(`Choose a class for "${unassigned.name}".`);
      return;
    }

    setResult(null);
    bulkAdd.mutate(
      {
        session_id: activeSession.id,
        rows: rows.map((row) => ({
          full_name: row.name.trim(),
          class_arm_id: row.armId,
          gender: row.gender === "unspecified" ? null : row.gender,
        })),
      },
      {
        onSuccess: (res) => {
          setResult(res);
          setRows([]);
          setPasteText("");
          setProblem("");
        },
        onError: (error) => {
          setProblem(error.message || "Could not add the students. Please try again.");
        },
      },
    );
  }

  if (isLoading) {
    return (
      <div className="space-y-4">
        <BackRow onChangeSchool={onChangeSchool} />
        <PanelSkeleton rows={8} />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="space-y-4">
        <BackRow onChangeSchool={onChangeSchool} />
        <Panel>
          <EmptyState message="Could not load this school's classes. Check the school still exists and try again." />
        </Panel>
      </div>
    );
  }

  const noClasses = sessions.length === 0 || arms.length === 0;

  return (
    <div className="space-y-5">
      <BackRow onChangeSchool={onChangeSchool} />

      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
            <UserPlus className="h-5 w-5 text-primary" /> Add students in bulk
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Adding to <span className="font-medium text-foreground">{data.school.name}</span>. Each child is created with an
            admission number and enrolled in the class you choose.
          </p>
        </div>
      </div>

      {noClasses ? (
        <Panel
          title="This school has no classes yet"
          subtitle={`Create the first class for ${data.school.name} here, then add students to it.`}
        >
          <div className="space-y-4">
            <div className="flex items-start gap-3 rounded-xl border border-amber-500/40 bg-amber-500/10 p-4 text-sm">
              <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />
              <p className="text-muted-foreground">
                Every student is enrolled in a class, and a class belongs to an academic session.
                {sessions.length === 0
                  ? " This school has no session yet, so name one below."
                  : " The session below is the school's current one."}
              </p>
            </div>
            <NewClassForm
              schoolId={data.school.id}
              sessions={sessions}
              defaultSessionId={sessionId}
              autoFocus
              onCreated={handleClassCreated}
            />
            <Link
              href={`/super-admin/schools/${data.school.id}`}
              className="inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:underline"
            >
              <Building2 className="h-3.5 w-3.5" /> Open {data.school.name}
            </Link>
          </div>
        </Panel>
      ) : (
        <>
          {result && <ResultPanel result={result} />}

          <Panel title="1. Paste the names">
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">
                One child per line. Write the name as it should appear on the student record: first name, middle name(s)
                and surname. For example <span className="font-medium text-foreground">Adaeze Ngozi Okafor</span>.
              </p>
              <textarea
                value={pasteText}
                onChange={(e) => setPasteText(e.target.value)}
                rows={7}
                placeholder={"Adaeze Ngozi Okafor\nTunde Bakare\nAmina Yusuf"}
                className="w-full resize-y rounded-xl border border-border/90 bg-background/70 px-3 py-2 font-mono text-[13px] leading-relaxed shadow-sm outline-none transition-all focus:border-primary/55 focus:ring-2 focus:ring-primary/20"
              />
              <div className="flex flex-wrap items-center gap-2">
                <Button type="button" onClick={parsePastedNames}>
                  <UserPlus className="h-4 w-4" /> Add names to the list
                </Button>
                <span className="text-xs text-muted-foreground">
                  {fmtNum(pasteText.split(/\r?\n/).filter((l) => l.trim()).length)} line(s) ready
                </span>
              </div>
            </div>
          </Panel>

          <Panel
            title={`2. Assign classes (${fmtNum(rows.length)} child${rows.length === 1 ? "" : "ren"})`}
            subtitle="Every child needs a class. Use the top selector to put the whole group in one class, then change individuals as needed."
          >
            <div className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label className="text-xs">Academic session</Label>
                  <Select
                    value={sessionId}
                    onValueChange={(value) => {
                      setSessionId(value);
                      setResult(null);
                    }}
                  >
                    <SelectTrigger className="h-9 w-full">
                      <SelectValue placeholder="Choose a session" />
                    </SelectTrigger>
                    <SelectContent>
                      {sessions.map((s) => (
                        <SelectItem key={s.id} value={s.id}>
                          {s.name}
                          {s.is_current ? " (current)" : ""}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs">Put everyone in</Label>
                  <Select
                    value={defaultArm || "none"}
                    onValueChange={(value) => applyDefaultArm(value === "none" ? "" : value)}
                    disabled={!rows.length}
                  >
                    <SelectTrigger className="h-9 w-full">
                      <SelectValue placeholder="Choose a class" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">No default class</SelectItem>
                      {arms.map((arm) => (
                        <SelectItem key={arm.id} value={arm.id}>
                          {arm.full_name} · {fmtNum(arm.students)} enrolled
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => setShowNewClass((open) => !open)}
                >
                  <Plus className="h-3.5 w-3.5" /> New class
                </Button>
                <p className="text-xs text-muted-foreground">
                  Need a class that is not in the list? Create it here and it becomes selectable straight away.
                </p>
              </div>

              {classNotice && (
                <p className="flex items-center gap-1.5 text-sm text-emerald-700 dark:text-emerald-300">
                  <CheckCircle2 className="h-3.5 w-3.5" /> {classNotice}
                </p>
              )}

              {showNewClass && (
                <div className="rounded-xl border bg-muted/40 p-3">
                  <NewClassForm
                    schoolId={schoolId}
                    sessions={sessions}
                    defaultSessionId={sessionId}
                    autoFocus
                    onCreated={handleClassCreated}
                    onCancel={() => setShowNewClass(false)}
                  />
                </div>
              )}

              {rows.length === 0 ? (
                <EmptyState message="Paste names above and add them to the list to assign classes." />
              ) : (
                <div className="overflow-hidden rounded-xl border">
                  <div className="hidden grid-cols-[1.6fr_1.1fr_0.9fr_auto] gap-2 border-b bg-muted/50 px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground sm:grid">
                    <span>Name</span>
                    <span>Class</span>
                    <span>Gender</span>
                    <span />
                  </div>
                  <div className="max-h-[28rem] divide-y overflow-y-auto">
                    {rows.map((row, index) => (
                      <div
                        key={row.key}
                        className="grid grid-cols-1 gap-2 px-3 py-2.5 sm:grid-cols-[1.6fr_1.1fr_0.9fr_auto] sm:items-center"
                      >
                        <div className="flex items-center gap-2">
                          <span className="w-6 shrink-0 text-right text-xs tabular-nums text-muted-foreground">
                            {index + 1}
                          </span>
                          <Input
                            value={row.name}
                            onChange={(e) => updateRow(row.key, { name: e.target.value })}
                            className="h-8 text-[13px]"
                            aria-label={`Name for child ${index + 1}`}
                          />
                        </div>
                        <Select
                          value={row.armId || ""}
                          onValueChange={(value) => updateRow(row.key, { armId: value })}
                        >
                          <SelectTrigger className="h-8 w-full text-[12px]">
                            <SelectValue placeholder="Choose class" />
                          </SelectTrigger>
                          <SelectContent>
                            {arms.map((arm) => (
                              <SelectItem key={arm.id} value={arm.id}>
                                {arm.full_name}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <Select
                          value={row.gender}
                          onValueChange={(value) => updateRow(row.key, { gender: value as Gender })}
                        >
                          <SelectTrigger className="h-8 w-full text-[12px]">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="unspecified">Not specified</SelectItem>
                            <SelectItem value="male">Male</SelectItem>
                            <SelectItem value="female">Female</SelectItem>
                          </SelectContent>
                        </Select>
                        <Button
                          type="button"
                          size="icon"
                          variant="ghost"
                          className="h-8 w-8 justify-self-end text-muted-foreground hover:text-destructive"
                          onClick={() => setRows((prev) => prev.filter((r) => r.key !== row.key))}
                          aria-label={`Remove ${row.name || "row"}`}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="flex flex-wrap items-center gap-2 border-t pt-4">
                <Button type="button" onClick={submit} disabled={!rows.length} isLoading={bulkAdd.isPending}>
                  <UserPlus className="h-4 w-4" />
                  {bulkAdd.isPending
                    ? "Adding students..."
                    : `Add ${fmtNum(rows.length)} student${rows.length === 1 ? "" : "s"}`}
                </Button>
                {rows.length > 0 && (
                  <Button type="button" variant="ghost" onClick={() => setRows([])} disabled={bulkAdd.isPending}>
                    <X className="h-4 w-4" /> Clear list
                  </Button>
                )}
                {problem && <p className="text-sm text-destructive">{problem}</p>}
              </div>
            </div>
          </Panel>
        </>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ new class */

/** The academic year a Nigerian session would be called right now, so the
 *  first class a school gets does not start from an empty box. */
function suggestedSessionName(): string {
  const now = new Date();
  const start = now.getMonth() >= 7 ? now.getFullYear() : now.getFullYear() - 1;
  return `${start}/${start + 1}`;
}

function NewClassForm({
  schoolId,
  sessions,
  defaultSessionId,
  autoFocus,
  onCreated,
  onCancel,
}: {
  schoolId: string;
  sessions: SaSessionWithArms[];
  defaultSessionId: string;
  autoFocus?: boolean;
  onCreated: (result: SaSchoolClassCreated) => void;
  onCancel?: () => void;
}) {
  const createClass = useSaCreateSchoolClass(schoolId);
  const [sessionChoice, setSessionChoice] = useState(defaultSessionId || (sessions.length ? sessions[0].id : "new"));
  const [newSessionName, setNewSessionName] = useState(suggestedSessionName);
  const [className, setClassName] = useState("");
  const [error, setError] = useState("");

  const creatingSession = sessions.length === 0 || sessionChoice === "new";

  function submit(event: FormEvent) {
    event.preventDefault();
    const label = className.trim();
    if (!label) {
      setError("Give the class a name, for example JSS 1A.");
      return;
    }
    if (creatingSession && !newSessionName.trim()) {
      setError("Give the academic session a name, for example 2025/2026.");
      return;
    }
    setError("");
    createClass.mutate(
      {
        name: label,
        session_id: creatingSession ? null : sessionChoice,
        session_name: creatingSession ? newSessionName.trim() : null,
      },
      {
        onSuccess: (created) => {
          setClassName("");
          onCreated(created);
        },
        onError: (err) => setError(err.message || "Could not create the class."),
      },
    );
  }

  return (
    <form className="space-y-3" onSubmit={submit}>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label className="text-xs">Academic session</Label>
          {sessions.length === 0 ? (
            <Input
              value={newSessionName}
              onChange={(e) => setNewSessionName(e.target.value)}
              placeholder="2025/2026"
              className="h-9"
              autoFocus={autoFocus}
            />
          ) : (
            <Select
              value={sessionChoice}
              onValueChange={(value) => {
                setSessionChoice(value);
                setError("");
              }}
            >
              <SelectTrigger className="h-9 w-full">
                <SelectValue placeholder="Choose a session" />
              </SelectTrigger>
              <SelectContent>
                {sessions.map((s) => (
                  <SelectItem key={s.id} value={s.id}>
                    {s.name}
                    {s.is_current ? " (current)" : ""}
                  </SelectItem>
                ))}
                <SelectItem value="new">New session...</SelectItem>
              </SelectContent>
            </Select>
          )}
          {sessions.length > 0 && sessionChoice === "new" && (
            <Input
              value={newSessionName}
              onChange={(e) => setNewSessionName(e.target.value)}
              placeholder="2025/2026"
              className="h-9"
            />
          )}
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs">Class name</Label>
          <Input
            value={className}
            onChange={(e) => setClassName(e.target.value)}
            placeholder="JSS 1A"
            className="h-9"
            autoFocus={autoFocus && sessions.length > 0}
          />
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Button type="submit" size="sm" isLoading={createClass.isPending}>
          <Plus className="h-3.5 w-3.5" /> Create class
        </Button>
        {onCancel && (
          <Button type="button" size="sm" variant="ghost" onClick={onCancel} disabled={createClass.isPending}>
            Cancel
          </Button>
        )}
        {error && <p className="text-sm text-destructive">{error}</p>}
      </div>
      {sessions.length === 0 && (
        <p className="text-xs text-muted-foreground">
          This school has no session yet. The session you name here becomes its current one.
        </p>
      )}
    </form>
  );
}

function BackRow({ onChangeSchool }: { onChangeSchool: () => void }) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <Link
        href="/super-admin/schools"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" /> Schools
      </Link>
      <span className="text-muted-foreground/50">/</span>
      <button
        type="button"
        onClick={onChangeSchool}
        className="text-sm font-medium text-primary hover:underline"
      >
        Change school
      </button>
    </div>
  );
}

function ResultPanel({ result }: { result: SaBulkStudentResult }) {
  return (
    <div
      className={
        result.failed
          ? "space-y-3 rounded-2xl border border-amber-500/40 bg-amber-500/10 p-4"
          : "space-y-3 rounded-2xl border border-emerald-500/40 bg-emerald-500/10 p-4"
      }
    >
      <div className="flex flex-wrap items-center gap-3">
        {result.failed ? (
          <AlertTriangle className="h-5 w-5 text-amber-600" />
        ) : (
          <CheckCircle2 className="h-5 w-5 text-emerald-600" />
        )}
        <p className="text-sm font-semibold">
          {fmtNum(result.created)} student{result.created === 1 ? "" : "s"} added to {result.school.name}
          {result.failed > 0 ? `, ${fmtNum(result.failed)} could not be added` : ""}.
        </p>
        <Badge variant={result.failed ? "warning" : "success"}>{result.session.name}</Badge>
      </div>

      {result.students.length > 0 && (
        <div className="max-h-56 overflow-y-auto rounded-lg border bg-card">
          <table className="w-full text-left text-[13px]">
            <thead className="sticky top-0 bg-muted/70 text-[11px] uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-3 py-1.5 font-semibold">Student</th>
                <th className="px-3 py-1.5 font-semibold">Admission no.</th>
                <th className="px-3 py-1.5 font-semibold">Class</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {result.students.map((s) => (
                <tr key={s.id}>
                  <td className="px-3 py-1.5 font-medium">{s.full_name}</td>
                  <td className="px-3 py-1.5 font-mono text-xs">{s.admission_no}</td>
                  <td className="px-3 py-1.5 text-muted-foreground">{s.class_arm_name}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {result.errors.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-300">
            Not added
          </p>
          <ul className="space-y-0.5 text-[13px]">
            {result.errors.map((err) => (
              <li key={err.index} className="text-muted-foreground">
                <span className="font-medium text-foreground">{err.full_name || `Row ${err.index + 1}`}</span>: {err.message}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}