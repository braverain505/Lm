"use client";

import { Download, Files, Printer, X } from "lucide-react";
import { motion } from "framer-motion";
import { useCallback, useRef, useState } from "react";

const ease = [0.25, 0.46, 0.45, 0.94] as const;

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { CommentManager } from "@/components/comment-manager";
import { PsychomotorEditor } from "@/components/psychomotor-editor";
import { ReportCardDocument } from "@/components/report-card-document";
import { useArms, useReportCard, useReportCards, useReportIndex, useSessions, useTerms } from "@/hooks/use-api";
import { cn } from "@/lib/utils";
import { downloadPdf, downloadBulkPdf } from "@/lib/pdf";
import { useToast } from "@/components/toast";
import "@/app/report-card.css";
import "@/app/report-card-templates.css";
import { ReportTemplatePicker } from "@/components/report-template-picker";
import { getSelectedTemplate } from "@/lib/report-templates";
import { useAuth } from "@/providers/auth-provider";

export default function ReportsPage() {
  const { activeSchool } = useAuth();
  const role = activeSchool?.role?.code ?? "";
  const isHomeroomTeacher = role === "homeroom_teacher";
  const { data: sessions = [] } = useSessions();
  const current = sessions.find((s) => s.is_current) ?? sessions[0];
  const { data: terms = [] } = useTerms(current?.id ?? null);
  const { data: arms = [] } = useArms(current?.id ?? null);

  const [activeTermId, setActiveTermId] = useState<string | null>(null);
  const term = terms.find((t) => t.id === activeTermId) ?? terms.find((t) => t.is_current) ?? terms[0];
  const [armId, setArmId] = useState("");
  const [studentId, setStudentId] = useState<string | null>(null);
  const [bulkOpen, setBulkOpen] = useState(false);
  const [templateId, setTemplateId] = useState(getSelectedTemplate());

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

      {/* Template picker (hidden on print) */}
      <motion.div
        className="print:hidden"
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, delay: 0.12, ease }}
      >
        <Card className="transition-all duration-200 hover:-translate-y-[1px] hover:shadow-card">
          <CardContent className="py-5">
            <ReportTemplatePicker value={templateId} onChange={setTemplateId} />
          </CardContent>
        </Card>
      </motion.div>

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
                  <ReportCardDocument card={c} template={`rc-template-${templateId}`} />
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
          {studentId && term && (
            <PsychomotorEditor
              studentId={studentId}
              termId={term.id}
              allowed={card.can_manage_psychomotor}
            />
          )}
          {/* Homeroom teachers only see/edit their own comment slot; other
              roles keep the existing all-roles view. */}
          <CommentManager card={card} userRole={isHomeroomTeacher ? role : undefined} />
          <div ref={reportCardRef}>
            <ReportCardDocument card={card} template={`rc-template-${templateId}`} />
          </div>
        </motion.div>
      )}
    </div>
  );
}