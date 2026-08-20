"use client";

import { Building2, ShieldCheck, Sparkles, UserPlus, Users, UserX } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/providers/auth-provider";
import {
  useCreateSchoolAdmin,
  usePlatformSchools,
  usePlatformTeachers,
  useSetSchoolAi,
  useSetSchoolSuspended,
} from "@/hooks/use-api";

function fmtDate(iso: string): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

const ROLE_LABELS: Record<string, string> = {
  super_admin: "School admin",
  director: "Director",
  principal: "Principal",
  head_teacher: "Head teacher",
  teacher: "Teacher",
};

function CreateAdminCard({ schoolId }: { schoolId: string }) {
  const create = useCreateSchoolAdmin();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [created, setCreated] = useState<{ email: string; password: string | null } | null>(null);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !email.trim()) return;
    create.mutate(
      { schoolId, body: { full_name: name.trim(), email: email.trim() } },
      {
        onSuccess: (res) => {
          setCreated({ email: res.email, password: res.password });
          setName("");
          setEmail("");
        },
      },
    );
  };

  return (
    <div className="rounded-xl border bg-muted/30 p-3">
      {created ? (
        <div className="space-y-2 text-sm">
          <p className="font-medium">Admin created — {created.email}</p>
          {created.password && (
            <p className="rounded-lg bg-amber-500/10 px-3 py-2 text-xs leading-relaxed text-amber-700 dark:text-amber-300">
              Temporary password: <code className="font-semibold">{created.password}</code>
              <br />
              Share it with the school owner now — it won&apos;t be shown again.
            </p>
          )}
          <p className="text-xs text-muted-foreground">
            Sign in at the school&apos;s login, then change the password.
          </p>
          <Button size="sm" variant="outline" onClick={() => setCreated(null)}>
            Create another
          </Button>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-3">
          <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            <UserPlus className="h-3.5 w-3.5" /> Create school admin
          </p>
          <div className="grid gap-3 sm:grid-cols-[1fr_1fr_auto]">
            <div className="space-y-1">
              <Label htmlFor={`admin-name-${schoolId}`} className="text-xs">
                Full name
              </Label>
              <Input
                id={`admin-name-${schoolId}`}
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Mrs. Adebayo"
                className="h-9"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor={`admin-email-${schoolId}`} className="text-xs">
                Email
              </Label>
              <Input
                id={`admin-email-${schoolId}`}
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="admin@school.edu"
                className="h-9"
              />
            </div>
            <Button type="submit" size="sm" className="mt-auto" disabled={create.isPending || !name.trim() || !email.trim()}>
              {create.isPending ? "Creating…" : "Create"}
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}

function SchoolRow({ school }: { school: { id: string; name: string; slug: string; school_type: string; email: string | null; created_at: string; students: number; class_arms: number; ai_enabled: boolean; suspended: boolean } }) {
  const toggleAi = useSetSchoolAi();
  const toggleSuspended = useSetSchoolSuspended();

  return (
    <Card className={school.suspended ? "opacity-70" : undefined}>
      <CardContent className="space-y-3 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 font-semibold text-primary">
              {school.name.charAt(0)}
            </div>
            <div className="min-w-0">
              <p className="flex flex-wrap items-center gap-2 font-medium">
                {school.name}
                {school.ai_enabled && (
                  <Badge variant="warning" className="gap-1">
                    <Sparkles className="h-3 w-3" /> Premium AI
                  </Badge>
                )}
                {school.suspended && (
                  <Badge variant="destructive" className="gap-1">
                    <UserX className="h-3 w-3" /> Disabled
                  </Badge>
                )}
              </p>
              <p className="truncate text-xs text-muted-foreground">
                {school.slug} · {school.school_type} · {school.email ?? "no email"} · registered {fmtDate(school.created_at)}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-5 text-sm">
            <div className="text-center">
              <p className="font-semibold">{school.students}</p>
              <p className="text-xs text-muted-foreground">students</p>
            </div>
            <div className="text-center">
              <p className="font-semibold">{school.class_arms}</p>
              <p className="text-xs text-muted-foreground">class arms</p>
            </div>
            <div className="flex flex-col gap-1.5">
              <Button
                size="sm"
                variant={school.ai_enabled ? "outline" : "default"}
                onClick={() => toggleAi.mutate({ schoolId: school.id, enabled: !school.ai_enabled })}
                disabled={toggleAi.isPending || school.suspended}
                className="gap-1.5"
              >
                <Sparkles className="h-3.5 w-3.5" />
                {school.ai_enabled ? "Disable AI" : "Enable AI"}
              </Button>
              <Button
                size="sm"
                variant={school.suspended ? "default" : "outline"}
                onClick={() => toggleSuspended.mutate({ schoolId: school.id, suspended: !school.suspended })}
                disabled={toggleSuspended.isPending}
                className="gap-1.5"
              >
                <UserX className="h-3.5 w-3.5" />
                {school.suspended ? "Re-enable school" : "Disable school"}
              </Button>
            </div>
          </div>
        </div>

        <CreateAdminCard schoolId={school.id} />
      </CardContent>
    </Card>
  );
}

function TeachersPanel() {
  const { data: teachers = [], isLoading } = usePlatformTeachers();

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Users className="h-4 w-4" /> Teacher accounts across every school
        </CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="space-y-2">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
          </div>
        ) : teachers.length === 0 ? (
          <p className="py-4 text-center text-sm text-muted-foreground">No teacher accounts yet.</p>
        ) : (
          <div className="divide-y">
            {teachers.map((t) => (
              <div key={t.user_id} className="flex flex-wrap items-center justify-between gap-2 py-2.5 text-sm">
                <div className="min-w-0">
                  <p className="font-medium">{t.full_name}</p>
                  <p className="truncate text-xs text-muted-foreground">{t.email}</p>
                </div>
                <div className="flex items-center gap-3">
                  <span className="max-w-[14rem] truncate text-xs text-muted-foreground">{t.school_name}</span>
                  <Badge variant="outline">{ROLE_LABELS[t.role_code] ?? t.role_code}</Badge>
                  {t.status !== "active" && <Badge variant="destructive">{t.status}</Badge>}
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function AdminPage() {
  const { user } = useAuth();
  const { data: schools = [], isLoading } = usePlatformSchools();
  const { data: teachers = [] } = usePlatformTeachers();

  if (!user?.is_superadmin) {
    return (
      <div className="flex flex-col items-center gap-3 py-24 text-center">
        <ShieldCheck className="h-10 w-10 text-muted-foreground" />
        <h1 className="text-lg font-semibold">Lumo platform admin only</h1>
        <p className="max-w-sm text-sm text-muted-foreground">
          Only Lumo&apos;s own platform administrators can see every school and
          manage premium subscriptions.
        </p>
      </div>
    );
  }

  const aiSchools = schools.filter((s) => s.ai_enabled).length;
  const activeSchools = schools.filter((s) => !s.suspended).length;

  return (
    <div className="space-y-8">
      {/* Hero */}
      <div className="relative overflow-hidden rounded-2xl border bg-gradient-to-br from-primary via-primary/80 to-primary/40 p-6 text-primary-foreground sm:p-8">
        <div className="pointer-events-none absolute -right-16 -top-16 h-56 w-56 rounded-full bg-white/10 blur-2xl" />
        <div className="pointer-events-none absolute -bottom-20 right-24 h-40 w-40 rounded-full bg-white/10 blur-xl" />
        <div className="relative space-y-4">
          <Badge className="gap-1 border-white/20 bg-white/10 text-primary-foreground">
            <ShieldCheck className="h-3 w-3" /> Lumo Platform
          </Badge>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
              Command center
            </h1>
            <p className="max-w-2xl text-sm text-primary-foreground/80">
              Every school on Lumo at a glance — enable premium AI, manage access,
              and support your tenants from one place.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <StatChip label="Schools" value={schools.length} />
            <StatChip label="Active" value={activeSchools} />
            <StatChip label="Premium AI" value={aiSchools} />
            <StatChip label="Teacher accounts" value={teachers.length} />
          </div>
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
        </div>
      ) : schools.length === 0 ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            No schools registered yet.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {schools.map((school) => (
            <SchoolRow key={school.id} school={school} />
          ))}
        </div>
      )}

      <TeachersPanel />

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">How platform control works</CardTitle>
        </CardHeader>
        <CardContent className="flex items-start gap-2 text-sm text-muted-foreground">
          <Building2 className="mt-0.5 h-4 w-4 shrink-0" />
          <p>
            <strong className="text-foreground">Premium AI</strong> unlocks the school&apos;s AI
            tools after they pay. <strong className="text-foreground">Disable school</strong>{" "}
            blocks every request from that school instantly ({" "}
            <code className="rounded bg-muted px-1">ERR_SCHOOL_SUSPENDED</code> ) — use it for
            unpaid or problematic tenants. <strong className="text-foreground">Create admin</strong>{" "}
            makes a school super admin whose credentials Lumo can hand over. Teacher passwords
            are hashed and never shown; view the account list for support and recovery.
          </p>
        </CardContent>
        <CardContent className="pt-0 text-xs text-muted-foreground">
          <Link href="/dashboard" className="underline">
            Back to your school →
          </Link>
        </CardContent>
      </Card>
    </div>
  );
}

function StatChip({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border border-white/20 bg-white/10 px-4 py-2 backdrop-blur">
      <p className="text-lg font-semibold leading-none">{value}</p>
      <p className="mt-0.5 text-[11px] uppercase tracking-wide text-primary-foreground/70">
        {label}
      </p>
    </div>
  );
}