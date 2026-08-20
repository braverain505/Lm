"use client";

import { CheckCircle2, Send } from "lucide-react";
import { useState } from "react";

import { EmptyState, Panel, PanelSkeleton, StatCard, StatusBadge, fmtDateTime, titleCase } from "@/components/platform-utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useSaCreateTicket, useSaTickets, useSaUpdateTicket } from "@/hooks/use-superadmin";

export default function SuperAdminSupportPage() {
  const { data, isLoading } = useSaTickets();
  const create = useSaCreateTicket();
  const update = useSaUpdateTicket();

  const [subject, setSubject] = useState("");
  const [description, setDescription] = useState("");
  const [severity, setSeverity] = useState("medium");
  const [category, setCategory] = useState("general");

  const summary = (data?.summary ?? {}) as Record<string, number>;
  const items = (data?.items ?? []) as Array<{
    id: string; school_id: string | null; school_name: string | null; subject: string;
    category: string; severity: string; status: string; description: string | null;
    created_at: string; resolved_at: string | null;
  }>;

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!subject.trim()) return;
    create.mutate({ subject: subject.trim(), description: description || undefined, severity, category });
    setSubject("");
    setDescription("");
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Open tickets" value={summary.open} />
        <StatCard label="Critical / high" value={summary.critical} accent="text-destructive" />
        <StatCard label="Awaiting school" value={summary.awaiting_response} />
        <StatCard label="Resolved today" value={summary.resolved_today} accent="text-success" />
      </div>

      <Panel title="Open a ticket" subtitle="Log a platform-level support ticket">
        <form onSubmit={submit} className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1">
              <Label className="text-xs">Subject</Label>
              <Input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Payment question…" className="h-9" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label className="text-xs">Severity</Label>
                <Select value={severity} onValueChange={setSeverity}>
                  <SelectTrigger className="h-9 w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="low">Low</SelectItem>
                    <SelectItem value="medium">Medium</SelectItem>
                    <SelectItem value="high">High</SelectItem>
                    <SelectItem value="critical">Critical</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Category</Label>
                <Select value={category} onValueChange={setCategory}>
                  <SelectTrigger className="h-9 w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="general">General</SelectItem>
                    <SelectItem value="billing">Billing</SelectItem>
                    <SelectItem value="technical">Technical</SelectItem>
                    <SelectItem value="feature">Feature</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
          <Input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Details (optional)" className="h-9" />
          <Button type="submit" size="sm" disabled={create.isPending || !subject.trim()}>
            <Send className="h-3.5 w-3.5" /> {create.isPending ? "Opening…" : "Open ticket"}
          </Button>
        </form>
      </Panel>

      {isLoading ? (
        <PanelSkeleton rows={6} />
      ) : items.length === 0 ? (
        <div className="rounded-xl border bg-card">
          <EmptyState message="No support tickets yet." />
        </div>
      ) : (
        <Panel title="Tickets" subtitle={`${items.length} most recent`}>
          <div className="divide-y">
            {items.map((t) => (
              <div key={t.id} className="flex flex-wrap items-start justify-between gap-3 py-3">
                <div className="min-w-0 flex-1">
                  <p className="flex flex-wrap items-center gap-2 font-medium">
                    {t.subject}
                    <StatusBadge status={t.status} />
                  </p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {t.school_name ?? "Platform"} · {titleCase(t.category)} · {fmtDateTime(t.created_at)}
                  </p>
                  {t.description && <p className="mt-1 text-[13px] leading-relaxed text-muted-foreground">{t.description}</p>}
                </div>
                <div className="flex shrink-0 flex-col items-end gap-2">
                  <StatusBadge status={t.severity} />
                  <div className="flex items-center gap-1.5">
                    {t.status === "open" && (
                      <>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => update.mutate({ ticketId: t.id, body: { status: "in_progress" } })}
                        >
                          Start
                        </Button>
                        <Button
                          size="sm"
                          onClick={() => update.mutate({ ticketId: t.id, body: { status: "resolved" } })}
                        >
                          <CheckCircle2 className="h-3.5 w-3.5" /> Resolve
                        </Button>
                      </>
                    )}
                    {t.status === "in_progress" && (
                      <Button
                        size="sm"
                        onClick={() => update.mutate({ ticketId: t.id, body: { status: "resolved" } })}
                      >
                        <CheckCircle2 className="h-3.5 w-3.5" /> Resolve
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Panel>
      )}
    </div>
  );
}