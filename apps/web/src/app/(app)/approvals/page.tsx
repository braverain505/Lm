"use client";

import type { WorkbenchRow } from "@clearis/shared";
import { Check, Loader2, Lock, Search } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { ReadinessBar } from "@/components/readiness-bar";
import {
  ACTION_PAST,
  ArmRail,
  BatchProgress,
  STAGE_META,
  STAGE_ORDER,
  StageTabs,
  SubjectRow,
  byReviewOrder,
  cellStage,
  isEntered,
  needsAction,
  nextStep,
  pct,
  summarise,
  type Action,
  type StageFilter,
} from "@/components/results/workbench";
import { useToast } from "@/components/toast";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useCompile, useResultAction, useSessions, useTerms, useWorkbench, type ReviewInput } from "@/hooks/use-api";
import { cn } from "@/lib/utils";

/**
 * The result pipeline desk: teacher entry → verify → approve → publish.
 *
 * A term holds every arm × subject cell the school offers, which is far too
 * much to pour down one page — so this screen shows one class and one stage at
 * a time. The rail on the left carries each class's pipeline progress and how
 * much of it is waiting on a human; the pane on the right lists only the cells
 * that match the selected stage, most actionable first, each with its own entry
 * progress bar. Bulk generation reports progress as it runs.
 */
export default function ProcessResultsPage() {
  const { data: sessions = [] } = useSessions();
  const current = sessions.find((s) => s.is_current) ?? sessions[0];
  const { data: terms = [] } = useTerms(current?.id ?? null);
  const [activeTermId, setActiveTermId] = useState<string | null>(null);
  const term = terms.find((t) => t.id === activeTermId) ?? terms.find((t) => t.is_current) ?? terms[0];
  const selectedTermClosed = term?.status === "closed";
  const activeTermIdKey = term?.id ?? activeTermId;

  const { data: rows = [], isLoading, error } = useWorkbench(activeTermIdKey ?? null);
  const validating = useResultAction("verify");
  const approving = useResultAction("approve");
  const publishing = useResultAction("publish");
  const rejecting = useResultAction("reject");
  const compiling = useCompile();
  const busy =
    validating.isPending || approving.isPending || publishing.isPending || rejecting.isPending || compiling.isPending;

  const [selectedArmId, setSelectedArmId] = useState<string | null>(null);
  const [stageFilter, setStageFilter] = useState<StageFilter>("action");
  const [query, setQuery] = useState("");
  const [rejectingKey, setRejectingKey] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [actionError, setActionError] = useState<{ key: string; message: string } | null>(null);
  const [processError, setProcessError] = useState<string | null>(null);
  const [batch, setBatch] = useState<{ done: number; total: number; failed: number } | null>(null);
  const { toast } = useToast();

  const keyOf = (row: WorkbenchRow) => `${row.arm_id}:${row.subject_id}`;
  const cellOf = (row: WorkbenchRow): ReviewInput["cell"] => ({
    arm_id: row.arm_id,
    subject_id: row.subject_id,
    term_id: row.term_id,
  });

  // ── Classes, with their own progress ────────────────────────────────────
  const arms = useMemo(() => {
    const byArm = new Map<string, WorkbenchRow[]>();
    rows.forEach((row) => {
      const list = byArm.get(row.arm_id) ?? [];
      list.push(row);
      byArm.set(row.arm_id, list);
    });
    return [...byArm.entries()]
      .map(([id, list]) => ({ id, name: list[0].arm_name, totals: summarise(list) }))
      .sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }));
  }, [rows]);

  const selectedArm = arms.find((arm) => arm.id === selectedArmId) ?? arms[0] ?? null;

  // Open on the class with the most work waiting — that is what the caller came
  // for — but only once per term, so it never fights a manual selection.
  const pickedFor = useRef<string | null>(null);
  useEffect(() => {
    if (!term?.id || arms.length === 0 || pickedFor.current === term.id) return;
    pickedFor.current = term.id;
    const busiest = [...arms].sort((a, b) => b.totals.action - a.totals.action)[0];
    setSelectedArmId(busiest.totals.action > 0 ? busiest.id : arms[0].id);
    setStageFilter("action");
  }, [arms, term?.id]);

  const overall = useMemo(() => summarise(rows), [rows]);
  const armRows = useMemo(
    () => (selectedArm ? rows.filter((row) => row.arm_id === selectedArm.id) : []),
    [rows, selectedArm],
  );

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return armRows
      .filter((row) => {
        if (needle && !row.subject_name.toLowerCase().includes(needle)) return false;
        if (stageFilter === "all") return true;
        if (stageFilter === "action") return needsAction(row);
        return cellStage(row) === stageFilter;
      })
      .sort(byReviewOrder);
  }, [armRows, query, stageFilter]);

  const readyCount = useMemo(() => rows.filter(isEntered).length, [rows]);

  /** Which mutation is running *for this row* — not a global spinner. */
  const pendingFor = (row: WorkbenchRow): "compile" | Action | "reject" | null => {
    const key = keyOf(row);
    const matches = (cell?: { arm_id: string; subject_id: string }) => !!cell && `${cell.arm_id}:${cell.subject_id}` === key;
    if (compiling.isPending && matches(compiling.variables)) return "compile";
    if (rejecting.isPending && matches(rejecting.variables?.cell)) return "reject";
    if (validating.isPending && matches(validating.variables?.cell)) return "verify";
    if (approving.isPending && matches(approving.variables?.cell)) return "approve";
    if (publishing.isPending && matches(publishing.variables?.cell)) return "publish";
    return null;
  };

  const fail = (key: string, message: string) => setActionError({ key, message });

  const run = (action: Action, row: WorkbenchRow) => {
    if (nextStep(row)?.action !== action) return;
    setActionError(null);
    const mutation = action === "verify" ? validating : action === "approve" ? approving : publishing;
    mutation.mutate(
      { cell: cellOf(row) },
      {
        onSuccess: () => toast(`${row.subject_name}: ${ACTION_PAST[action]} ✓`),
        onError: (err: unknown) =>
          fail(keyOf(row), err instanceof Error ? err.message : `Could not ${action} ${row.subject_name}`),
      },
    );
  };

  const generate = (row: WorkbenchRow) => {
    setActionError(null);
    compiling.mutate(cellOf(row), {
      onSuccess: () => toast(`Result generated for ${row.subject_name}`),
      onError: (err: unknown) =>
        fail(keyOf(row), err instanceof Error ? err.message : `Could not generate ${row.subject_name}`),
    });
  };

  const bounce = (row: WorkbenchRow) => {
    setActionError(null);
    rejecting.mutate(
      { cell: cellOf(row), reason: reason.trim() },
      {
        onSettled: () => setRejectingKey(null),
        onSuccess: () => toast(`Bounced ${row.subject_name} to draft`),
        onError: (err: unknown) =>
          fail(keyOf(row), err instanceof Error ? err.message : `Could not reject ${row.subject_name}`),
      },
    );
  };

  /** Generate every complete-but-unprocessed cell, reporting progress as it goes. */
  const processReady = async () => {
    const ready = rows.filter(isEntered);
    if (ready.length === 0) return;
    const noun = ready.length === 1 ? "result" : "results";
    if (!window.confirm(`Generate and publish ${ready.length} complete ${noun}?`)) return;
    setActionError(null);
    setProcessError(null);
    setBatch({ done: 0, total: ready.length, failed: 0 });
    let failed = 0;
    for (let i = 0; i < ready.length; i += 1) {
      try {
        await compiling.mutateAsync(cellOf(ready[i]));
      } catch {
        failed += 1;
      }
      setBatch({ done: i + 1, total: ready.length, failed });
    }
    if (failed === 0) {
      toast(`Processed ${ready.length} ${noun} ✓`);
    } else {
      setProcessError(`Could not process ${failed} of ${ready.length} ${noun}.`);
      toast(`Failed to process ${failed} ${failed === 1 ? "result" : "results"}`, "error");
    }
  };

  const termPct = pct(overall.published, overall.enrolled);

  return (
    <div className="space-y-5">
      {/* ── Header ─────────────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-[22px] font-bold tracking-tight text-foreground">Process results</h1>
          <p className="mt-1 text-[13px] text-muted-foreground">
            Walk results from teacher entry to published — one class and one stage at a time. Every step is journaled.
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          {selectedTermClosed && (
            <span className="inline-flex items-center gap-2 rounded-xl border border-warning/20 bg-warning/5 px-3 py-2 text-[12px] text-warning">
              <Lock className="h-3.5 w-3.5 shrink-0" />
              This term is closed — actions are disabled.
            </span>
          )}
          <Button onClick={processReady} disabled={busy || selectedTermClosed || readyCount === 0}>
            {compiling.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
            Process ready results{readyCount > 0 ? ` (${readyCount})` : ""}
          </Button>
        </div>
      </div>
      {processError && <p className="text-[12px] text-destructive">{processError}</p>}

      {/* ── Term ───────────────────────────────────────────────────────── */}
      {terms.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="mr-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/60">Term</span>
          {terms.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => {
                setActiveTermId(t.id);
                setSelectedArmId(null);
                setQuery("");
                setRejectingKey(null);
                pickedFor.current = null;
              }}
              aria-pressed={t.id === term?.id}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-[12px] font-medium transition-colors duration-150",
                t.id === term?.id
                  ? "border-primary/40 bg-primary/10 text-primary"
                  : "border-border/60 text-muted-foreground hover:bg-muted/50 hover:text-foreground",
              )}
            >
              {t.name}
              {t.status === "closed" && <Lock className="h-3 w-3" />}
            </button>
          ))}
        </div>
      )}

      {/* ── Live batch ─────────────────────────────────────────────────── */}
      {batch && (
        <BatchProgress
          done={batch.done}
          total={batch.total}
          failed={batch.failed}
          onDismiss={() => setBatch(null)}
        />
      )}

      {isLoading ? (
        <div className="grid gap-5 lg:grid-cols-[minmax(0,255px)_minmax(0,1fr)]">
          <Skeleton className="h-72 rounded-2xl" />
          <div className="space-y-2">
            <Skeleton className="h-9 w-64 rounded-lg" />
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-[72px] rounded-xl" />
            ))}
          </div>
        </div>
      ) : error ? (
        <Card>
          <CardContent className="py-12 text-center text-destructive">
            Could not load the approval workbench. {String(error)}
          </CardContent>
        </Card>
      ) : rows.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            No results in this term yet. Teachers enter scores, then submit for review.
          </CardContent>
        </Card>
      ) : (
        <>
          {/* ── Term pipeline ──────────────────────────────────────────── */}
          <Card>
            <CardContent className="space-y-3 p-4">
              <div className="flex flex-wrap items-end justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-[13px] font-semibold text-foreground">Term pipeline</p>
                  <p className="mt-0.5 text-[11.5px] text-muted-foreground">
                    {overall.published} of {overall.enrolled} results published · {overall.entered} entered ·{" "}
                    {overall.subjects} subject cells
                  </p>
                </div>
                {overall.action > 0 ? (
                  <Badge variant="warning" className="tabular-nums">
                    {overall.action} cell{overall.action === 1 ? "" : "s"} need action
                  </Badge>
                ) : (
                  <Badge variant="success" className="gap-1">
                    <Check className="h-2.5 w-2.5" />
                    Everything published
                  </Badge>
                )}
              </div>
              <ReadinessBar value={termPct} size="lg" />
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                {STAGE_ORDER.slice(0, 4).map((stage) => (
                  <div key={stage} className="rounded-lg border border-border/50 bg-muted/20 px-2.5 py-2">
                    <p className="text-[10.5px] font-medium uppercase tracking-wider text-muted-foreground/60">
                      {STAGE_META[stage].label}
                    </p>
                    <p className="mt-0.5 text-[15px] font-semibold tabular-nums text-foreground">
                      {overall.stages[stage]}
                    </p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* ── Classes × stages ───────────────────────────────────────── */}
          <div className="grid gap-5 lg:grid-cols-[minmax(0,255px)_minmax(0,1fr)] lg:items-start">
            <ArmRail
              arms={arms}
              selectedId={selectedArm?.id ?? null}
              onSelect={(id) => {
                setSelectedArmId(id);
                setQuery("");
                setRejectingKey(null);
              }}
              className="max-h-[300px] overflow-y-auto lg:sticky lg:top-20 lg:max-h-[calc(100vh-6.5rem)]"
            />

            <div className="min-w-0 space-y-3">
              {selectedArm && (
                <>
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="min-w-0">
                      <h2 className="text-[16px] font-semibold tracking-tight text-foreground">{selectedArm.name}</h2>
                      <p className="mt-0.5 text-[11.5px] text-muted-foreground">
                        {selectedArm.totals.action > 0
                          ? `${selectedArm.totals.action} of ${selectedArm.totals.subjects} subjects waiting on a reviewer`
                          : `All ${selectedArm.totals.subjects} subjects published`}
                      </p>
                    </div>
                    <div className="relative shrink-0">
                      <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground/50" />
                      <Input
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        placeholder="Find a subject…"
                        aria-label="Find a subject"
                        className="h-9 w-[190px] pl-8 text-[12.5px]"
                      />
                    </div>
                  </div>

                  <StageTabs totals={selectedArm.totals} value={stageFilter} onChange={setStageFilter} />

                  {visible.length === 0 ? (
                    <Card>
                      <CardContent className="py-10 text-center text-[13px] text-muted-foreground">
                        {query.trim()
                          ? `No subject in ${selectedArm.name} matches “${query.trim()}”.`
                          : stageFilter === "action"
                            ? `Nothing in ${selectedArm.name} needs your action right now.`
                            : `No subjects in ${STAGE_META[stageFilter as keyof typeof STAGE_META]?.label ?? "this"} stage.`}
                      </CardContent>
                    </Card>
                  ) : (
                    <div className="space-y-2">
                      {visible.map((row) => {
                        const key = keyOf(row);
                        return (
                          <SubjectRow
                            key={key}
                            row={row}
                            pending={pendingFor(row)}
                            disabled={busy || selectedTermClosed}
                            rejecting={rejectingKey === key}
                            reason={reason}
                            onReasonChange={setReason}
                            onAction={(action) => run(action, row)}
                            onCompile={() => generate(row)}
                            onStartReject={() => {
                              setRejectingKey(key);
                              setReason("");
                            }}
                            onCancelReject={() => setRejectingKey(null)}
                            onReject={() => bounce(row)}
                            error={actionError?.key === key ? actionError.message : null}
                          />
                        );
                      })}
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
