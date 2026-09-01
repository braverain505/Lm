"use client";

import { Sparkles, Trash2, X } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader } from "@/components/ui/loader";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { PremiumLock, useAiEnabled } from "@/components/premium-lock";
import {
  COMMENT_ROLES,
  type CommentRole,
  useCommentBank,
  useCreateCommentBankEntry,
  useDeactivateCommentBankEntry,
  usePreviewRoleComment,
  useSaveRoleComment,
  useGenerateRoleComment,
} from "@/hooks/use-api";
import type { ReportCard } from "@schoolos/shared";
import { cn } from "@/lib/utils";
import { useToast } from "@/components/toast";

type Source = "manual" | "bank" | "ai";

const TONES = [
  { value: "professional", label: "Professional" },
  { value: "warm", label: "Warm" },
  { value: "concise", label: "Concise" },
];

const CATEGORIES = [
  "performance",
  "effort",
  "behavior",
  "attendance",
  "conduct",
  "general",
];

function AIContentModal({
  role,
  roleLabel,
  studentId,
  termId,
  onClose,
}: {
  role: CommentRole;
  roleLabel: string;
  studentId: string;
  termId: string;
  onClose: () => void;
}) {
  const [tone, setTone] = useState("professional");
  const [focus, setFocus] = useState("");
  const [preview, setPreview] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [touched, setTouched] = useState(false);

  const previewGen = usePreviewRoleComment();
  const saveAI = useGenerateRoleComment(studentId, termId);
  const saveManual = useSaveRoleComment(studentId, termId);
  const { toast } = useToast();

  const handlePreview = () => {
    previewGen.mutate(
      { studentId, termId, role, focus: focus || null, tone },
      {
        onSuccess: (res) => {
          setPreview(res.body);
          setDraft(res.body);
          setTouched(false);
        },
      },
    );
  };

  const persist = () => {
    const finalBody = draft.trim();
    if (!finalBody) return;
    const unchanged = touched === false && preview !== null && draft === preview;
    if (unchanged) {
      saveAI.mutate(
        { role, focus: focus || null, tone },
        {
          onSuccess: () => toast("AI comment saved to report"),
          onError: () => toast("Failed to save AI comment", "error"),
        },
      );
    } else {
      saveManual.mutate(
        { role, body: finalBody },
        {
          onSuccess: () => toast("Comment saved to report"),
          onError: () => toast("Failed to save comment", "error"),
        },
      );
    }
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 print:hidden">
      <div className="w-full max-w-2xl rounded-xl border bg-background p-5 shadow-xl">
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold">AI comment — {roleLabel}</h3>
            <p className="text-sm text-muted-foreground">
              Grounded in the published report card. Review before saving; edits save as a
              manual comment.
            </p>
          </div>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="mb-4 grid gap-3 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="tone">Tone</Label>
            <Select value={tone} onValueChange={(v) => setTone(v)}>
              <SelectTrigger id="tone" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {TONES.map((t) => (
                  <SelectItem key={t.value} value={t.value}>
                    {t.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="focus">Focus (optional)</Label>
            <Input
              id="focus"
              placeholder="e.g. steady revision in Mathematics"
              value={focus}
              onChange={(e) => setFocus(e.target.value)}
            />
          </div>
        </div>

        <div className="mb-3">
          <Button
            size="sm"
            onClick={handlePreview}
            disabled={previewGen.isPending}
            className="gap-1.5"
          >
            <Sparkles className="h-3.5 w-3.5" />
            {previewGen.isPending ? "Composing…" : "Preview draft"}
          </Button>
        </div>

        {previewGen.isPending ? (
          <div className="flex justify-center py-8">
            <Loader />
          </div>
        ) : preview === null ? (
          <p className="rounded-lg border border-dashed px-4 py-6 text-center text-sm text-muted-foreground">
            Set the tone and optional focus, then preview the draft.
          </p>
        ) : (
          <>
            <textarea
              className="min-h-40 w-full rounded-lg border border-input bg-transparent p-3 text-sm leading-relaxed"
              value={draft}
              onChange={(e) => {
                setDraft(e.target.value);
                setTouched(true);
              }}
            />
            <div className="mt-3 flex items-center justify-between gap-2">
              <span className="text-xs text-muted-foreground">
                {touched ? "Edited — will save as a manual comment" : "Unchanged — will save as an AI comment"}
              </span>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={handlePreview}>
                  Regenerate
                </Button>
                <Button
                  size="sm"
                  onClick={persist}
                  disabled={saveAI.isPending || saveManual.isPending || !draft.trim()}
                >
                  {saveAI.isPending || saveManual.isPending ? "Saving…" : "Save to report"}
                </Button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function RoleCommentCard({
  role,
  roleLabel,
  studentId,
  termId,
  initialBody,
  canEdit,
}: {
  role: CommentRole;
  roleLabel: string;
  studentId: string;
  termId: string;
  initialBody: string | null;
  canEdit: boolean;
}) {
  const canComment = canEdit;
  const [source, setSource] = useState<Source>("manual");
  const [text, setText] = useState(initialBody ?? "");
  const [category, setCategory] = useState("");
  const [sentiment, setSentiment] = useState("");
  const [showAI, setShowAI] = useState(false);
  const [showPremium, setShowPremium] = useState(false);
  const aiEnabled = useAiEnabled();
  const { toast } = useToast();

  const openAI = () => {
    if (!aiEnabled) {
      setShowAI(false);
      setShowPremium(true);
    } else {
      setShowPremium(false);
      setShowAI(true);
    }
  };

  const { data: bank = [], isLoading: bankLoading } = useCommentBank({ category, sentiment });
  const save = useSaveRoleComment(studentId, termId);

  // Wrap save with toast
  const handleSave = () => {
    save.mutate(
      { role, body: text },
      {
        onSuccess: () => toast(`${roleLabel} comment saved`),
        onError: () => toast("Failed to save comment", "error"),
      },
    );
  };

  const filteredBank = useMemo(
    () =>
      bank.filter((e) => {
        const domain = e.applicable_domain ?? "all";
        return domain === "all" || domain === role;
      }),
    [bank, role],
  );

  const saved = useMemo(() => text !== (initialBody ?? ""), [text, initialBody]);

  return (
    <Card className="print:hidden">
      <div className="border-b px-4 py-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <h4 className="text-sm font-semibold">{roleLabel}</h4>
            {initialBody && <Badge variant="muted">saved</Badge>}
            {saved && <Badge variant="warning">unsaved edits</Badge>}
          </div>
          <Button size="sm" onClick={openAI} className="gap-1.5" disabled={!canComment}>
            <Sparkles className="h-3.5 w-3.5" />
            AI
          </Button>
        </div>
      </div>

      {showPremium && (
        <div className="px-4 pt-3">
          <PremiumLock compact />
        </div>
      )}

      <div className="space-y-3 px-4 py-3">
        <textarea
          className="min-h-28 w-full rounded-lg border border-input bg-transparent p-3 text-sm leading-relaxed"
          placeholder={`Write the ${roleLabel.toLowerCase()} comment, or pick a source below.`}
          value={text}
          onChange={(e) => setText(e.target.value)}
        />

        <div className="flex items-center justify-between gap-2">
          <div className="flex gap-1.5">
            {(["manual", "bank", "ai"] as Source[]).map((s) => (
              <button
                key={s}
                onClick={() => setSource(s)}
                className={cn(
                  "rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
                  source === s
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:bg-accent",
                )}
              >
                {s === "manual" ? "Manual" : s === "bank" ? "Comment bank" : "AI"}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-2">
            {initialBody && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setText(initialBody ?? "")}
                disabled={!saved}
              >
                Reset
              </Button>
            )}
            <Button
              size="sm"
              onClick={handleSave}
              disabled={!canComment || !text.trim() || save.isPending}
              isLoading={save.isPending}
            >
              {save.isPending ? "Saving…" : "Save"}
            </Button>
          </div>
        </div>

        {source === "bank" && (
          <div className="rounded-lg border bg-muted/30 p-3">
            <div className="mb-2 grid gap-2 sm:grid-cols-[1fr_150px_130px]">
              <Select
                value=""
                onValueChange={(value) => {
                  setText(value);
                  setSource("manual");
                }}
              >
                <SelectTrigger className="bg-background">
                  <SelectValue placeholder="Select a comment from the bank…" />
                </SelectTrigger>
                <SelectContent>
                  {filteredBank.length === 0 && (
                    <p className="px-3 py-2 text-xs text-muted-foreground">
                      No matching comments in the bank.
                    </p>
                  )}
                  {filteredBank.map((e) => (
                    <SelectItem key={e.id} value={e.comment_text}>
                      {e.comment_text}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={category} onValueChange={setCategory}>
                <SelectTrigger>
                  <SelectValue placeholder="Category" />
                </SelectTrigger>
                <SelectContent>
                  {CATEGORIES.map((c) => (
                    <SelectItem key={c} value={c}>
                      {c[0].toUpperCase() + c.slice(1)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={sentiment} onValueChange={setSentiment}>
                <SelectTrigger>
                  <SelectValue placeholder="Sentiment" />
                </SelectTrigger>
                <SelectContent>
                  {["positive", "neutral", "negative"].map((s) => (
                    <SelectItem key={s} value={s}>
                      {s[0].toUpperCase() + s.slice(1)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {bankLoading ? (
              <div className="flex justify-center py-4">
                <Loader />
              </div>
            ) : filteredBank.length === 0 ? (
              <p className="py-3 text-center text-xs text-muted-foreground">
                No matching comments in the bank.
              </p>
            ) : (
              <ul className="max-h-44 space-y-1.5 overflow-y-auto">
                {filteredBank.map((e) => (
                  <li key={e.id} className="flex items-start justify-between gap-2 rounded-md border bg-background px-3 py-2">
                    <span className="text-xs leading-relaxed">{e.comment_text}</span>
                    <Button
                      variant="outline"
                      size="sm"
                      className="shrink-0"
                      onClick={() => {
                        setText(e.comment_text);
                        setSource("manual");
                      }}
                    >
                      Insert
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {source === "ai" && (
          <p className="rounded-lg border border-dashed px-3 py-2 text-xs text-muted-foreground">
            Use the <b>AI</b> button above to compose a draft grounded in the published report
            card, then review and save it here.
          </p>
        )}
      </div>

      {showAI && (
        <AIContentModal
          role={role}
          roleLabel={roleLabel}
          studentId={studentId}
          termId={termId}
          onClose={() => setShowAI(false)}
        />
      )}
    </Card>
  );
}

function BankCurationPanel({ canEdit }: { canEdit: boolean }) {
  const [text, setText] = useState("");
  const [category, setCategory] = useState("performance");
  const [sentiment, setSentiment] = useState("positive");
  const [domain, setDomain] = useState("all");
  const { toast } = useToast();

  const { data: bank = [], isLoading } = useCommentBank({});
  const create = useCreateCommentBankEntry();
  const deactivate = useDeactivateCommentBankEntry();

  if (!canEdit) return null;

  return (
    <Card className="print:hidden">
      <div className="border-b px-4 py-3">
        <h4 className="text-sm font-semibold">Comment bank</h4>
        <p className="text-xs text-muted-foreground">
          Pre-approved phrases teachers can search and insert into any comment area.
        </p>
      </div>
      <div className="space-y-3 px-4 py-3">
        <div className="grid gap-2 sm:grid-cols-[1fr_130px_120px_130px_auto]">
          <Input
            placeholder="New comment text…"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <Select value={category} onValueChange={setCategory}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {CATEGORIES.map((c) => (
                <SelectItem key={c} value={c}>
                  {c[0].toUpperCase() + c.slice(1)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={sentiment} onValueChange={setSentiment}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {["positive", "neutral", "negative"].map((s) => (
                <SelectItem key={s} value={s}>
                  {s[0].toUpperCase() + s.slice(1)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={domain} onValueChange={setDomain}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {["all", "principal", "vice_principal", "homeroom"].map((d) => (
                <SelectItem key={d} value={d}>
                  {d === "all" ? "All roles" : d.replace("_", " ")}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            size="sm"
            onClick={() => create.mutate(
              { comment_text: text, category, sentiment, applicable_domain: domain },
              {
                onSuccess: () => { setText(""); toast("Comment added to bank"); },
                onError: () => toast("Failed to add comment", "error"),
              },
            )}
            disabled={!text.trim() || create.isPending}
            isLoading={create.isPending}
          >
            Add
          </Button>
        </div>

        {isLoading ? (
          <div className="flex justify-center py-4">
            <Loader />
          </div>
        ) : bank.length === 0 ? (
          <p className="py-3 text-center text-xs text-muted-foreground">
            The bank is empty — add your first reusable comment above.
          </p>
        ) : (
          <ul className="max-h-64 space-y-1.5 overflow-y-auto">
            {bank.map((e) => (
              <li
                key={e.id}
                className="flex items-start justify-between gap-3 rounded-md border px-3 py-2"
              >
                <div>
                  <p className="text-xs leading-relaxed">{e.comment_text}</p>
                  <p className="mt-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
                    {e.category} · {e.sentiment} · {e.applicable_domain ?? "all"}
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="shrink-0 text-muted-foreground hover:text-destructive"
                  onClick={() => deactivate.mutate(e.id, {
                    onSuccess: () => toast("Comment removed from bank"),
                    onError: () => toast("Failed to remove comment", "error"),
                  })}
                  disabled={deactivate.isPending}
                  title="Remove from bank"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}

export function CommentManager({ card, userRole }: { card: ReportCard; userRole?: string }) {
  const { student_id: studentId } = card.student;

  // Filter comment roles based on the user's role.
  // Homeroom teachers can only write homeroom comments.
  // Principal / VP academics can write principal and vice_principal comments.
  const visibleRoles = COMMENT_ROLES.filter((r) => {
    if (!userRole) return true; // no role info = show all (backwards compat)
    if (userRole === "homeroom_teacher") return r.key === "homeroom";
    if (userRole === "principal") return r.key === "principal";
    if (userRole === "vp_academics") return r.key === "vice_principal";
    return true; // admin / super_admin etc. see everything
  });

  const gridCols = visibleRoles.length <= 1 ? "lg:grid-cols-1" : visibleRoles.length === 2 ? "lg:grid-cols-2" : "lg:grid-cols-3";

  return (
    <div className="space-y-4 print:hidden">
      <div>
        <h3 className="text-sm font-semibold text-muted-foreground">Comments on this report</h3>
        <p className="text-xs text-muted-foreground">
          Write manually, pull from the school&apos;s comment bank, or
          compose with AI — always review before saving.
        </p>
      </div>

      <div className={`grid gap-4 ${gridCols}`}>
        {visibleRoles.map((r) => (
          <RoleCommentCard
            key={r.key}
            role={r.key}
            roleLabel={r.label}
            studentId={studentId}
            termId={card.term.id}
            initialBody={card.comments[r.key] ?? null}
            canEdit={card.can_comment}
          />
        ))}
      </div>

      <BankCurationPanel canEdit={card.can_comment} />
    </div>
  );
}