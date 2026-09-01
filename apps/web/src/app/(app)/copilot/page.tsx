"use client";

import { Bot, MessageSquare, Plus, Send, Sparkles } from "lucide-react";
import { useState } from "react";

import type { CopilotMessage } from "@schoolos/shared";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { PremiumLock, useAiEnabled } from "@/components/premium-lock";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useAskCopilot,
  useCanCopilot,
  useConversation,
  useConversations,
  useCopilotIntents,
  useSessions,
  useTerms,
} from "@/hooks/use-api";
import { cn } from "@/lib/utils";

function fmtTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

// ---------------------------------------------------------------------------
// Payload cards — turn the JSONB facts attached to an answer into small
// visualizations (count stats, a top-3 table, per-arm readiness bars).
// ---------------------------------------------------------------------------
function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border bg-muted/40 px-3 py-2">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-sm font-semibold">{value}</p>
    </div>
  );
}

function PayloadCard({ payload }: { payload: Record<string, unknown> | null }) {
  if (!payload) return null;
  const intent = typeof payload.intent === "string" ? payload.intent : "";

  if (intent === "top_performers" && Array.isArray(payload.rows)) {
    const rows = payload.rows as Record<string, unknown>[];
    return (
      <div className="mt-2 overflow-hidden rounded-md border">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 text-xs text-muted-foreground">
            <tr>
              <th className="px-3 py-2 text-left font-medium">#</th>
              <th className="px-3 py-2 text-left font-medium">Student</th>
              <th className="px-3 py-2 text-right font-medium">Total</th>
              <th className="px-3 py-2 text-right font-medium">Grade</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-t">
                <td className="px-3 py-2 text-muted-foreground">{i + 1}</td>
                <td className="px-3 py-2">
                  {String(r.full_name ?? "")}
                  <span className="ml-2 text-xs text-muted-foreground">
                    {String(r.admission_no ?? "")}
                  </span>
                </td>
                <td className="px-3 py-2 text-right font-medium">
                  {r.total != null ? Number(r.total).toFixed(0) : "—"}
                </td>
                <td className="px-3 py-2 text-right text-muted-foreground">
                  {String(r.grade_letter ?? "—")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  if (intent === "readiness" && Array.isArray(payload.arms)) {
    const arms = payload.arms as Record<string, unknown>[];
    return (
      <div className="mt-2 space-y-2">
        {arms.map((a) => {
          const students = Number(a.students ?? 0);
          const entered = Number(a.entered ?? 0);
          const submitted = Number(a.submitted ?? 0);
          const pct = students > 0 ? Math.round((entered / students) * 100) : 0;
          return (
            <div key={String(a.arm_name)}>
              <div className="flex items-center justify-between text-xs">
                <span className="font-medium">{String(a.arm_name)}</span>
                <span className="text-muted-foreground">
                  {entered}/{students} entered · {submitted} submitted
                </span>
              </div>
              <div className="mt-1 h-1.5 rounded-full bg-muted">
                <div
                  className="h-1.5 rounded-full bg-primary"
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    );
  }

  const stats: Array<[string, string | number]> = [];
  if (intent === "class_snapshot") {
    stats.push(["Enrolled", Number(payload.enrolled ?? 0)]);
    stats.push(["Boys", Number(payload.boys ?? 0)]);
    stats.push(["Girls", Number(payload.girls ?? 0)]);
  } else if (intent === "class_subjects" && Array.isArray(payload.subject_names)) {
    stats.push(["Subjects", (payload.subject_names as unknown[]).length]);
  } else if (intent === "subject_average") {
    stats.push(["Published", Number(payload.published ?? 0)]);
    stats.push(["Average", Number(payload.average ?? 0).toFixed(2)]);
    if (payload.min != null) stats.push(["Min", Number(payload.min).toFixed(0)]);
    if (payload.max != null) stats.push(["Max", Number(payload.max).toFixed(0)]);
  } else if (intent === "term_summary") {
    stats.push(["Published cards", Number(payload.published_cards ?? 0)]);
    stats.push(["Class average", Number(payload.class_average ?? 0).toFixed(2)]);
    if (payload.top && typeof payload.top === "object") {
      const top = payload.top as Record<string, unknown>;
      stats.push([
        "Top student",
        `${String(top.full_name ?? "")} (${Number(top.total ?? 0).toFixed(0)})`,
      ]);
    }
  } else if (intent === "school_overview") {
    if (payload.students != null) stats.push(["Students", Number(payload.students)]);
    if (payload.teachers != null) stats.push(["Teachers", Number(payload.teachers)]);
    if (payload.subjects != null) stats.push(["Subjects", Number(payload.subjects)]);
    if (payload.arms != null) stats.push(["Arms", Number(payload.arms)]);
    if (payload.levels != null) stats.push(["Levels", Number(payload.levels)]);
  } else if (
    intent === "student_report" &&
    payload.summary &&
    typeof payload.summary === "object"
  ) {
    const s = payload.summary as Record<string, unknown>;
    stats.push(["Published", Number(s.subjects_published ?? 0)]);
    if (s.total != null) stats.push(["Total", Number(s.total).toFixed(0)]);
    if (s.average != null) stats.push(["Average", Number(s.average).toFixed(2)]);
    if (s.grade_letter != null) stats.push(["Grade", String(s.grade_letter)]);
    if (s.class_rank != null)
      stats.push(["Class rank", `${s.class_rank} of ${s.class_size ?? "—"}`]);
  }

  if (stats.length === 0) return null;
  return (
    <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3">
      {stats.map(([label, value]) => (
        <Stat key={label} label={label} value={value} />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function CopilotPage() {
  const can = useCanCopilot();
  const aiEnabled = useAiEnabled();
  const { data: sessions = [] } = useSessions();
  const current = sessions.find((s) => s.is_current) ?? sessions[0];
  const { data: terms = [] } = useTerms(current?.id ?? null);

  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [scopeTermId, setScopeTermId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState<string | null>(null);

  const { data: conversations = [], isLoading: railLoading } = useConversations();
  const { data: conversation, isLoading: threadLoading } = useConversation(activeConvId);
  const { data: intents = [] } = useCopilotIntents();
  const ask = useAskCopilot();

  const messages: CopilotMessage[] = conversation?.messages ?? [];

  const send = (text?: string) => {
    const q = (text ?? input).trim();
    if (!q || ask.isPending || !can) return;
    setInput("");
    setThinking(q);
    const body: { question: string; conversation_id?: string; term_id?: string } = {
      question: q,
    };
    if (activeConvId) body.conversation_id = activeConvId;
    else if (scopeTermId) body.term_id = scopeTermId;
    ask.mutate(body, {
      onSuccess: (result) => {
        // Follow-ups stay in the current thread; a fresh thread becomes active.
        setActiveConvId((cur) => cur ?? result.conversation.id);
      },
      onSettled: () => setThinking(null),
    });
  };

  // Header
  const header = (
    <div className="flex items-start justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">School copilot</h1>
        <p className="text-sm text-muted-foreground">
          Ask questions about this school and get answers grounded in its own
          records — no invented numbers. Every turn is metered under ai.copilot.
        </p>
      </div>
    </div>
  );

  if (!can) {
    return (
      <div className="space-y-6">
        {header}
        <Card>
          <CardContent className="pt-6">
            <div className="flex gap-3">
              <Bot className="h-5 w-5 text-muted-foreground" />
              <div>
                <p className="font-medium">Copilot is off for this account</p>
                <p className="text-sm text-muted-foreground">
                  The school copilot needs the{" "}
                  <code className="rounded bg-muted px-1 py-0.5 text-xs">ai.copilot</code>{" "}
                  permission, which leadership roles (director, principal, head
                  teacher, academic coordinator) hold.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!aiEnabled) {
    return (
      <div className="space-y-6">
        {header}
        <PremiumLock />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {header}

      <div className="grid gap-4 lg:grid-cols-[16rem_1fr]">
        {/* Left rail: saved conversations */}
        <Card className="flex max-h-[calc(100vh-11rem)] flex-col">
          <div className="border-b p-3">
            <Button
              variant="outline"
              className="w-full"
              onClick={() => {
                setActiveConvId(null);
                setScopeTermId(null);
                setInput("");
              }}
            >
              <Plus className="mr-2 h-4 w-4" /> New chat
            </Button>
          </div>
          <div className="flex-1 space-y-1 overflow-y-auto p-2">
            {railLoading &&
              Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-9 w-full" />
              ))}
            {!railLoading && conversations.length === 0 && (
              <p className="px-2 py-4 text-center text-xs text-muted-foreground">
                No conversations yet
              </p>
            )}
            {conversations.map((c) => (
              <button
                key={c.id}
                onClick={() => {
                  setActiveConvId(c.id);
                  setThinking(null);
                }}
                className={cn(
                  "flex w-full items-start gap-2 rounded-md px-2 py-2 text-left text-sm transition-colors",
                  c.id === activeConvId
                    ? "bg-primary/10 text-primary"
                    : "hover:bg-accent",
                )}
              >
                <MessageSquare className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                <span className="min-w-0">
                  <span className="block truncate font-medium">{c.title}</span>
                  <span className="block text-xs text-muted-foreground">
                    {fmtTime(c.created_at)}
                  </span>
                </span>
              </button>
            ))}
          </div>
        </Card>

        {/* Main chat pane */}
        <Card className="flex max-h-[calc(100vh-11rem)] flex-col">
          {/* Term scope pills — compose a new question's results scope */}
          <div className="flex flex-wrap items-center gap-2 border-b px-4 py-2.5">
            <span className="text-xs text-muted-foreground">New-chat term scope</span>
            {terms.map((t) => (
              <button
                key={t.id}
                disabled={!!activeConvId}
                onClick={() => setScopeTermId(scopeTermId === t.id ? null : t.id)}
                className={cn(
                  "rounded-md border px-2.5 py-1 text-xs font-medium transition-colors",
                  scopeTermId === t.id
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-input text-muted-foreground hover:bg-accent",
                  activeConvId && "opacity-50",
                )}
              >
                {t.name}
              </button>
            ))}
            {/* The active conversation's own term scope, once known */}
            {activeConvId && conversation?.term_id && (
              <span className="text-xs text-muted-foreground">
                · scoped to{" "}
                {terms.find((t) => t.id === conversation.term_id)?.name ?? "this term"}
              </span>
            )}
          </div>

          {/* Thread */}
          <div className="flex-1 space-y-4 overflow-y-auto p-4">
            {activeConvId && threadLoading && (
              <div className="space-y-3">
                <Skeleton className="ml-auto h-9 w-2/3" />
                <Skeleton className="h-16 w-3/4" />
              </div>
            )}

            {!activeConvId && messages.length === 0 && !thinking && (
              <Intro
                intents={intents.map((i) => i.examples).flat().slice(0, 6)}
                onPick={(q) => send(q)}
              />
            )}

            {messages.map((m) => (
              <MessageBubble key={m.id} message={m} />
            ))}

            {thinking && (
              <>
                <MessageBubble
                  message={{
                    id: "local-q",
                    conversation_id: activeConvId ?? "",
                    role: "user",
                    content: thinking,
                    intent: null,
                    answer_payload: null,
                    created_at: new Date().toISOString(),
                  }}
                />
                <div className="flex items-start gap-2">
                  <Bot className="mt-1 h-4 w-4 text-primary" />
                  <div className="flex items-center gap-1 rounded-lg border bg-muted/40 px-3 py-2 text-sm text-muted-foreground">
                    <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-primary" />
                    Thinking…
                  </div>
                </div>
              </>
            )}

            </div>

          {/* Composer */}
          <div className="border-t p-3">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                send();
              }}
              className="flex items-end gap-2"
            >
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    send();
                  }
                }}
                rows={1}
                placeholder="Ask about this school… (Enter to send, Shift+Enter for a new line)"
                className="max-h-32 min-h-[2.5rem] flex-1 resize-y rounded-md border border-input bg-transparent px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              />
              <Button type="submit" disabled={!input.trim() || ask.isPending}>
                <Send className="mr-2 h-4 w-4" /> Ask
              </Button>
            </form>
            <p className="mt-2 flex items-center gap-1 text-[11px] text-muted-foreground">
              <Sparkles className="h-3 w-3" />
              AI copilot · clearis-copilot-v1 · deterministic and data-grounded ·
              every turn metered
            </p>
          </div>
        </Card>
      </div>
    </div>
  );
}

function Intro({ intents, onPick }: { intents: string[]; onPick: (q: string) => void }) {
  return (
    <div className="mx-auto max-w-xl py-6 text-center">
      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary">
        <Bot className="h-6 w-6" />
      </div>
      <p className="mt-3 font-medium">Ask anything about this school</p>
      <p className="text-sm text-muted-foreground">
        Counts, subjects, score-entry progress, published results, top performers
        and term averages — answered from your school&apos;s own records.
      </p>
      <div className="mt-4 flex flex-wrap justify-center gap-2">
        {intents.map((q) => (
          <button
            key={q}
            onClick={() => onPick(q)}
            className="rounded-full border border-input px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: CopilotMessage }) {
  const isUser = message.role === "user";
  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-lg bg-primary px-3 py-2 text-sm text-primary-foreground">
          {message.content}
        </div>
      </div>
    );
  }
  return (
    <div className="flex items-start gap-2">
      <Bot className="mt-1 h-4 w-4 shrink-0 text-primary" />
      <div className="max-w-[92%]">
        <div className="rounded-lg border bg-card px-3 py-2">
          <p className="text-sm">{message.content}</p>
          <PayloadCard payload={message.answer_payload} />
        </div>
        {message.intent && message.intent !== "unknown" && (
          <p className="mt-1 text-[11px] text-muted-foreground">
            intent {message.intent} · {fmtTime(message.created_at)}
          </p>
        )}
      </div>
    </div>
  );
}

