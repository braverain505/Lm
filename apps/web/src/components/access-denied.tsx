"use client";

import { Lock } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/providers/auth-provider";

/**
 * Shown in place of a page the caller's role does not open.
 *
 * This is a courtesy screen, never the control: every gated area is enforced
 * again by the API on each request, so a user who types the URL directly gets a
 * 403 from the server rather than anything they should not see. Hiding the link
 * and rendering this panel just keeps the workspace honest about what is
 * available to the person looking at it.
 */
export function NoAccess({
  title,
  message,
  backHref = "/dashboard",
  backLabel = "Back to dashboard",
}: {
  title: string;
  message: string;
  backHref?: string;
  backLabel?: string;
}) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-2xl border border-border/60 bg-card px-6 py-14 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-muted">
        <Lock className="h-7 w-7 text-muted-foreground" />
      </div>
      <h2 className="text-xl font-semibold tracking-tight">{title}</h2>
      <p className="max-w-md text-sm text-muted-foreground">{message}</p>
      <Button asChild variant="outline" size="sm" className="mt-1">
        <Link href={backHref}>{backLabel}</Link>
      </Button>
    </div>
  );
}

/** Convenience: does the active membership hold this permission code? */
export function useHasPermission(code: string): boolean {
  const { activeSchool } = useAuth();
  return activeSchool?.permissions?.includes(code) ?? false;
}
