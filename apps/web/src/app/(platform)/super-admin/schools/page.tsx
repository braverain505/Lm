"use client";

import { Building2, Search } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { EmptyState, PanelSkeleton, ProgressBar, StatusBadge, fmtDate, fmtNum, titleCase } from "@/components/platform-utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useSaSchools } from "@/hooks/use-superadmin";

const PER_PAGE = 20;

export default function SuperAdminSchoolsPage() {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("all");
  const [plan, setPlan] = useState("all");
  const [sort, setSort] = useState("created_desc");
  const [page, setPage] = useState(1);

  const { data, isLoading } = useSaSchools({
    q: q || undefined,
    status: status === "all" ? undefined : status,
    plan: plan === "all" ? undefined : plan,
    sort,
    page,
    per_page: PER_PAGE,
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const pages = Math.max(1, data?.pages ?? 1);

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
            placeholder="Search name, slug, email…"
            className="h-9 pl-9"
          />
        </div>
        <Select
          value={status}
          onValueChange={(v) => {
            setStatus(v);
            setPage(1);
          }}
        >
          <SelectTrigger className="h-9 w-full sm:w-40">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="trial">Trial</SelectItem>
            <SelectItem value="past_due">Past due</SelectItem>
            <SelectItem value="expired">Expired</SelectItem>
            <SelectItem value="pending">Pending</SelectItem>
            <SelectItem value="suspended">Suspended</SelectItem>
          </SelectContent>
        </Select>
        <Select
          value={plan}
          onValueChange={(v) => {
            setPlan(v);
            setPage(1);
          }}
        >
          <SelectTrigger className="h-9 w-full sm:w-40">
            <SelectValue placeholder="Plan" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All plans</SelectItem>
            <SelectItem value="trial">Trial</SelectItem>
            <SelectItem value="starter">Starter</SelectItem>
            <SelectItem value="professional">Professional</SelectItem>
            <SelectItem value="enterprise">Enterprise</SelectItem>
          </SelectContent>
        </Select>
        <Select
          value={sort}
          onValueChange={(v) => {
            setSort(v);
            setPage(1);
          }}
        >
          <SelectTrigger className="h-9 w-full sm:w-44">
            <SelectValue placeholder="Sort" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="created_desc">Newest first</SelectItem>
            <SelectItem value="created_asc">Oldest first</SelectItem>
            <SelectItem value="name">Name (A–Z)</SelectItem>
            <SelectItem value="students">Most students</SelectItem>
            <SelectItem value="ai_usage">Most AI usage</SelectItem>
          </SelectContent>
        </Select>
        <p className="ml-auto text-sm text-muted-foreground">
          {fmtNum(total)} school{total === 1 ? "" : "s"}
        </p>
      </div>

      {isLoading ? (
        <PanelSkeleton rows={6} />
      ) : items.length === 0 ? (
        <div className="rounded-xl border bg-card">
          <EmptyState message="No schools match these filters." />
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((s) => (
            <Link
              key={s.id}
              href={`/super-admin/schools/${s.id}`}
              className="block rounded-xl border bg-card p-4 shadow-sm transition-all hover:border-primary/40 hover:shadow-md"
            >
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex min-w-0 items-center gap-3">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 font-semibold text-primary">
                    {s.name.charAt(0)}
                  </div>
                  <div className="min-w-0">
                    <p className="flex flex-wrap items-center gap-2 font-medium">
                      {s.name}
                      {s.ai_enabled && (
                        <Badge variant="info" className="gap-1">
                          AI
                        </Badge>
                      )}
                    </p>
                    <p className="truncate text-xs text-muted-foreground">
                      {s.slug} · {titleCase(s.school_type)} · {s.state ?? s.country} · joined {fmtDate(s.created_at)}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <div className="text-right">
                    <p className="font-semibold">{fmtNum(s.students)}</p>
                    <p className="text-[11px] text-muted-foreground">students</p>
                  </div>
                  <div className="text-right">
                    <p className="font-semibold">{titleCase(s.plan_name)}</p>
                    <p className="text-[11px] text-muted-foreground">plan</p>
                  </div>
                  <StatusBadge status={s.status} />
                </div>
              </div>
              {s.ai_credits_total > 0 && (
                <div className="mt-3 flex items-center gap-3">
                  <Building2 className="h-3.5 w-3.5 text-muted-foreground" />
                  <div className="flex-1">
                    <ProgressBar pct={(s.ai_credits_used / s.ai_credits_total) * 100} />
                  </div>
                  <span className="text-[11px] text-muted-foreground">
                    {fmtNum(s.ai_credits_used)} / {fmtNum(s.ai_credits_total)} AI credits
                  </span>
                </div>
              )}
            </Link>
          ))}
        </div>
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