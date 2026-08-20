"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { Loader } from "@/components/ui/loader";
import { useAuth } from "@/providers/auth-provider";

export default function HomePage() {
  const { user, memberships, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.replace("/login");
    } else if (user.is_superadmin && memberships.length === 0) {
      router.replace("/super-admin");
    } else {
      router.replace("/dashboard");
    }
  }, [loading, user, memberships, router]);

  return (
    <div className="flex min-h-screen items-center justify-center">
      <Loader />
    </div>
  );
}