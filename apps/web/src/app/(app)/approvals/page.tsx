"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useCompile, useResultAction, useSessions, useTerms, useWorkbench, type ReviewInput } from "@/hooks/use-api";
import { Check, Loader2, RotateCcw, X } from "lucide-react";
import type { WorkbenchRow } from "@schoolos/shared";
import { cn } from "@/lib/utils";

type NextStep = { action: "verify" | "approve" | "publish"; label: string } | null;

function nextStep(row: WorkbenchRow): NextStep {
  if (row.submitted > 0) return { action: "verify", label: "Verify submitted" };
  if (row.verified > 0) return { action: "approve", label: "Approve verified" };
  if (row.approved > 0) return { action: "publish", label: "Publish" };
  return null;
}

function inFlight(row: WorkbenchRow): boolean {
  return row.submitted + row.verified + row.approved > 0;
}

interface StagePillProps {
  label: string;
  count: number;
  tone: "success" | "warning" | "muted" | "destructive" | "default";
}

function StagePill({ label, count, tone }: StagePillProps) {
  if (count === 0) return null;
  return (
    <Badge variant={tone} className="gap-1">
      <span className="tabular-nums">{count}</span> {label}
    </Badge>
  );
}

export default function ApprovalsPage() {
  const { data: sessions = [] } = useSessions();
  const current = sessions.find((s) => s.is_current) ?? sessions[0];
  const { data: terms = [] } = useTerms(current?.id ?? null);
  const [activeTermId, setActiveTermId] = useState<string | null>(null);
  const term = terms.find((t) => t.id === activeTermId) ?? terms.find((t) => t.is_current) ?? terms[0];
  const activeTermIdKey = term?.id ?? activeTermId;

  const { data: rows = [], isLoading, error } = useWorkbench(activeTermIdKey ?? null);
  const validating = useResultAction("verify");
  const approving = useResultAction("approve");
  const publishing = useResultAction("publish");
  const rejecting = useResultAction("reject");
  const compiling = useCompile();
  const busy = validating.isPending || approving.isPending || publishing.isPending || rejecting.isPending || compiling.isPending;

  const [rejectingKey, setRejectingKey] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [processError, setProcessError] = useState<string | null>(null);

  const grouped = new Map<string, WorkbenchRow[]>();
  rows.forEach((r) => {
    const list = grouped.get(r.arm_name) ?? [];
    list.push(r);
    grouped.set(r.arm_name, list);
  });

  const cellOf = (r: WorkbenchRow): ReviewInput["cell"] => ({
    arm_id: r.arm_id,
    subject_id: r.subject_id,
    term_id: r.term_id,
  });

  const run = (action: "verify" | "approve" | "publish", r: WorkbenchRow) => {
    const step = nextStep(r);
    if (step?.action === action) {
      const fn = action === "verify" ? validating : action === "approve" ? approving : publishing;
      fn.mutate({ cell: cellOf(r) });
    }
  };

  const processReady = () => {
    const ready = rows.filter((row) => row.draft > 0 && row.entered === row.enrolled);
    if (ready.length === 0) return;
    if (!window.confirm(`Process and publish ${ready.length} complete result${ready.length === 1 ? "" : "s"}?`)) return;
    setProcessError(null);
    ready
      .reduce(
            (chain, row) => chain.then(() => compiling.mutateAsync(cellOf(row)).then(() => undefined)),
        Promise.resolve(),
      )
      .catch((error: unknown) => {
        setProcessError(error instanceof Error ? error.message : "Could not process all ready results");
      });
  };

  return (
    <div className="space-y-6">
      <div>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Result approvals</h1>
            <p className="text-sm text-muted-foreground">
              Move results from teacher entry to published — verifiers, approvers, and publishers act here.
              Every step is journaled.
            </p>
          </div>
          <Button
            disabled={busy || rows.every((row) => row.draft === 0 || row.entered !== row.enrolled)}
            onClick={processReady}
          >
            {compiling.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
            Process ready results
          </Button>
          {processError && <p className="w-full text-right text-xs text-destructive">{processError}</p>}
        </div>
      </div>

      {/* Term picker */}
      {terms.length > 0 ? (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm text-muted-foreground">Term</span>
          {terms.map((t) => (
            <button
              key={t.id}
              onClick={() => setActiveTermId(t.id)}
              className={cn(
                "rounded-md border px-3 py-1.5 text-sm font-medium transition-colors",
                t.id === term?.id
                  ? "border-primary bg-primary/10 text-primary"
                  : "border-input text-muted-foreground hover:bg-accent",
              )}
            >
              {t.name}
            </button>
          ))}
        </div>
      ) : null}

      {isLoading ? (
        <Skeleton className="h-48 w-full" />
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
        [...grouped.entries()].map(([armName, armRows]) => (
          <Card key={armName}>
            <CardHeader>
              <CardTitle>{armName}</CardTitle>
              <CardDescription>
                {armRows.filter(inFlight).length} subject{armRows.filter(inFlight).length === 1 ? "" : "s"} awaiting
                review
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 p-4">
              {armRows.map((row) => {
                const key = `${row.arm_id}:${row.subject_id}`;
                const step = nextStep(row);
                const isRejecting = rejectingKey === key;
                return (
                  <div
                    key={key}
                    className="flex flex-wrap items-center gap-3 rounded-lg border bg-card/50 px-3 py-2.5"
                  >
                    <div className="flex-1 text-sm font-medium">{row.subject_name}</div>

                    <StagePill label="draft" count={row.draft} tone="muted" />
                    <StagePill label="submitted" count={row.submitted} tone="warning" />
                    <StagePill label="verified" count={row.verified} tone="default" />
                    <StagePill label="approved" count={row.approved} tone="default" />
                    <StagePill label="bounced" count={row.rejected} tone="destructive" />
                    <StagePill label="published" count={row.published} tone="success" />

                    <div className="ml-auto flex items-center gap-2">
                      {row.draft > 0 && row.entered === row.enrolled && (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={busy}
                          onClick={() => compiling.mutate(cellOf(row))}
                        >
                          {compiling.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
                          Generate card
                        </Button>
                      )}
                      {!isRejecting && step && (
                        <Button
                          size="sm"
                          disabled={busy}
                          onClick={() => run(step.action, row)}
                        >
                          {(() => {
                            const pending =
                              (step.action === "verify" && validating.isPending) ||
                              (step.action === "approve" && approving.isPending) ||
                              (step.action === "publish" && publishing.isPending);
                            return pending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />;
                          })()}
                          {step.label}
                        </Button>
                      )}
                      {!isRejecting && inFlight(row) && (
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={busy}
                          onClick={() => {
                            setRejectingKey(key);
                            setReason("");
                          }}
                        >
                          <RotateCcw className="h-3.5 w-3.5" />
                          Reject
                        </Button>
                      )}
                      {isRejecting && (
                        <div className="flex items-center gap-2">
                          <div className="space-y-1">
                            <Label htmlFor={`reason-${key}`} className="text-xs">
                              Reason for bouncing to draft
                            </Label>
                            <Input
                              id={`reason-${key}`}
                              value={reason}
                              onChange={(e) => setReason(e.target.value)}
                              placeholder="e.g. totals look inconsistent"
                              className="h-8 w-64"
                            />
                          </div>
                          <Button
                            size="sm"
                            variant="destructive"
                            disabled={!reason.trim() || rejecting.isPending}
                            onClick={() => {
                              rejecting.mutate(
                                { cell: cellOf(row), reason: reason.trim() },
                                { onSettled: () => setRejectingKey(null) },
                              );
                            }}
                          >
                            {rejecting.isPending ? (
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            ) : (
                              <RotateCcw className="h-3.5 w-3.5" />
                            )}
                            Bounce
                          </Button>
                          <Button size="sm" variant="ghost" onClick={() => setRejectingKey(null)}>
                            Cancel
                          </Button>
                        </div>
                      )}
                    </div>
                    {(validating.error || approving.error || publishing.error || rejecting.error) && (
                      <div className="w-full text-xs text-destructive">
                        {(validating.error ?? approving.error ?? publishing.error ?? rejecting.error)?.message}
                      </div>
                    )}
                  </div>
                );
              })}
            </CardContent>
          </Card>
        ))
      )}
    </div>
  );
}