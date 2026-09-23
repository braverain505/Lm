"use client";

import { Check, Copy, Plus, RotateCcw, Save, Star, Trash2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import type { ReportCardTemplate, ReportLayout } from "@clearis/shared";

import { NoAccess } from "@/components/access-denied";
import { ReportCardDesigner } from "@/components/report-card-designer";
import { useToast } from "@/components/toast";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useCreateReportCardTemplate,
  useDeleteReportCardTemplate,
  useDuplicateReportCardTemplate,
  useReportCardTemplates,
  useSetDefaultReportCardTemplate,
  useUpdateReportCardTemplate,
} from "@/hooks/use-api";
import { cloneLayout, emptyLayout } from "@/lib/report-layout";
import { isSchoolAdminRole } from "@/lib/roles";
import { useAuth } from "@/providers/auth-provider";
import { cn } from "@/lib/utils";

import "@/app/report-card.css";
import "@/app/report-card-templates.css";

/** A design's identity for change detection: the name plus the layout as sent. */
const snapshot = (name: string, layout: ReportLayout) => JSON.stringify({ name, layout });

/**
 * The report card designer.
 *
 * Designing a card is `school.manage` (which the API enforces on every write), so
 * this page is the school admin's. The check below only decides what is
 * rendered: reaching the URL directly still gets a 403 from the API.
 */
export default function ReportCardDesignerPage() {
  const { activeSchool } = useAuth();
  const permissions = activeSchool?.permissions ?? [];
  const role = activeSchool?.role?.code ?? "";

  if (!permissions.includes("school.manage") || !isSchoolAdminRole(role)) {
    return (
      <NoAccess
        title="Report card design is the school admin's"
        message="Only the school owner, director, admin or principal can change what the school's report cards look like. The exam office prints the cards this produces."
        backHref="/reports"
        backLabel="Go to Report Cards"
      />
    );
  }

  return <DesignerWorkspace />;
}

function DesignerWorkspace() {
  const { toast } = useToast();
  const { data: templates = [], isLoading } = useReportCardTemplates();

  const createTemplate = useCreateReportCardTemplate();
  const updateTemplate = useUpdateReportCardTemplate();
  const setDefault = useSetDefaultReportCardTemplate();
  const duplicateTemplate = useDuplicateReportCardTemplate();
  const deleteTemplate = useDeleteReportCardTemplate();

  // What is open in the builder. `saved` is a snapshot of the last server state,
  // so "unsaved changes" is a comparison rather than a flag that can drift.
  const [activeId, setActiveId] = useState<string | null>(null);
  const [name, setName] = useState("New design");
  const [layout, setLayout] = useState<ReportLayout>(() => emptyLayout());
  const [saved, setSaved] = useState("");

  const loadedOnce = useRef(false);

  const active: ReportCardTemplate | null = useMemo(
    () => templates.find((t) => t.id === activeId) ?? null,
    [templates, activeId],
  );

  function openTemplate(template: ReportCardTemplate) {
    setActiveId(template.id);
    setName(template.name);
    setLayout(cloneLayout(template.layout));
    setSaved(snapshot(template.name, template.layout));
  }

  // Open the card the school actually prints, once, when the list arrives. After
  // that the selection is the user's to change — a background refetch must never
  // yank the design they are editing out from under them.
  useEffect(() => {
    if (loadedOnce.current || templates.length === 0) return;
    loadedOnce.current = true;
    openTemplate(templates.find((t) => t.is_default) ?? templates[0]);
  }, [templates]);

  const dirty = JSON.stringify({ name: name.trim(), layout }) !== saved;

  function guardUnsaved(): boolean {
    return !dirty || window.confirm("Discard your unsaved changes to this design?");
  }

  function handleStartNew() {
    if (!guardUnsaved()) return;
    setActiveId(null);
    setName("New design");
    setLayout(emptyLayout());
    setSaved("");
  }

  function handleSave() {
    const trimmed = name.trim();
    if (!trimmed) {
      toast("Give the design a name first", "error");
      return;
    }
    // The API names the offending block on a validation failure, so surface its
    // message rather than a generic one — only the school can fix it.
    const onError = (err: unknown) =>
      toast(err instanceof Error ? err.message : "Could not save the design", "error");

    if (active) {
      updateTemplate.mutate(
        { templateId: active.id, name: trimmed, layout },
        {
          onSuccess: (updated) => {
            setSaved(snapshot(updated.name, updated.layout));
            toast("Design saved");
          },
          onError,
        },
      );
      return;
    }
    createTemplate.mutate(
      { name: trimmed, layout },
      {
        onSuccess: (created) => {
          openTemplate(created);
          toast(
            created.is_default ? "Design saved and set as your report card" : "Design saved",
          );
        },
        onError,
      },
    );
  }

  const busy =
    createTemplate.isPending ||
    updateTemplate.isPending ||
    setDefault.isPending ||
    duplicateTemplate.isPending ||
    deleteTemplate.isPending;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Report card designer</h1>
          <p className="max-w-2xl text-sm text-muted-foreground/60">
            Build your school&apos;s report card from blocks. Drag to reorder, click a block to
            change its settings, and preview the A4 card before you save. Every card — printed,
            on screen and on the parent portal — then uses the design marked{" "}
            <strong>in use</strong>.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" onClick={handleStartNew} disabled={busy}>
            <Plus className="h-4 w-4" /> New design
          </Button>
          {active && (
            <Button
              variant="outline"
              disabled={busy || active.is_default}
              onClick={() =>
                setDefault.mutate(active.id, {
                  onSuccess: () => toast("This is now your report card"),
                  onError: () => toast("Could not set the default", "error"),
                })
              }
            >
              <Star className="h-4 w-4" />
              {active.is_default ? "Current card" : "Use for all cards"}
            </Button>
          )}
          <Button onClick={handleSave} disabled={busy || (!dirty && !!active)} isLoading={busy}>
            {!busy && <Save className="h-4 w-4" />}
            Save
          </Button>
        </div>
      </div>

      {isLoading ? (
        <Skeleton className="h-96 w-full" />
      ) : (
        <div className="grid gap-4 xl:grid-cols-[17rem_minmax(0,1fr)]">
          {/* Saved designs */}
          <Card className="h-fit">
            <CardContent className="p-3">
              <p className="px-1 pb-2 text-[12.5px] font-semibold">
                Your designs{" "}
                <span className="font-normal text-muted-foreground/60">({templates.length})</span>
              </p>

              {templates.length === 0 ? (
                <p className="rounded-lg border border-dashed border-border/70 px-3 py-6 text-center text-[12px] text-muted-foreground/60">
                  No designs yet. Save this one and it becomes your report card.
                </p>
              ) : (
                <div className="space-y-1">
                  {templates.map((t) => (
                    <div
                      key={t.id}
                      className={cn(
                        "group flex items-center gap-1.5 rounded-lg border px-2.5 py-2 transition-colors",
                        t.id === activeId
                          ? "border-primary/50 bg-primary/[0.04]"
                          : "border-transparent hover:bg-accent",
                      )}
                    >
                      <button
                        type="button"
                        onClick={() => {
                          if (t.id === activeId || guardUnsaved()) openTemplate(t);
                        }}
                        className="min-w-0 flex-1 text-left"
                      >
                        <span className="flex items-center gap-1.5">
                          <span className="truncate text-[12.5px] font-medium">{t.name}</span>
                          {t.is_default && (
                            <Badge variant="success">
                              <Check className="h-2.5 w-2.5" /> in use
                            </Badge>
                          )}
                        </span>
                        <span className="block text-[10.5px] text-muted-foreground/50">
                          {t.layout.widgets.length} block
                          {t.layout.widgets.length === 1 ? "" : "s"} · {t.layout.theme}
                        </span>
                      </button>
                      <button
                        type="button"
                        aria-label={`Duplicate ${t.name}`}
                        title="Duplicate"
                        onClick={() =>
                          duplicateTemplate.mutate(t.id, {
                            // Not auto-opened: that would throw away whatever the
                            // admin is working on. The copy appears in the list.
                            onSuccess: (copy) => toast(`Copied as "${copy.name}"`),
                            onError: () => toast("Could not copy the design", "error"),
                          })
                        }
                        className="rounded p-1 text-muted-foreground/50 opacity-0 transition-opacity hover:bg-accent hover:text-foreground group-hover:opacity-100"
                      >
                        <Copy className="h-3.5 w-3.5" />
                      </button>
                      <button
                        type="button"
                        aria-label={`Delete ${t.name}`}
                        title={t.is_default ? "Delete (another design takes over)" : "Delete"}
                        onClick={() => {
                          if (
                            !window.confirm(
                              t.is_default
                                ? `Delete "${t.name}"? It is the design your cards use now — another design takes over.`
                                : `Delete "${t.name}"?`,
                            )
                          ) {
                            return;
                          }
                          deleteTemplate.mutate(t.id, {
                            onSuccess: () => {
                              toast("Design deleted");
                              if (activeId === t.id) {
                                setActiveId(null);
                                setSaved("");
                                setName("New design");
                                setLayout(emptyLayout());
                              }
                            },
                            onError: () => toast("Could not delete the design", "error"),
                          });
                        }}
                        className="rounded p-1 text-muted-foreground/50 opacity-0 transition-opacity hover:bg-destructive/10 hover:text-destructive group-hover:opacity-100"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              )}

              <p className="mt-3 rounded-lg bg-muted/50 px-2.5 py-2 text-[11px] leading-snug text-muted-foreground/70">
                Designs are shared across the school: the exam office, class teachers and the
                parent result portal all render the design marked <strong>in use</strong>.
              </p>
            </CardContent>
          </Card>

          {/* The builder */}
          <div className="space-y-3">
            <Card>
              <CardContent className="flex flex-wrap items-end gap-3 p-3">
                <div className="min-w-[14rem] flex-1 space-y-1">
                  <Label htmlFor="design-name">Design name</Label>
                  <Input
                    id="design-name"
                    value={name}
                    placeholder="e.g. Secondary school card"
                    onChange={(e) => setName(e.target.value)}
                  />
                </div>
                <div className="flex items-center gap-2 pb-1">
                  {!active ? (
                    <Badge variant="info">New design</Badge>
                  ) : dirty ? (
                    <Badge variant="warning">Unsaved changes</Badge>
                  ) : (
                    <Badge variant="muted">
                      <Check className="h-2.5 w-2.5" /> Saved
                    </Badge>
                  )}
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={!dirty || !active}
                    onClick={() => {
                      if (active) openTemplate(active);
                    }}
                  >
                    <RotateCcw className="h-3.5 w-3.5" /> Revert
                  </Button>
                </div>
              </CardContent>
            </Card>

            <ReportCardDesigner
              layout={layout}
              onChange={setLayout}
              onDuplicateWidgetHint={(message) => toast(message, "info")}
            />
          </div>
        </div>
      )}
    </div>
  );
}
