"use client";

import type { WorkbenchRow } from "@clearis/shared";
import { Check, CheckCheck, Loader2, RotateCcw, ShieldCheck, Upload, Wand2, X } from "lucide-react";
import type * as React from "react";

import { ReadinessBar } from "@/components/readiness-bar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Pipeline model
// ---------------------------------------------------------------------------

export const STAGE_ORDER = ["draft", "submitted", "verified", "approved", "published"] as const;
export type Stage = (typeof STAGE_ORDER)[number];

export type Action = "verify" | "approve" | "publish";

export const STAGE_META: Record<Stage, { label: string; badge: React.ComponentProps<typeof Badge>["variant"] }> = {
  draft: { label: "In draft", badge: "muted" },
  submitted: { label: "Submitted", badge: "warning" },
  verified: { label: "Verified", badge: "info" },
  approved: { label: "Approved", badge: "default" },
  published: { label: "Published", badge: "success" },
};

export const ACTION_ICON: Record<Action, React.ElementType> = {
  verify: ShieldCheck,
  approve: CheckCheck,
  publish: Upload,
};

/** Rounded percentage that never divides by zero. */
export function pct(part: number, whole: number): number {
  return whole > 0 ? Math.round((part / whole) * 100) : 0;
}

/**
 * Where a cell's work currently sits. Actionable stages win over earlier ones —
 * a cell is "submitted" as long as someone still has to verify it, even if part
 * of the class was entered later. A cell with nothing in flight is either still
 * being entered (draft) or done (published).
 */
export function cellStage(row: WorkbenchRow): Stage {
  if (row.submitted > 0) return "submitted";
  if (row.verified > 0) return "verified";
  if (row.approved > 0) return "approved";
  if (row.draft > 0) return "draft";
  return "published";
}

/** Somebody has to act on this cell: verify, approve or publish it. */
export function needsAction(row: WorkbenchRow): boolean {
  return row.submitted + row.verified + row.approved > 0;
}

/** The one step that moves this cell forward, or null when it is done. */
export function nextStep(row: WorkbenchRow): { action: Action; label: string } | null {
  if (row.submitted > 0) return { action: "verify", label: "Verify submitted" };
  if (row.verified > 0) return { action: "approve", label: "Approve verified" };
  if (row.approved > 0) return { action: "publish", label: "Publish" };
  return null;
}

/** The stage an action lands a cell in, for confirmations. */
export const ACTION_PAST: Record<Action, string> = {
  verify: "verified",
  approve: "approved",
  publish: "published",
};

/** A cell can only be generated once every enrolled student has a score. */
export function isEntered(row: WorkbenchRow): boolean {
  return row.draft > 0 && row.entered === row.enrolled;
}

/**
 * Human work order, not pipeline order: what an approver can act on now comes
 * first, cells still being entered next, finished ones last.
 */
const REVIEW_ORDER: Stage[] = ["submitted", "verified", "approved", "draft", "published"];

export function byReviewOrder(a: WorkbenchRow, b: WorkbenchRow): number {
  const rank = REVIEW_ORDER.indexOf(cellStage(a)) - REVIEW_ORDER.indexOf(cellStage(b));
  return rank !== 0 ? rank : a.subject_name.localeCompare(b.subject_name);
}

export interface Totals {
  /** Cells (arm × subject) in the set. */
  subjects: number;
  enrolled: number;
  entered: number;
  published: number;
  /** Cells waiting on a verifier, approver or publisher. */
  action: number;
  stages: Record<Stage, number>;
}

export function summarise(rows: WorkbenchRow[]): Totals {
  const stages: Record<Stage, number> = { draft: 0, submitted: 0, verified: 0, approved: 0, published: 0 };
  let enrolled = 0;
  let entered = 0;
  let published = 0;
  let action = 0;
  for (const row of rows) {
    enrolled += row.enrolled;
    entered += row.entered;
    published += row.published;
    stages[cellStage(row)] += 1;
    if (needsAction(row)) action += 1;
  }
  return { subjects: rows.length, enrolled, entered, published, action, stages };
}

// ---------------------------------------------------------------------------
// Class rail — one class at a time, never a page-long list of them
// ---------------------------------------------------------------------------

export interface ArmSummary {
  id: string;
  name: string;
  totals: Totals;
}

export function ArmRail({
  arms,
  selectedId,
  onSelect,
  className,
}: {
  arms: ArmSummary[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  className?: string;
}) {
  return (
    <aside
      className={cn("rounded-2xl border border-border/60 bg-card p-2 shadow-xs", className)}
      aria-label="Classes"
    >
      <div className="flex items-center justify-between px-2 py-1.5">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/60">
          Classes
        </span>
        <span className="text-[11px] tabular-nums text-muted-foreground/60">{arms.length}</span>
      </div>
      <div className="space-y-1">
        {arms.map((arm) => {
          const selected = arm.id === selectedId;
          const published = pct(arm.totals.published, arm.totals.enrolled);
          return (
            <button
              key={arm.id}
              type="button"
              onClick={() => onSelect(arm.id)}
              aria-current={selected ? "true" : undefined}
              className={cn(
                "block w-full rounded-xl border px-3 py-2.5 text-left transition-[background-color,border-color] duration-150",
                selected
                  ? "border-primary/40 bg-primary/[0.06]"
                  : "border-transparent hover:border-border/60 hover:bg-muted/40",
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="truncate text-[13px] font-semibold text-foreground">{arm.name}</span>
                {arm.totals.action > 0 ? (
                  <Badge variant="warning" className="shrink-0 tabular-nums">
                    {arm.totals.action} to action
                  </Badge>
                ) : (
                  <Badge variant="success" className="shrink-0 gap-1">
                    <Check className="h-2.5 w-2.5" />
                    Clear
                  </Badge>
                )}
              </div>
              <ReadinessBar size="sm" value={published} className="mt-2" sheen={false} />
              <div className="mt-1 flex items-center justify-between text-[10.5px] text-muted-foreground/70">
                <span>
                  {arm.totals.subjects} subject{arm.totals.subjects === 1 ? "" : "s"}
                </span>
                <span className="tabular-nums">{published}% published</span>
              </div>
            </button>
          );
        })}
      </div>
    </aside>
  );
}

// ---------------------------------------------------------------------------
// Stage filters — work one step of the pipeline at a time
// ---------------------------------------------------------------------------

export type StageFilter = "action" | "all" | Stage;

export function StageTabs({
  totals,
  value,
  onChange,
}: {
  totals: Totals;
  value: StageFilter;
  onChange: (next: StageFilter) => void;
}) {
  const tabs = (
    [
      { key: "action", label: "Needs action", count: totals.action },
      { key: "all", label: "All", count: totals.subjects },
      ...STAGE_ORDER.map((stage) => ({
        key: stage as StageFilter,
        label: STAGE_META[stage].label,
        count: totals.stages[stage],
      })),
    ] satisfies { key: StageFilter; label: string; count: number }[]
  ).filter((tab) => tab.count > 0 || tab.key === "action" || tab.key === "all");

  return (
    <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Filter by stage">
      {tabs.map((tab) => {
        const active = tab.key === value;
        return (
          <button
            key={tab.key}
            type="button"
            onClick={() => onChange(tab.key)}
            aria-pressed={active}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-[12px] font-medium transition-colors duration-150",
              active
                ? "border-primary/40 bg-primary/10 text-primary"
                : "border-border/60 text-muted-foreground hover:bg-muted/50 hover:text-foreground",
            )}
          >
            {tab.label}
            <span className={cn("tabular-nums text-[11px]", active ? "text-primary/70" : "text-muted-foreground/60")}>
              {tab.count}
            </span>
          </button>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Subject row — one cell, its progress, and the single next action
// ---------------------------------------------------------------------------

export function SubjectRow({
  row,
  pending,
  disabled,
  rejecting,
  reason,
  onReasonChange,
  onAction,
  onCompile,
  onStartReject,
  onCancelReject,
  onReject,
  error,
}: {
  row: WorkbenchRow;
  /** Which mutation is running for *this* row, if any. */
  pending: "compile" | Action | "reject" | null;
  disabled: boolean;
  rejecting: boolean;
  /** Message from the last failed action on this row. */
  error?: string | null;
  reason: string;
  onReasonChange: (value: string) => void;
  onAction: (action: Action) => void;
  onCompile: () => void;
  onStartReject: () => void;
  onCancelReject: () => void;
  onReject: () => void;
}) {
  const stage = cellStage(row);
  const step = nextStep(row);
  const busy = pending !== null;
  const entered = pct(row.entered, row.enrolled);

  return (
    <div
      className={cn(
        "rounded-xl border bg-card px-3.5 py-3 transition-[border-color,background-color] duration-150",
        busy ? "border-primary/40 bg-primary/[0.03]" : "border-border/50 hover:border-border",
      )}
    >
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2.5">
        <div className="min-w-[180px] flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate text-[13.5px] font-medium text-foreground">{row.subject_name}</span>
            {row.rejected > 0 && (
              <Badge variant="destructive" className="tabular-nums">
                {row.rejected} bounced
              </Badge>
            )}
          </div>
          <div className="mt-1.5 flex items-center gap-2">
            <ReadinessBar size="sm" value={entered} className="max-w-[150px]" sheen={false} />
            <span className="text-[11px] tabular-nums text-muted-foreground/70">
              {row.entered}/{row.enrolled} entered
              {row.published > 0 ? ` · ${row.published} published` : ""}
            </span>
          </div>
        </div>

        <Badge variant={STAGE_META[stage].badge} className="shrink-0">
          {STAGE_META[stage].label}
        </Badge>

        <div className="ml-auto flex shrink-0 items-center gap-2">
          {isEntered(row) && (
            <Button size="sm" variant="outline" disabled={disabled} onClick={onCompile}>
              {pending === "compile" ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Wand2 className="h-3.5 w-3.5" />
              )}
              Generate card
            </Button>
          )}
          {!rejecting && step && (
            <Button size="sm" disabled={disabled} onClick={() => onAction(step.action)}>
              {pending === step.action ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                (() => {
                  const Icon = ACTION_ICON[step.action];
                  return <Icon className="h-3.5 w-3.5" />;
                })()
              )}
              {step.label}
            </Button>
          )}
          {!rejecting && needsAction(row) && (
            <Button variant="ghost" size="sm" disabled={disabled} onClick={onStartReject}>
              <RotateCcw className="h-3.5 w-3.5" />
              Reject
            </Button>
          )}
        </div>
      </div>

      {error && <p className="mt-2 px-1 text-[11.5px] text-destructive">{error}</p>}

      {rejecting && (
        <div className="mt-3 flex flex-wrap items-end gap-2 rounded-lg border border-destructive/20 bg-destructive/[0.04] p-3">
          <div className="min-w-[220px] flex-1 space-y-1">
            <Label htmlFor={`reason-${row.arm_id}-${row.subject_id}`} className="text-[11.5px]">
              Why is this going back to draft?
            </Label>
            <Input
              id={`reason-${row.arm_id}-${row.subject_id}`}
              value={reason}
              onChange={(e) => onReasonChange(e.target.value)}
              placeholder="e.g. totals look inconsistent"
              className="h-8"
            />
          </div>
          <Button
            size="sm"
            variant="destructive"
            disabled={!reason.trim() || disabled}
            onClick={onReject}
          >
            {pending === "reject" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RotateCcw className="h-3.5 w-3.5" />}
            Bounce to draft
          </Button>
          <Button size="sm" variant="ghost" onClick={onCancelReject}>
            Cancel
          </Button>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Batch progress — visible while cards are being generated
// ---------------------------------------------------------------------------

export function BatchProgress({
  done,
  total,
  failed,
  onDismiss,
}: {
  done: number;
  total: number;
  failed: number;
  onDismiss: () => void;
}) {
  const finished = done >= total;
  const value = pct(done, total);
  return (
    <Card className="border-primary/25 bg-primary/[0.03]">
      <CardContent className="space-y-2.5 p-4">
        <div className="flex items-center justify-between gap-3">
          <p className="text-[13px] font-semibold text-foreground">
            {finished ? "Finished generating result cards" : "Generating result cards…"}
          </p>
          <div className="flex items-center gap-2">
            <span className="text-[12px] tabular-nums text-muted-foreground">
              {done} of {total}
            </span>
            <Button variant="ghost" size="sm" className="h-7 px-1.5" onClick={onDismiss} aria-label="Dismiss">
              <X className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
        <ReadinessBar value={value} size="md" sheen={!finished} />
        {finished && failed > 0 && (
          <p className="text-[11.5px] text-destructive">
            {failed} result{failed === 1 ? "" : "s"} could not be generated — retry them individually below.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
