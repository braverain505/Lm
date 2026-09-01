"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { api } from "@schoolos/shared";
import { motion } from "framer-motion";
import { AlertCircle, ArrowRight, Loader2, Lock } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ThemeSwitch } from "@/components/theme-switch";

const schema = z
  .object({
    new_password: z.string().min(8, "Password must be at least 8 characters"),
    confirm: z.string(),
  })
  .refine((d) => d.new_password === d.confirm, {
    message: "Passwords do not match",
    path: ["confirm"],
  });

type ResetForm = z.infer<typeof schema>;

function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [error, setError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ResetForm>({ resolver: zodResolver(schema) });

  const onSubmit = async (values: ResetForm) => {
    setError(null);
    if (!token) {
      setError(
        "This reset link is missing a token. Request a new one from the sign-in page.",
      );
      return;
    }
    try {
      await api.confirmPasswordReset(token, values.new_password);
      router.replace("/login");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not update password");
    }
  };

  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center bg-background px-4 py-12">
      {/* Subtle background */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -left-[20%] -top-[20%] h-[600px] w-[600px] rounded-full bg-primary/[0.04] blur-[120px]" />
        <div className="absolute -bottom-[20%] -right-[20%] h-[500px] w-[500px] rounded-full bg-primary/[0.03] blur-[100px]" />
      </div>

      <div className="absolute right-4 top-4 sm:right-6 sm:top-6">
        <ThemeSwitch />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.25, 0.46, 0.45, 0.94] }}
        className="relative z-10 w-full max-w-[420px]"
      >
        {/* Logo */}
        <div className="mb-8 flex flex-col items-center gap-3">
          <Image
            src="/clearisbg.png"
            alt="Clearis"
            width={1536}
            height={1024}
            priority
            className="h-12 w-auto object-contain"
          />
        </div>

        {/* Heading */}
        <div className="mb-8 text-center">
          <h1 className="text-[28px] font-bold tracking-tight text-foreground">
            Choose a new password
          </h1>
          <p className="mt-2 text-[15px] text-muted-foreground">
            This link can be used once and expires after an hour.
          </p>
        </div>

        {/* Card */}
        <div className="rounded-2xl border border-border/60 bg-card p-8 shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
          <form
            onSubmit={handleSubmit(onSubmit)}
            className="space-y-5"
            noValidate
          >
            <div className="space-y-2">
              <Label htmlFor="new_password" className="text-[13px] font-medium">
                New password
              </Label>
              <div className="relative">
                <Lock className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground/60" />
                <Input
                  id="new_password"
                  type="password"
                  autoComplete="new-password"
                  placeholder="At least 8 characters"
                  className="h-11 pl-10 text-[14px]"
                  {...register("new_password")}
                />
              </div>
              {errors.new_password && (
                <p className="text-[12px] text-destructive">
                  {errors.new_password.message}
                </p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="confirm" className="text-[13px] font-medium">
                Confirm password
              </Label>
              <Input
                id="confirm"
                type="password"
                autoComplete="new-password"
                placeholder="Confirm your new password"
                className="h-11 text-[14px]"
                {...register("confirm")}
              />
              {errors.confirm && (
                <p className="text-[12px] text-destructive">
                  {errors.confirm.message}
                </p>
              )}
            </div>

            {error && (
              <motion.div
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex items-center gap-2 rounded-xl border border-destructive/20 bg-destructive/5 px-3.5 py-2.5 text-[13px] text-destructive"
              >
                <AlertCircle className="h-4 w-4 shrink-0" />
                {error}
              </motion.div>
            )}

            <Button
              type="submit"
              className="h-11 w-full text-[14px] font-semibold"
              disabled={isSubmitting || !token}
              isLoading={isSubmitting}
            >
              {isSubmitting ? "Updating…" : "Update password"}
              {!isSubmitting && <ArrowRight className="ml-1 h-4 w-4" />}
            </Button>
          </form>
        </div>

        <div className="mt-6 text-center">
          <p className="text-[13px] text-muted-foreground">
            <Link
              href="/login"
              className="font-semibold text-primary hover:text-primary/80 transition-colors"
            >
              Back to sign in
            </Link>
          </p>
        </div>
      </motion.div>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-background text-[13px] text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin" />
        </div>
      }
    >
      <ResetPasswordForm />
    </Suspense>
  );
}
