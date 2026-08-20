"use client";

import { AccountantDashboard } from "@/components/dashboard/accountant";
import { ManagementDashboard } from "@/components/dashboard/management";
import { useAuth } from "@/providers/auth-provider";

export default function DashboardPage() {
  const { activeSchool } = useAuth();
  const role = activeSchool?.role?.code ?? "";
  const perms = activeSchool?.permissions ?? [];

  const variant =
    role === "accountant"
      ? "accountant"
      : perms.includes("results.verify") || role === "principal" || role === "vp_academics"
        ? "academic"
        : "admin";

  if (variant === "accountant") return <AccountantDashboard />;
  return <ManagementDashboard variant={variant === "academic" ? "academic" : "admin"} />;
}