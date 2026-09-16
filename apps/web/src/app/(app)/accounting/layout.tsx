"use client";

import { Lock } from "lucide-react";

import { useAuth } from "@/providers/auth-provider";

/**
 * Accountant-only gate for the whole accounting section.
 *
 * The API refuses every accounting route for anyone but the school's Accountant
 * (role code + permission, resolved per school), so this is a courtesy screen —
 * it explains *why* rather than showing a page that would fail on every request.
 * A platform super admin still passes: they own the platform and the API
 * bypasses the role check for them.
 */
export default function AccountingLayout({ children }: { children: React.ReactNode }) {
  const { user, activeSchool } = useAuth();
  const isAccountant = activeSchool?.role?.code === "accountant";
  const isPlatformAdmin = user?.is_superadmin ?? false;

  if (!isAccountant && !isPlatformAdmin) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-24 text-center">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-muted/60">
          <Lock className="h-6 w-6 text-muted-foreground/50" />
        </div>
        <h1 className="text-lg font-semibold">The accounting desk is Accountant-only</h1>
        <p className="max-w-md text-[13px] text-muted-foreground">
          Only this school&apos;s <strong>Accountant</strong> can keep the ledger, record
          expenses, reconcile the cashbook, chase debtors and issue receipts. A school admin
          can give someone the Accountant role — and their own login — from
          Teachers &amp; Staff.
        </p>
      </div>
    );
  }

  return <>{children}</>;
}
