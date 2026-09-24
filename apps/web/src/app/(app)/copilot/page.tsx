"use client";

import { Bot, MessageSquare, Plus, Send, Sparkles, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import type { CopilotMessage } from "@clearis/shared";
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
  useDeleteConversation,
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

// Command outcomes carry an `action` object rather than an intent-shaped payload:
// a pending proposal, a denial, a cancellation, or what a confirmed run changed.
const ACTION_TONES: Record<string, string> = {
  pending: "border-amber-300 bg-amber-50 text-amber-900",
  done: "border-emerald-300 bg-emerald-50 text-emerald-900",
  denied: "border-rose-300 bg-rose-50 text-rose-900",
  failed: "border-rose-300 bg-rose-50 text-rose-900",
  cancelled: "border-input bg-muted/40 text-muted-foreground",
};

const ACTION_LABELS: Record<string, string> = {
  pending: "Awaiting confirmation",
  done: "Done",
  denied: "Not permitted",
  failed: "Failed",
  cancelled: "Cancelled",
};

function ActionCard({ action }: { action: Record<string, unknown> }) {
  const status = String(action.status ?? "");
  const result = (action.result ?? {}) as Record<string, unknown>;
  const totals = result.totals as Record<string, unknown> | undefined;
  const entries: Array<[string, string]> = [];
  if (result.admission_no) entries.push(["Admission no", String(result.admission_no)]);
  if (result.class_arm) entries.push(["Class", String(result.class_arm)]);
  if (result.staff_no) entries.push(["Staff no", String(result.staff_no)]);
  if (result.name) entries.push(["Name", String(result.name)]);
  if (totals && typeof totals === "object") {
    for (const [key, value] of Object.entries(totals)) entries.push([key, String(value)]);
  }
  const missing = Array.isArray(action.missing) ? (action.missing as unknown[]) : [];

  return (
    <div
      className={cn(
        "mt-2 rounded-md border px-3 py-2",
        ACTION_TONES[status] ?? "border-input bg-muted/40",
      )}
    >
      <p className="text-[11px] font-semibold uppercase tracking-wide">
        {ACTION_LABELS[status] ?? status}
      </p>
      {action.detail ? <p className="mt-1 text-sm">{String(action.detail)}</p> : null}
      {action.error ? <p className="mt-1 text-sm">{String(action.error)}</p> : null}
      {missing.length > 0 ? (
        <p className="mt-1 text-xs">Still needed: {missing.map(String).join(", ")}</p>
      ) : null}
      {entries.length > 0 ? (
        <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3">
          {entries.map(([label, value]) => (
            <Stat key={label} label={label} value={value} />
          ))}
        </div>
      ) : null}
    </div>
  );
}

function PayloadCard({ payload }: { payload: Record<string, unknown> | null }) {
  if (!payload) return null;
  const intent = typeof payload.intent === "string" ? payload.intent : "";

  // A command turn: proposal, denial, cancellation or result.
  const action = payload.action;
  if (action && typeof action === "object") {
    return <ActionCard action={action as Record<string, unknown>} />;
  }

  if (intent === "class_roster" && Array.isArray(payload.students)) {
    const rows = payload.students as Record<string, unknown>[];
    if (rows.length === 0) return null;
    return (
      <div className="mt-2 overflow-hidden rounded-md border bg-background">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 text-xs text-muted-foreground">
            <tr>
              <th className="px-3 py-2 text-left font-medium">#</th>
              <th className="px-3 py-2 text-left font-medium">Student</th>
              <th className="px-3 py-2 text-left font-medium">Admission no</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-t">
                <td className="px-3 py-2 text-muted-foreground">{i + 1}</td>
                <td className="px-3 py-2">{String(r.full_name ?? "")}</td>
                <td className="px-3 py-2 font-mono text-xs text-muted-foreground">
                  {String(r.admission_no ?? "")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  if (intent === "top_performers" && Array.isArray(payload.rows)) {
    const rows = payload.rows as Record<string, unknown>[];
    return (
      <div className="mt-2 overflow-hidden rounded-md border bg-background">
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
  const scrollRef = useRef<HTMLDivElement>(null);

  const { data: conversations = [], isLoading: railLoading } = useConversations();
  const { data: conversation, isLoading: threadLoading } = useConversation(activeConvId);
  const { data: intents = [] } = useCopilotIntents();
  const ask = useAskCopilot();
  const del = useDeleteConversation();

  const messages: CopilotMessage[] = conversation?.messages ?? [];
  const activeConv = conversations.find((c) => c.id === activeConvId) ?? null;

  // Messenger behavior: the newest message is always the one you're reading.
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages.length, thinking, activeConvId]);

  const newChat = () => {
    setActiveConvId(null);
    setScopeTermId(null);
    setInput("");
    setThinking(null);
  };

  const removeChat = (id: string, title: string) => {
    if (
      !window.confirm(
        `Delete “${title}”? This removes the chat and its messages for everyone.`,
      )
    ) {
      return;
    }
    del.mutate(id, {
      onSuccess: () => setActiveConvId((cur) => (cur === id ? null : cur)),
    });
  };

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
          records — no invented numbers. You can also give it commands (like
          &ldquo;add Genesis John to Nursery 1&rdquo;): it shows you exactly what
          will change and waits for you to reply &ldquo;confirm&rdquo;. Every
          turn is metered under ai.copilot.
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
    <div className="space-y-4">
      {header}

      {/* The messenger window: sidebar + thread in one rounded frame. */}
      <div className="flex h-[calc(100vh-12rem)] min-h-[28rem] overflow-hidden rounded-xl border bg-card shadow-sm">
        {/* Sidebar: saved conversations */}
        <aside className="hidden w-72 shrink-0 flex-col border-r bg-muted/20 sm:flex">
          <div className="flex items-center justify-between gap-2 border-b px-3 py-3">
            <p className="text-sm font-semibold">Chats</p>
            <Button size="sm" variant="outline" onClick={newChat}>
              <Plus className="mr-1 h-4 w-4" />
              New
            </Button>
          </div>
          <div className="flex-1 space-y-1 overflow-y-auto p-2">
            {railLoading &&
              Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-14 w-full rounded-lg" />
              ))}
            {!railLoading && conversations.length === 0 && (
              <p className="px-2 py-6 text-center text-xs text-muted-foreground">
                No conversations yet
              </p>
            )}
            {conversations.map((c) => (
              <div
                key={c.id}
                className={cn(
                  "group flex items-center gap-1 rounded-lg transition-colors",
                  c.id === activeConvId ? "bg-primary/10" : "hover:bg-accent",
                )}
              >
                <button
                  onClick={() => {
                    setActiveConvId(c.id);
                    setThinking(null);
                  }}
                  className="flex min-w-0 flex-1 items-center gap-2 px-2 py-2 text-left"
                >
                  <span
                    className={cn(
                      "flex h-9 w-9 shrink-0 items-center justify-center rounded-full",
                      c.id === activeConvId
                        ? "bg-primary/15 text-primary"
                        : "bg-muted text-muted-foreground",
                    )}
                  >
                    <MessageSquare className="h-4 w-4" />
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-medium">{c.title}</span>
                    <span className="block truncate text-xs text-muted-foreground">
                      {fmtTime(c.created_at)}
                    </span>
                  </span>
                </button>
                <button
                  onClick={() => removeChat(c.id, c.title)}
                  aria-label={`Delete chat ${c.title}`}
                  title="Delete chat"
                  className="mr-1 rounded-md p-1.5 text-muted-foreground opacity-0 transition-opacity hover:bg-destructive/10 hover:text-destructive focus-visible:opacity-100 group-hover:opacity-100"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        </aside>

        {/* Thread */}
        <div className="flex min-w-0 flex-1 flex-col">
          {/* Chat header */}
          <header className="flex items-center gap-3 border-b px-3 py-3 sm:px-4">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary to-primary/60 text-primary-foreground">
              <Bot className="h-5 w-5" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold">
                {activeConv?.title ?? "School copilot"}
              </p>
              <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                Grounded in your school&apos;s own records
              </p>
            </div>

            {/* On phones the sidebar is hidden, so switching threads lives here. */}
            <select
              value={activeConvId ?? ""}
              onChange={(e) => {
                setActiveConvId(e.target.value || null);
                setThinking(null);
                setScopeTermId(null);
              }}
              className="max-w-[9rem] truncate rounded-md border border-input bg-transparent px-2 py-1 text-xs sm:hidden"
              aria-label="Switch chat"
            >
              <option value="">New chat</option>
              {conversations.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.title}
                </option>
              ))}
            </select>

            <Button
              variant="ghost"
              size="icon"
              onClick={newChat}
              aria-label="New chat"
              title="New chat"
              className="sm:hidden"
            >
              <Plus className="h-4 w-4" />
            </Button>
            {activeConvId && (
              <Button
                variant="ghost"
                size="icon"
                onClick={() =>
                  removeChat(activeConvId, activeConv?.title ?? "this chat")
                }
                aria-label="Delete this chat"
                title="Delete this chat"
                className="hover:bg-destructive/10 hover:text-destructive"
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            )}
          </header>

          {/* Term scope — only meaningful for a chat that has not started yet. */}
          <div className="flex flex-wrap items-center gap-2 border-b bg-muted/20 px-3 py-2 sm:px-4">
            {activeConvId ? (
              <span className="text-xs text-muted-foreground">
                Scoped to{" "}
                {terms.find((t) => t.id === conversation?.term_id)?.name ?? "the current term"}
              </span>
            ) : (
              <>
                <span className="text-xs text-muted-foreground">New-chat term scope</span>
                {terms.map((t) => (
                  <button
                    key={t.id}
                    onClick={() => setScopeTermId(scopeTermId === t.id ? null : t.id)}
                    className={cn(
                      "rounded-full border px-2.5 py-1 text-xs font-medium transition-colors",
                      scopeTermId === t.id
                        ? "border-primary bg-primary/10 text-primary"
                        : "border-input text-muted-foreground hover:bg-accent",
                    )}
                  >
                    {t.name}
                  </button>
                ))}
              </>
            )}
          </div>

          {/* Messages */}
          <div
            ref={scrollRef}
            className="flex-1 space-y-3 overflow-y-auto bg-muted/10 px-3 py-4 sm:px-5"
          >
            {activeConvId && threadLoading && (
              <div className="space-y-3">
                <Skeleton className="ml-auto h-9 w-2/3 rounded-2xl" />
                <Skeleton className="h-16 w-3/4 rounded-2xl" />
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
                <div className="flex items-end gap-2">
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary to-primary/60 text-primary-foreground">
                    <Bot className="h-3.5 w-3.5" />
                  </div>
                  <div className="flex items-center gap-1 rounded-2xl rounded-bl-sm border bg-background px-3 py-2 text-sm text-muted-foreground">
                    <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-primary" />
                    Thinking…
                  </div>
                </div>
              </>
            )}
          </div>

          {/* Composer */}
          <div className="border-t bg-card p-3">
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
                placeholder="Message the copilot… (try “add Genesis John to Nursery 1”)"
                className="max-h-32 min-h-[2.75rem] flex-1 resize-y rounded-2xl border border-input bg-transparent px-3.5 py-3 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              />
              <Button
                type="submit"
                size="icon"
                className="h-11 w-11 shrink-0 rounded-full"
                disabled={!input.trim() || ask.isPending}
                aria-label="Send"
              >
                <Send className="h-4 w-4" />
              </Button>
            </form>
            <p className="mt-2 flex items-center gap-1 text-[11px] text-muted-foreground">
              <Sparkles className="h-3 w-3" />
              AI copilot · clearis-copilot-v1 · deterministic and data-grounded ·
              commands are permission-checked, confirmed before they run, and
              audited
            </p>
          </div>
        </div>
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
        Counts, class lists, subjects, score-entry progress, published results,
        top performers and term averages — answered from your school&apos;s own
        records. You can also ask it to do things: admit a student, add a
        teacher, create a subject or class, or run results through to
        published.
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
      <div className="flex flex-col items-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-primary px-3.5 py-2.5 text-sm text-primary-foreground">
          {message.content}
        </div>
        <p className="mt-1 pr-1 text-[10px] text-muted-foreground">
          {fmtTime(message.created_at)}
        </p>
      </div>
    );
  }
  return (
    <div className="flex items-end gap-2">
      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary to-primary/60 text-primary-foreground">
        <Bot className="h-3.5 w-3.5" />
      </div>
      <div className="max-w-[92%]">
        <div className="rounded-2xl rounded-bl-sm border bg-background px-3.5 py-2.5 shadow-sm">
          <p className="whitespace-pre-wrap text-sm">{message.content}</p>
          <PayloadCard payload={message.answer_payload} />
        </div>
        <p className="mt-1 pl-1 text-[10px] text-muted-foreground">
          {fmtTime(message.created_at)}
        </p>
      </div>
    </div>
  );
}
