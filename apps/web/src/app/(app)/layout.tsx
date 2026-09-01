"use client";

import { Ban, Eye, ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { ReactNode, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Loader } from "@/components/ui/loader";
import { useAuth } from "@/providers/auth-provider";
import { api } from "@schoolos/shared";

export default function AppLayout({ children }: { children: ReactNode }) {
  const { user, activeSchool, memberships, loading, refreshMe } = useAuth();
  const router = useRouter();
  const [impersonating, setImpersonating] = useState(false);

  useEffect(() => {
    try {
      setImpersonating(localStorage.getItem("schoolos.impersonating") === "1");
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  useEffect(() => {
    // Platform admins with no school membership have nothing to do in the
    // school workspace — take them to the command center.
    if (!loading && user?.is_superadmin && memberships.length === 0) {
      router.replace("/admin");
    }
  }, [loading, user, memberships, router]);

  async function exitImpersonation() {
    try {
      await api.impersonateExit();
      try {
        localStorage.removeItem("schoolos.impersonating");
      } catch {
        /* ignore */
      }
      await refreshMe();
      router.replace("/super-admin");
    } finally {
      setImpersonating(false);
    }
  }

  if (loading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader />
      </div>
    );
  }

  if (activeSchool?.suspended) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-muted/30 p-6">
        <Card className="max-w-md">
          <CardContent className="space-y-3 p-8 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-destructive/10">
              <Ban className="h-6 w-6 text-destructive" />
            </div>
            <Badge variant="destructive">School disabled</Badge>
            <h1 className="text-lg font-semibold">{activeSchool.school_name} is disabled</h1>
            <p className="text-sm leading-relaxed text-muted-foreground">
              This school has been suspended by Clearis. Access is blocked until it
              is re-enabled. Contact Clearis support for help.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (impersonating) {
    return (
      <div className="min-h-screen bg-background">
        <div className="flex flex-wrap items-center gap-3 border-b bg-amber-500/10 px-4 py-2.5 text-sm">
          <span className="flex items-center gap-2 font-medium text-amber-700 dark:text-amber-300">
            <Eye className="h-4 w-4" /> Viewing as {activeSchool?.school_name} admin
          </span>
          <span className="text-xs text-muted-foreground">
            You are impersonating this school&apos;s admin to troubleshoot. Actions are audited.
          </span>
          <Button size="sm" variant="outline" className="ml-auto" onClick={exitImpersonation}>
            Exit impersonation
          </Button>
        </div>
        {children}
      </div>
    );
  }

  return <AppShell>{children}</AppShell>;
}