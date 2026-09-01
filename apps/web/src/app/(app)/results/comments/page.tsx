"use client";

import { Suspense, useState } from "react";
import { ChevronDown, ChevronRight, FileText } from "lucide-react";
import { useSearchParams } from "next/navigation";

import { CommentManager } from "@/components/comment-manager";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Loader } from "@/components/ui/loader";
import {
  useSessions,
  useTerms,
  useArms,
  useMyAssignments,
  useReportCards,
} from "@/hooks/use-api";
import { useAuth } from "@/providers/auth-provider";
import { cn } from "@/lib/utils";
import type { ReportCard } from "@schoolos/shared";

function StudentCommentRow({
  card,
  defaultOpen,
  userRole,
}: {
  card: ReportCard;
  defaultOpen?: boolean;
  userRole?: string;
}) {
  const [open, setOpen] = useState(defaultOpen ?? false);
  const hasComment = Boolean(card.comments.homeroom);
  const canComment = card.can_comment;

  return (
    <div className="rounded-xl border transition-colors hover:border-primary/20">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left"
      >
        <div className="flex items-center gap-3 min-w-0">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">
            {card.student.full_name.charAt(0)}
          </span>
          <div className="min-w-0">
            <p className="text-sm font-semibold truncate">{card.student.full_name}</p>
            <p className="text-xs text-muted-foreground">{card.student.admission_no}</p>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {hasComment && (
            <Badge variant="success" className="text-[10px]">Has comment</Badge>
          )}
          {!hasComment && canComment && (
            <Badge variant="warning" className="text-[10px]">No comment</Badge>
          )}
          {open ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          )}
        </div>
      </button>
      {open && (
        <div className="border-t px-4 pb-4 pt-3">
          <CommentManager card={card} userRole={userRole} />
        </div>
      )}
    </div>
  );
}

function CommentsContent() {
  const searchParams = useSearchParams();
  const armId = searchParams.get("arm_id");
  const termId = searchParams.get("term_id");

  const { activeSchool } = useAuth();
  const role = activeSchool?.role?.code ?? "";
  const isHomeroomTeacher = role === "homeroom_teacher";

  const { data: sessions = [] } = useSessions();
  const current = sessions.find((s) => s.is_current) ?? sessions[0];
  const { data: terms = [] } = useTerms(current?.id ?? null);
  const { data: arms = [] } = useArms(current?.id ?? null);
  const { data: myAssignments = [] } = useMyAssignments();

  const myArmIds = new Set(myAssignments.map((a) => a.arm_id));
  const visibleArms = isHomeroomTeacher
    ? arms.filter((a) => myArmIds.has(a.id))
    : arms;

  const [selectedArm, setSelectedArm] = useState(armId ?? "");
  const [selectedTerm, setSelectedTerm] = useState(termId ?? "");

  // Use URL params or state
  const effectiveArm = armId ?? selectedArm;
  const effectiveTerm =
    termId ??
    selectedTerm ??
    terms.find((t) => t.is_current)?.id ??
    terms[0]?.id ??
    "";

  const { data: cards = [], isLoading } = useReportCards(
    effectiveArm || null,
    effectiveTerm || null,
  );

  // Summary stats
  const totalStudents = cards.length;
  const withComments = cards.filter((c) => Boolean(c.comments.homeroom)).length;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          <FileText className="mr-2 inline h-5 w-5" />
          Homeroom Comments
        </h1>
        <p className="text-sm text-muted-foreground">
          Write result comments for each student in your class.
        </p>
      </div>

      {/* Selectors (only if not passed via URL) */}
      {!armId && (
        <Card>
          <CardContent className="py-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>Term</Label>
                <select
                  className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
                  value={effectiveTerm}
                  onChange={(e) => setSelectedTerm(e.target.value)}
                >
                  <option value="">Choose term…</option>
                  {terms.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                <Label>Class arm</Label>
                <select
                  className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
                  value={effectiveArm}
                  onChange={(e) => setSelectedArm(e.target.value)}
                >
                  <option value="">Choose arm…</option>
                  {visibleArms.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.full_name}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Stats */}
      {effectiveArm && effectiveTerm && (
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="stat-card">
            <p className="text-[13px] text-muted-foreground">Students</p>
            <p className="mt-1 text-2xl font-bold tracking-tight">{totalStudents}</p>
          </div>
          <div className="stat-card">
            <p className="text-[13px] text-muted-foreground">Comments written</p>
            <p className={cn("mt-1 text-2xl font-bold tracking-tight", withComments === totalStudents ? "text-success" : "text-warning")}>
              {withComments}/{totalStudents}
            </p>
          </div>
          <div className="stat-card">
            <p className="text-[13px] text-muted-foreground">Remaining</p>
            <p className={cn("mt-1 text-2xl font-bold tracking-tight", totalStudents - withComments === 0 ? "text-success" : "text-destructive")}>
              {totalStudents - withComments}
            </p>
          </div>
        </div>
      )}

      {/* Student list */}
      {!effectiveArm || !effectiveTerm ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            Select a class arm and term to see students.
          </CardContent>
        </Card>
      ) : isLoading ? (
        <div className="flex justify-center py-20">
          <Loader />
        </div>
      ) : cards.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            No students found in this class arm for the selected term.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          {cards.map((card) => (
            <StudentCommentRow key={card.enrollment_id} card={card} userRole={role} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function CommentsPage() {
  return (
    <Suspense fallback={<Loader className="mx-auto my-20" />}>
      <CommentsContent />
    </Suspense>
  );
}
