"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { api } from "@schoolos/shared";
import { AlertCircle, ArrowRight, Lock } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

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
      setError("This reset link is missing a token. Request a new one from the sign-in page.");
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
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-b from-background to-muted/40 p-6">
      <div className="w-full max-w-[26rem] rounded-2xl border bg-card p-8 shadow-card">
        <Image
          src="/clearis.png"
          alt="Clearis"
          width={1536}
          height={1024}
          priority
          className="mx-auto h-16 w-auto rounded-lg object-contain"
        />
        <h2 className="mt-6 text-[22px] font-bold tracking-tight">Choose a new password</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          This link can be used once and expires after an hour.
        </p>

        <form onSubmit={handleSubmit(onSubmit)} className="mt-7 space-y-5" noValidate>
          <div className="space-y-2">
            <Label htmlFor="new_password">New password</Label>
            <div className="relative">
              <Lock className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                id="new_password"
                type="password"
                autoComplete="new-password"
                placeholder="At least 8 characters"
                className="h-11 pl-10"
                {...register("new_password")}
              />
            </div>
            {errors.new_password && (
              <p className="text-xs text-destructive">{errors.new_password.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="confirm">Confirm password</Label>
            <Input
              id="confirm"
              type="password"
              autoComplete="new-password"
              className="h-11"
              {...register("confirm")}
            />
            {errors.confirm && <p className="text-xs text-destructive">{errors.confirm.message}</p>}
          </div>

          {error && (
            <div className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              <AlertCircle className="h-4 w-4 shrink-0" />
              {error}
            </div>
          )}

          <Button type="submit" className="h-11 w-full text-base" disabled={isSubmitting || !token}>
            {isSubmitting ? "Updating…" : "Update password"}
            <ArrowRight className="ml-1 h-4 w-4" />
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-muted-foreground">
          <Link href="/login" className="font-semibold text-primary hover:underline">
            Back to sign in
          </Link>
        </p>
      </div>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center text-sm text-muted-foreground">
          Loading…
        </div>
      }
    >
      <ResetPasswordForm />
    </Suspense>
  );
}
