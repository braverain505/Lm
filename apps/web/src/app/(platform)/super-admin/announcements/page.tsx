"use client";

import { Megaphone } from "lucide-react";
import { useState } from "react";

import { EmptyState, Panel, PanelSkeleton, StatusBadge, fmtDate, titleCase } from "@/components/platform-utils";
import { Badge } from "@/components/ui/badge";
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
import { useSaAnnouncements, useSaCreateAnnouncement } from "@/hooks/use-superadmin";

export default function SuperAdminAnnouncementsPage() {
  const { data, isLoading } = useSaAnnouncements();
  const create = useSaCreateAnnouncement();

  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [audience, setAudience] = useState("all");
  const [severity, setSeverity] = useState("info");

  const items = (data ?? []) as Array<{
    id: string; title: string; body: string; audience: string; severity: string; is_active: boolean; created_at: string;
  }>;

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim() || !body.trim()) return;
    create.mutate({ title: title.trim(), body: body.trim(), audience, severity });
    setTitle("");
    setBody("");
  }

  return (
    <div className="space-y-6">
      <Panel title="Post an announcement" subtitle="Shown to every tenant (or a targeted audience)">
        <form onSubmit={submit} className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="space-y-1 sm:col-span-1">
              <Label className="text-xs">Title</Label>
              <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Scheduled maintenance…" className="h-9" />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Audience</Label>
              <Select value={audience} onValueChange={setAudience}>
                <SelectTrigger className="h-9 w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All schools</SelectItem>
                  <SelectItem value="admins">School admins</SelectItem>
                  <SelectItem value="teachers">Teachers</SelectItem>
                  <SelectItem value="parents">Parents</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Severity</Label>
              <Select value={severity} onValueChange={setSeverity}>
                <SelectTrigger className="h-9 w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="info">Info</SelectItem>
                  <SelectItem value="warning">Warning</SelectItem>
                  <SelectItem value="critical">Critical</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Message</Label>
            <Input value={body} onChange={(e) => setBody(e.target.value)} placeholder="Details…" className="h-9" />
          </div>
          <Button type="submit" size="sm" disabled={create.isPending || !title.trim() || !body.trim()}>
            <Megaphone className="h-3.5 w-3.5" /> {create.isPending ? "Posting…" : "Post announcement"}
          </Button>
        </form>
      </Panel>

      <Panel title="Active announcements" subtitle="Most recent 50">
        {isLoading ? (
          <PanelSkeleton rows={5} />
        ) : items.length === 0 ? (
          <EmptyState message="No announcements yet." />
        ) : (
          <div className="divide-y">
            {items.map((a) => (
              <div key={a.id} className="flex flex-wrap items-start justify-between gap-3 py-3">
                <div className="min-w-0 flex-1">
                  <p className="flex flex-wrap items-center gap-2 font-medium">
                    {a.title}
                    <Badge variant="outline">{titleCase(a.audience)}</Badge>
                    {a.is_active && <Badge variant="success">Active</Badge>}
                  </p>
                  <p className="mt-0.5 text-[13px] text-muted-foreground">{a.body}</p>
                  <p className="mt-0.5 text-[11px] text-muted-foreground/70">Posted {fmtDate(a.created_at)}</p>
                </div>
                <StatusBadge status={a.severity} />
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}