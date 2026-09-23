"use client";

import { Download, Files, PenLine, Printer, X } from "lucide-react";
import { motion } from "framer-motion";
import { useCallback, useRef, useState } from "react";

import type { ReportTheme } from "@clearis/shared";

const ease = [0.25, 0.46, 0.45, 0.94] as const;

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import Link from "next/link";

import { CommentManager } from "@/components/comment-manager";
import { ReportCardDocument } from "@/components/report-card-document";
import { ResultCodeCard } from "@/components/result-codes-card";
import {
  useArms,
  useCreateReportCardTemplate,
  useReportCard,
  useReportCardDesign,
  useReportCards,
  useReportIndex,
  useSessions,
  useTerms,
  useUpdateReportCardTemplate,
} from "@/hooks/use-api";
import { cn } from "@/lib/utils";
import { downloadPdf, downloadBulkPdf } from "@/lib/pdf";
import { useToast } from "@/components/toast";
import "@/app/report-card.css";
import "@/app/report-card-templates.css";
import { ReportTemplatePicker } from "@/components/report-template-picker";
import { useAuth } from "@/providers/auth-provider";
import { isSchoolAdminRole } from "@/lib/roles";
import { NoAccess } from "@/components/access-denied";
import { REPORT_CARD_PERM } from "@/components/nav-config";

/**
 * Report cards belong to the school's Exam Office: the Exam Officer, the
 * Principal, VP Academics and the school/ platform admins. A teacher — who may
 * enter and read their own scoresheets — must not open another teacher's
 * subject marks through a card.
 *
 * The permission check below only decides what is rendered; the API enforces
 * ``results.report_card`` on every report-card endpoint, so reaching this URL
 * directly still yields a 403 for a teacher rather than somebody's card.
 */
export default function ReportsPage() {
  const { activeSchool } = useAuth();
  const permissions = activeSchool?.permissions ?? [];

  if (!permissions.includes(REPORT_CARD_PERM)) {
    return (
      <NoAccess
        title="Report cards are the Exam Office's desk"
        message="Only the Exam Officer and school leadership can open report cards. You can still enter and review your own scoresheets from Results."
        backHref="/results"
        backLabel="Go to Results"
      />
    );
  }

  return <ReportsWorkspace />;
}

function ReportsWorkspace() {
  const { activeSchool } = useAuth();
  const role = activeSchool?.role?.code ?? "";
  const isHomeroomTeacher = role === "homeroom_teacher";
  const isAdmin = isSchoolAdminRole(role);
  const { data: sessions = [] } = useSessions();
  const current = sessions.find((s) => s.is_current) ?? sessions[0];
  const { data: terms = [] } = useTerms(current?.id ?? null);
  const { data: arms = [] } = useArms(current?.id ?? null);

  const [activeTermId, setActiveTermId] = useState<string | null>(null);
  const term = terms.find((t) => t.id === activeTermId) ?? terms.find((t) => t.is_current) ?? terms[0];
  const [armId, setArmId] = useState("");
  const [studentId, setStudentId] = useState<string | null>(null);
  const [bulkOpen, setBulkOpen] = useState(false);

  // The design every card on this page is drawn in. It comes from the school's
  // saved template (a card is the school's document, not this browser's), so the
  // exam office, a teacher and a parent all see the same card.
  const { data: design } = useReportCardDesign();
  const updateTemplate = useUpdateReportCardTemplate();
  const createTemplate = useCreateReportCardTemplate();
  const themeBusy = updateTemplate.isPending || createTemplate.isPending;

  /**
   * Change the card style from here.
   *
   * A style belongs to the school's saved design, so this writes the design
   * rather than a browser preference — and a school that has never saved one gets
   * its first design created from this click, rather than a style that applies to
   * nothing.
   */
  function handleThemeChange(theme: ReportTheme) {
    if (!design || design.theme === theme || themeBusy) return;
    const layout = { ...design.layout, theme };
    const onError = () => toast("Could not update the card style", "error");
    if (design.template_id) {
      updateTemplate.mutate(
        { templateId: design.template_id, layout },
        { onSuccess: () => toast("Card style updated for the school"), onError },
      );
      return;
    }
    createTemplate.mutate(
      { name: "School report card", layout, is_default: true },
      { onSuccess: () => toast("Card style saved for the school"), onError },
    );
  }

  const { data: index = [], isLoading: indexLoading } = useReportIndex(armId || null, term?.id ?? null);
  const { data: card, isLoading: cardLoading, error } = useReportCard(studentId, term?.id ?? null);
  const {
    data: bulkCards = [],
    isLoading: bulkLoading,
    isFetching: bulkFetching,
  } = useReportCards(bulkOpen ? armId : null, bulkOpen ? term?.id ?? null : null);

  const { toast } = useToast();
  const reportCardRef = useRef<HTMLDivElement>(null);
  const bulkRefs = useRef<Map<string, HTMLDivElement>>(new Map());

  const handleDownloadSingle = useCallback(async () => {
    const el = reportCardRef.current;
    if (!el || !card) return;
    try {
      await downloadPdf(el, `report-card-${card.student.admission_no}.pdf`);
      toast("Report card downloaded");
    } catch {
      toast("Failed to generate PDF", "error");
    }
  }, [card, toast]);

  const handleDownloadBulk = useCallback(async () => {
    const els = Array.from(bulkRefs.current.values());
    if (els.length === 0) return;
    try {
      await downloadBulkPdf(els, `report-cards-${armId}.pdf`);
      toast(`${els.length} report cards downloaded`);
    } catch {
      toast("Failed to generate PDF", "error");
    }
  }, [armId, toast]);

  return (
    <div className="space-y-6 print:space-y-0">
      {/* Toolbar (hidden on print) */}
      <div className="print:hidden">
        <motion.div
          className="flex items-start justify-between gap-4"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.04, ease }}
        >
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Report cards</h1>
            <p className="text-sm text-muted-foreground/50">
              Premium printable term reports built from published results — totals are frozen at
              publish, so cards never drift.
            </p>
          </div>
          <div className="flex items-center gap-2">
            {bulkOpen ? (
              <Button variant="outline" onClick={() => setBulkOpen(false)}>
                <X className="h-4 w-4" /> Back to one card
              </Button>
            ) : (
              <>
                {armId && term && (
                  <Button
                    variant="outline"
                    onClick={() => {
                      setBulkOpen(true);
                      setStudentId(null);
                    }}
                  >
                    <Files className="h-4 w-4" /> All report cards
                    {!indexLoading && index.length > 0 && (
                      <span className="text-muted-foreground/50">({index.filter((r) => r.subjects_published > 0).length})</span>
                    )}
                  </Button>
                )}
                {card && (
                  <>
                    <Button variant="outline" onClick={() => window.print()}>
                      <Printer className="h-4 w-4" /> Print
                    </Button>
                    <Button onClick={handleDownloadSingle}>
                      <Download className="h-4 w-4" /> Download PDF
                    </Button>
                  </>
                )}
              </>
            )}
          </div>
        </motion.div>

        {/* Term + arm filters */}
        <motion.div
          className="mt-4 flex flex-wrap items-center gap-4"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.08, ease }}
        >
          {terms.length > 0 && (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm text-muted-foreground/50">Term</span>
              {terms.map((t) => (
                <button
                  key={t.id}
                  onClick={() => setActiveTermId(t.id)}
                  className={cn(
                    "rounded-md border px-3 py-1.5 text-sm font-medium transition-all duration-200",
                    t.id === term?.id
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-input text-muted-foreground/50 hover:bg-accent",
                  )}
                >
                  {t.name}
                </button>
              ))}
            </div>
          )}
          <div className="space-y-1">
            <Label htmlFor="arm">Class arm</Label>
            <select
              id="arm"
              className="h-9 w-56 rounded-md border border-input bg-transparent px-3 text-sm"
              value={armId}
              onChange={(e) => {
                setArmId(e.target.value);
                setStudentId(null);
                setBulkOpen(false);
              }}
            >
              <option value="">Choose arm…</option>
              {arms.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.full_name}
                </option>
              ))}
            </select>
          </div>
        </motion.div>

        {/* Arm index: students + publish coverage */}
        {armId && term && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: 0.12, ease }}
          >
            <Card className="mt-4 transition-all duration-200 hover:-translate-y-[1px] hover:shadow-card">
              <CardHeader className="px-5 py-3.5">
                <CardTitle>Students in this arm</CardTitle>
              </CardHeader>
              <CardContent>
                {indexLoading ? (
                  <Skeleton className="h-32 w-full" />
                ) : index.length === 0 ? (
                  <p className="text-sm text-muted-foreground/50">No enrollments in this arm.</p>
                ) : (
                  <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                    {index.map((row, idx) => (
                      <motion.button
                        key={row.student_id}
                        onClick={() => setStudentId(row.student_id)}
                        className={cn(
                          "flex items-center justify-between gap-2 rounded-lg border px-3 py-2 text-left text-sm transition-all duration-200",
                          row.student_id === studentId
                            ? "border-primary bg-primary/10"
                            : "border-input hover:bg-accent hover:-translate-y-[1px]",
                        )}
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.35, delay: 0.16 + idx * 0.04, ease }}
                      >
                        <span className="font-medium">{row.full_name}</span>
                        {row.subjects_published > 0 ? (
                          <Badge variant="success">
                            {row.subjects_published} subject{row.subjects_published === 1 ? "" : "s"} ready
                          </Badge>
                        ) : (
                          <Badge variant="muted">pending</Badge>
                        )}
                      </motion.button>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </motion.div>
        )}
      </div>

      {/* Result codes: the credential the Exam Office issues for parents. */}
      <div className="print:hidden">
        <ResultCodeCard />
      </div>

      {/* Card style + a way into the designer (admin/principal only, hidden on print) */}
      {isAdmin && (
        <motion.div
          className="print:hidden"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.12, ease }}
        >
          <Card className="transition-all duration-200 hover:-translate-y-[1px] hover:shadow-card">
            <CardContent className="space-y-4 py-5">
              <ReportTemplatePicker
                value={design?.theme ?? "classic"}
                onChange={handleThemeChange}
                disabled={themeBusy}
              />
              <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border/60 pt-4">
                <p className="text-xs text-muted-foreground/60">
                  {design
                    ? design.builtin
                      ? "Your cards use the built-in design. Open the designer to make it your own."
                      : `Your cards use \u201c${design.name}\u201d \u00b7 ${design.layout.widgets.length} blocks`
                    : "Loading your card design\u2026"}
                </p>
                <Button variant="outline" asChild>
                  <Link href="/reports/designer">
                    <PenLine className="h-4 w-4" /> Open the designer
                  </Link>
                </Button>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      )}

      {/* The premium card */}
      {bulkOpen ? (
        <div className="space-y-6 print:space-y-0">
          <motion.div
            className="print:hidden"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: 0.04, ease }}
          >
            <Card className="transition-all duration-200 hover:-translate-y-[1px] hover:shadow-card">
              <CardContent className="flex flex-wrap items-center justify-between gap-3 py-4">
                <div>
                  <p className="text-sm font-medium">All report cards — {armId ? arms.find((a) => a.id === armId)?.full_name ?? "this arm" : ""}</p>
                  <p className="text-xs text-muted-foreground/50">
                    {bulkLoading || bulkFetching
                      ? "Loading…"
                      : `${bulkCards.length} card${bulkCards.length === 1 ? "" : "s"} ready · prints one card per page`}
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    disabled={bulkCards.length === 0 || bulkLoading}
                    onClick={() => window.print()}
                  >
                    <span className="flex h-8 w-8 items-center justify-center rounded-xl">
                      <Printer className="h-4 w-4" />
                    </span>
                    Print all ({bulkCards.length})
                  </Button>
                  <Button
                    disabled={bulkCards.length === 0 || bulkLoading}
                    onClick={handleDownloadBulk}
                  >
                    <span className="flex h-8 w-8 items-center justify-center rounded-xl">
                      <Download className="h-4 w-4" />
                    </span>
                    Download PDF
                  </Button>
                </div>
              </CardContent>
            </Card>
          </motion.div>
          {bulkLoading && bulkCards.length === 0 ? (
            <Skeleton className="h-64 w-full" />
          ) : bulkCards.length === 0 ? (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, delay: 0.08, ease }}
            >
              <Card>
                <CardContent className="py-12 text-center text-muted-foreground/50">
                  No published report cards for this arm this term yet.
                </CardContent>
              </Card>
            </motion.div>
          ) : (
            <div className="space-y-8">
              {bulkCards.map((c) => (
                <div
                  key={c.enrollment_id}
                  className="rc-print-page"
                  ref={(el) => {
                    if (el) bulkRefs.current.set(c.enrollment_id, el);
                  }}
                >
                  <ReportCardDocument card={c} layout={design?.layout} />
                </div>
              ))}
            </div>
          )}
        </div>
      ) : cardLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : error || !card ? (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.04, ease }}
        >
          <Card className="transition-all duration-200 hover:-translate-y-[1px] hover:shadow-card">
            <CardContent className="py-12 text-center text-muted-foreground/50">
              {studentId
                ? "No published results for this student in this term yet."
                : "Pick a student to view their report card."}
            </CardContent>
          </Card>
        </motion.div>
      ) : (
        <motion.div
          className="report-card-stage"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.04, ease }}
        >
          {/* The psychomotor/affective record has its own page (/results/
              psychomotor) — it is the class teacher's to write, and this page
              belongs to the exam office. The card below still *displays* it. */}
          {/* Homeroom teachers only see/edit their own comment slot; other
              roles keep the existing all-roles view. */}
          <CommentManager card={card} userRole={isHomeroomTeacher ? role : undefined} />
          <div ref={reportCardRef}>
            <ReportCardDocument card={card} layout={design?.layout} />
          </div>
        </motion.div>
      )}
    </div>
  );
}