"use client";

import { Ban, Eye, Mail, ArrowRight, ShieldAlert } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ReactNode, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
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
      <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-background px-4 py-12">
        {/* Background orbs */}
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute -left-[15%] -top-[15%] h-[500px] w-[500px] rounded-full bg-destructive/[0.03] blur-[120px]" />
          <div className="absolute -bottom-[15%] -right-[15%] h-[400px] w-[400px] rounded-full bg-amber-500/[0.03] blur-[100px]" />
        </div>

        <div className="relative z-10 w-full max-w-[460px]">
          {/* Logo */}
          <div className="mb-10 flex flex-col items-center gap-2">
            <Image
              src="/clearisbg.png"
              alt="Clearis"
              width={1536}
              height={1024}
              priority
              className="h-16 w-auto object-contain opacity-80"
            />
          </div>

          {/* Card */}
          <div className="rounded-2xl border border-border/40 bg-white/80 p-10 text-center shadow-[0_1px_3px_rgba(0,0,0,0.04)] backdrop-blur-sm dark:bg-white/5">
            {/* Icon */}
            <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-red-50 to-amber-50 ring-1 ring-red-100/80">
              <ShieldAlert className="h-7 w-7 text-red-500" />
            </div>

            {/* Badge */}
            <div className="mb-4 inline-flex items-center gap-1.5 rounded-full bg-red-50 px-3 py-1 text-[11px] font-semibold uppercase tracking-wider text-red-600 ring-1 ring-red-100/80">
              <Ban className="h-3 w-3" />
              School Suspended
            </div>

            {/* Title */}
            <h1 className="text-[22px] font-bold tracking-tight text-foreground">
              {activeSchool.school_name}
            </h1>
            <p className="mt-1 text-[14px] font-medium text-red-500/80">
              Access has been temporarily suspended
            </p>

            {/* Description */}
            <p className="mt-5 text-[13px] leading-relaxed text-muted-foreground">
              This school has been suspended by <span className="font-semibold text-foreground/70">Clearis</span>. All access is blocked until the suspension is lifted by our team.
            </p>

            {/* Divider */}
            <div className="my-7 h-px bg-gradient-to-r from-transparent via-border to-transparent" />

            {/* What to do */}
            <div className="mx-auto mb-7 max-w-[300px] space-y-3 text-left">
              {[
                { step: "1", text: "Contact Clearis support" },
                { step: "2", text: "Provide your school details" },
                { step: "3", text: "Access will be restored" },
              ].map((item) => (
                <div key={item.step} className="flex items-center gap-3">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-muted text-[10px] font-bold text-muted-foreground">
                    {item.step}
                  </span>
                  <span className="text-[13px] text-muted-foreground">{item.text}</span>
                </div>
              ))}
            </div>

            {/* CTA */}
            <a href="mailto:support@clearis.com">
              <Button className="h-11 w-full text-[13px] font-semibold" variant="outline">
                <Mail className="mr-2 h-4 w-4" />
                Contact Support
                <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
              </Button>
            </a>
          </div>

          {/* Footer */}
          <p className="mt-6 text-center text-[11px] text-muted-foreground/50">
            Clearis School Management Platform
          </p>
        </div>
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