"use client";

import { motion } from "framer-motion";

import { useSessionTerm } from "@/providers/session-context";
import { useAuth } from "@/providers/auth-provider";

const ease = [0.25, 0.46, 0.45, 0.94] as const;

function Greeting() {
  const { user } = useAuth();
  const { term } = useSessionTerm();
  const hour = new Date().getHours();
  const part = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
  const today = new Date().toLocaleDateString(undefined, {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease }}
    >
      <h2 className="text-[26px] font-bold tracking-tight text-foreground">
        {part}, {user?.full_name?.split(" ")[0] ?? "there"}.
      </h2>
      <p className="mt-1.5 text-[14px] text-muted-foreground/70">
        Here&apos;s what&apos;s happening today — {today}
      </p>
      {term && (
        <p className="mt-1 text-[13px] font-medium text-muted-foreground/50">{term.name}</p>
      )}
    </motion.div>
  );
}

export function ManagementDashboard({ variant }: { variant: "admin" | "academic" }) {
  return (
    <div className="space-y-8">
      <Greeting />
    </div>
  );
}
