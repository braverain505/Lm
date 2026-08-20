"use client";

import { Search } from "lucide-react";
import { useState } from "react";

import { EmptyState, Panel, PanelSkeleton, StatusBadge, fmtDateTime, fmtNum, titleCase } from "@/components/platform-utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useSaAudit } from "@/hooks/use-superadmin";

const PER_PAGE = 30;

export default function SuperAdminAuditPage() {
  const [q, setQ] = useState("");
  const [action, setAction] = useState("all");
  const [entity, setEntity] = useState("all");
  const [page, setPage] = useState(1);

  const { data, isLoading } = useSaAudit({
    q: q || undefined,
    action: action === "all" ? undefined : action,
    entity: entity === "all" ? undefined : entity,
    page,
    per_page: PER_PAGE,
  });

  const items = (data?.items ?? []) as Array<{
    id: string; ts: string; action: string; entity_type: string; entity_id: string | null;
    school_id: string | null; school_name: string | null; actor: string; ip: string | null; details: string | null;
  }>;
  const total = data?.total ?? 0;
  const pages = Math.max(1, data?.pages ?? 1);

  const actions = Array.from(new Set(items.map((i) => i.action))).slice(0, 12);
  const entities = Array.from(new Set(items.map((i) => i.entity_type))).slice(0, 12);

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative w-full sm:max-w-xs">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setPage(1);
            }}
            placeholder="Search details, school, actor…"
            className="h-9 pl-9"
          />
        </div>
        {actions.length > 0 && (
          <Select
            value={action}
            onValueChange={(v) => {
              setAction(v);
              setPage(1);
            }}
          >
            <SelectTrigger className="h-9 w-40">
              <SelectValue placeholder="Action" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All actions</SelectItem>
              {actions.map((a) => (
                <SelectItem key={a} value={a}>
                  {titleCase(a)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
        {entities.length > 0 && (
          <Select
            value={entity}
            onValueChange={(v) => {
              setEntity(v);
              setPage(1);
            }}
          >
            <SelectTrigger className="h-9 w-44">
              <SelectValue placeholder="Entity" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All entities</SelectItem>
              {entities.map((e) => (
                <SelectItem key={e} value={e}>
                  {titleCase(e)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
        <p className="ml-auto text-sm text-muted-foreground">{fmtNum(total)} events</p>
      </div>

      {isLoading ? (
        <PanelSkeleton rows={8} />
      ) : items.length === 0 ? (
        <div className="rounded-xl border bg-card">
          <EmptyState message="No audit events match these filters." />
        </div>
      ) : (
        <Panel title="Audit trail" subtitle="Immutable platform + school events">
          <div className="divide-y">
            {items.map((e) => (
              <div key={e.id} className="flex flex-wrap items-start justify-between gap-3 py-3">
                <div className="min-w-0 flex-1">
                  <p className="flex flex-wrap items-center gap-2 text-sm font-medium">
                    {titleCase(e.action)}
                    <span className="text-muted-foreground">{titleCase(e.entity_type)}</span>
                    {e.school_name && <span className="text-xs text-muted-foreground">· {e.school_name}</span>}
                  </p>
                  {e.details && <p className="mt-0.5 text-[13px] text-muted-foreground">{e.details}</p>}
                  <p className="mt-0.5 text-[11px] text-muted-foreground/70">
                    {e.actor}{e.ip ? ` · ${e.ip}` : ""} · {fmtDateTime(e.ts)}
                  </p>
                </div>
                <StatusBadge status={e.action === "create" ? "resolved" : e.action === "update" ? "active" : "muted"} />
              </div>
            ))}
          </div>
        </Panel>
      )}

      {pages > 1 && (
        <div className="flex items-center justify-between pt-2">
          <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>
            Previous
          </Button>
          <span className="text-sm text-muted-foreground">
            Page {page} of {pages}
          </span>
          <Button variant="outline" size="sm" disabled={page >= pages} onClick={() => setPage((p) => Math.min(pages, p + 1))}>
            Next
          </Button>
        </div>
      )}
    </div>
  );
}