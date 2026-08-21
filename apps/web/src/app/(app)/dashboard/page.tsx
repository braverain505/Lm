"use client";

import { AccountantDashboard } from "@/components/dashboard/accountant";
import { ManagementDashboard } from "@/components/dashboard/management";
import { TeacherDashboard } from "@/components/dashboard/teacher";
import { useAuth } from "@/providers/auth-provider";

export default function DashboardPage() {
  const { activeSchool } = useAuth();
  const role = activeSchool?.role?.code ?? "";
  const perms = activeSchool?.permissions ?? [];

  // Teachers and homeroom teachers get the teacher-specific dashboard
  if (role === "teacher" || role === "homeroom_teacher") {
    return <TeacherDashboard />;
  }

  if (role === "accountant") return <AccountantDashboard />;

  const variant =
    perms.includes("results.verify") || role === "principal" || role === "vp_academics"
      ? "academic"
      : "admin";

  return <ManagementDashboard variant={variant === "academic" ? "academic" : "admin"} />;
}