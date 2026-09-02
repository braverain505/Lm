"use client";

import { motion } from "framer-motion";
import { AccountantDashboard } from "@/components/dashboard/accountant";
import { ManagementDashboard } from "@/components/dashboard/management";
import { TeacherDashboard } from "@/components/dashboard/teacher";
import { useAuth } from "@/providers/auth-provider";

const ease = [0.25, 0.46, 0.45, 0.94] as const;

export default function DashboardPage() {
  const { activeSchool } = useAuth();
  const role = activeSchool?.role?.code ?? "";

  // Teachers and homeroom teachers get the teacher-specific dashboard
  if (role === "teacher" || role === "homeroom_teacher") {
    return (
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, delay: 0.04, ease }}
      >
        <TeacherDashboard />
      </motion.div>
    );
  }

  if (role === "accountant") {
    return (
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, delay: 0.04, ease }}
      >
        <AccountantDashboard />
      </motion.div>
    );
  }

  const variant =
    perms.includes("results.verify") || role === "principal" || role === "vp_academics"
      ? "academic"
      : "admin";

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: 0.04, ease }}
    >
      <ManagementDashboard variant={variant === "academic" ? "academic" : "admin"} />
    </motion.div>
  );
}