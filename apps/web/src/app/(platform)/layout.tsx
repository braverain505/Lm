"use client";

import { ShieldAlert } from "lucide-react";
import { useRouter } from "next/navigation";
import { ReactNode, useEffect } from "react";

import { PlatformShell } from "@/components/platform-shell";
import { Card, CardContent } from "@/components/ui/card";
import { Loader } from "@/components/ui/loader";
import { useAuth } from "@/providers/auth-provider";

export default function PlatformLayout({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  if (loading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader />
      </div>
    );
  }

  if (!user.is_superadmin) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-muted/30 p-6">
        <Card className="max-w-md">
          <CardContent className="space-y-3 p-8 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-destructive/10">
              <ShieldAlert className="h-6 w-6 text-destructive" />
            </div>
            <h1 className="text-lg font-semibold">Platform admins only</h1>
            <p className="text-sm leading-relaxed text-muted-foreground">
              This area is reserved for Lumo platform administrators. Sign in with
              a super admin account to access the command center.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return <PlatformShell>{children}</PlatformShell>;
}