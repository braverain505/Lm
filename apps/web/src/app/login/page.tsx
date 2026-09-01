"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { api } from "@schoolos/shared";
import { motion } from "framer-motion";
import {
  AlertCircle,
  ArrowRight,
  Eye,
  EyeOff,
  Loader2,
  Lock,
  Mail,
} from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ThemeSwitch } from "@/components/theme-switch";
import { useAuth } from "@/providers/auth-provider";

const schema = z.object({
  email: z.string().email("Enter a valid email"),
  password: z.string().min(1, "Password is required"),
});
type LoginForm = z.infer<typeof schema>;

const EMAIL_KEY = "schoolos.login.email";

export default function LoginPage() {
  const router = useRouter();
  const { refreshMe } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const [showForgot, setShowForgot] = useState(false);
  const [forgotEmail, setForgotEmail] = useState("");
  const [forgotBusy, setForgotBusy] = useState(false);
  const [forgotMessage, setForgotMessage] = useState<string | null>(null);
  const [forgotToken, setForgotToken] = useState<string | null>(null);
  const [savedEmail] = useState<string>(() => {
    if (typeof window === "undefined") return "";
    try {
      return localStorage.getItem(EMAIL_KEY) ?? "";
    } catch {
      return "";
    }
  });

  const {
    register,
    handleSubmit,
    getValues,
    formState: { errors, isSubmitting },
  } = useForm<LoginForm>({
    resolver: zodResolver(schema),
    defaultValues: { email: savedEmail },
  });

  const onSubmit = async (values: LoginForm) => {
    setError(null);
    try {
      try {
        localStorage.setItem(EMAIL_KEY, values.email);
      } catch {
        /* ignore */
      }
      await api.login(values);
      await refreshMe();
      const me = await api.me();
      router.replace(
        me.user.is_superadmin && me.memberships.length === 0
          ? "/super-admin"
          : "/dashboard",
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Sign in failed");
    }
  };

  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center bg-background px-4 py-12">
      {/* Subtle background treatment */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -left-[20%] -top-[20%] h-[600px] w-[600px] rounded-full bg-primary/[0.04] blur-[120px]" />
        <div className="absolute -bottom-[20%] -right-[20%] h-[500px] w-[500px] rounded-full bg-primary/[0.03] blur-[100px]" />
      </div>

      {/* Theme switcher */}
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
            src="/clearis.png"
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
            Welcome back
          </h1>
          <p className="mt-2 text-[15px] text-muted-foreground">
            Sign in to your Clearis workspace
          </p>
        </div>

        {/* Card */}
        <div className="rounded-2xl border border-border/60 bg-card p-8 shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5" noValidate>
            <div className="space-y-2">
              <Label htmlFor="email" className="text-[13px] font-medium">
                Email address
              </Label>
              <div className="relative">
                <Mail className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground/60" />
                <Input
                  id="email"
                  type="email"
                  autoComplete="email"
                  autoFocus
                  placeholder="you@school.edu"
                  className="h-11 pl-10 text-[14px]"
                  {...register("email")}
                />
              </div>
              {errors.email && (
                <p className="text-[12px] text-destructive">
                  {errors.email.message}
                </p>
              )}
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="password" className="text-[13px] font-medium">
                  Password
                </Label>
                <button
                  type="button"
                  onClick={() => {
                    setShowForgot(true);
                    setForgotMessage(null);
                    setForgotToken(null);
                    setForgotEmail(getValues("email") || savedEmail);
                  }}
                  className="text-[12px] font-medium text-primary hover:text-primary/80 transition-colors"
                >
                  Forgot password?
                </button>
              </div>
              <div className="relative">
                <Lock className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground/60" />
                <Input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  placeholder="••••••••"
                  className="h-11 pl-10 pr-11 text-[14px]"
                  {...register("password")}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label={
                    showPassword ? "Hide password" : "Show password"
                  }
                  className="absolute right-3 top-1/2 -translate-y-1/2 rounded-md p-0.5 text-muted-foreground/60 hover:text-foreground transition-colors"
                >
                  {showPassword ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </button>
              </div>
              {errors.password && (
                <p className="text-[12px] text-destructive">
                  {errors.password.message}
                </p>
              )}
            </div>

            {/* Forgot password inline */}
            {showForgot && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                transition={{ duration: 0.2 }}
                className="space-y-3 rounded-xl border border-border/60 bg-muted/30 p-4"
              >
                <p className="text-[12px] leading-relaxed text-muted-foreground">
                  Enter your email and we&apos;ll send a reset link.
                </p>
                <div className="flex gap-2">
                  <Input
                    type="email"
                    autoComplete="email"
                    placeholder="you@school.edu"
                    value={forgotEmail}
                    onChange={(e) => setForgotEmail(e.target.value)}
                    className="h-9 text-[13px]"
                  />
                  <Button
                    type="button"
                    size="sm"
                    className="h-9 shrink-0"
                    disabled={forgotBusy || !forgotEmail}
                    onClick={async () => {
                      setForgotBusy(true);
                      setForgotMessage(null);
                      setForgotToken(null);
                      try {
                        const result = await api.requestPasswordReset(
                          forgotEmail,
                        );
                        setForgotMessage(result.message);
                        setForgotToken(result.reset_token);
                      } catch (e) {
                        setForgotMessage(
                          e instanceof Error
                            ? e.message
                            : "Could not send reset",
                        );
                      } finally {
                        setForgotBusy(false);
                      }
                    }}
                  >
                    {forgotBusy ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      "Send"
                    )}
                  </Button>
                </div>
                {forgotMessage && (
                  <p className="text-[12px] leading-relaxed text-muted-foreground">
                    {forgotMessage}
                  </p>
                )}
                {forgotToken && (
                  <p className="text-[12px]">
                    <Link
                      href={`/reset-password?token=${encodeURIComponent(forgotToken)}`}
                      className="font-medium text-primary hover:underline"
                    >
                      Continue to choose a new password
                    </Link>
                    <span className="text-muted-foreground">
                      {" "}
                      (shown in development only)
                    </span>
                  </p>
                )}
              </motion.div>
            )}

            {/* Error */}
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

            {/* Submit */}
            <Button
              type="submit"
              className="h-11 w-full text-[14px] font-semibold"
              disabled={isSubmitting}
              isLoading={isSubmitting}
            >
              {isSubmitting ? "Signing in…" : "Sign in"}
              {!isSubmitting && <ArrowRight className="ml-1 h-4 w-4" />}
            </Button>
          </form>
        </div>

        {/* Footer links */}
        <div className="mt-6 text-center">
          <p className="text-[13px] text-muted-foreground">
            Don&apos;t have an account?{" "}
            <Link
              href="/register"
              className="font-semibold text-primary hover:text-primary/80 transition-colors"
            >
              Create a workspace
            </Link>
          </p>
        </div>

        {/* Trust indicator */}
        <div className="mt-8 text-center">
          <p className="text-[11px] tracking-wide text-muted-foreground/60">
            Secure school management for modern institutions
          </p>
        </div>
      </motion.div>
    </div>
  );
}
