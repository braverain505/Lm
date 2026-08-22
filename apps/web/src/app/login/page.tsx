"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { api } from "@schoolos/shared";
import { motion } from "framer-motion";
import {
  AlertCircle,
  ArrowRight,
  Eye,
  EyeOff,
  GraduationCap,
  Lock,
  Mail,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { useAuth } from "@/providers/auth-provider";

const schema = z.object({
  email: z.string().email("Enter a valid email"),
  password: z.string().min(1, "Password is required"),
});
type LoginForm = z.infer<typeof schema>;

const EMAIL_KEY = "schoolos.login.email";

const FEATURES = [
  { icon: GraduationCap, title: "One system for your whole school", text: "Students, staff, results, billing, attendance and timetable — together." },
  { icon: ShieldCheck, title: "Secure multi-tenant platform", text: "Every school's data is isolated and permission-protected by design." },
  { icon: Sparkles, title: "AI-powered school copilot", text: "Ask anything about your records and get grounded, real answers." },
];

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
  const [remember, setRemember] = useState(true);
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
  } = useForm<LoginForm>({ resolver: zodResolver(schema), defaultValues: { email: savedEmail } });

  const onSubmit = async (values: LoginForm) => {
    setError(null);
    try {
      if (remember) {
        try {
          localStorage.setItem(EMAIL_KEY, values.email);
        } catch {
          /* ignore */
        }
      } else {
        try {
          localStorage.removeItem(EMAIL_KEY);
        } catch {
          /* ignore */
        }
      }
      await api.login(values);
      await refreshMe();
      const me = await api.me();
      router.replace(me.user.is_superadmin && me.memberships.length === 0 ? "/super-admin" : "/dashboard");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Sign in failed");
    }
  };

  return (
    <div className="flex min-h-screen bg-background">
      {/* Left: brand panel (matches in-app dark sidebar) */}
      <div className="relative hidden w-[46%] flex-col overflow-hidden bg-gradient-to-br from-indigo-950 via-[#3b2b8f] to-[#7c3aed] text-white lg:flex">
        {/* Colorful glow gradients */}
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute -left-32 -top-32 h-96 w-96 rounded-full bg-fuchsia-500/25 blur-[120px]" />
          <div className="absolute -bottom-40 -right-24 h-[28rem] w-[28rem] rounded-full bg-sky-400/20 blur-[140px]" />
          <div className="absolute right-10 top-1/3 h-64 w-64 rounded-full bg-primary/30 blur-[100px]" />
        </div>
        {/* Soft color wash */}
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top_left,rgba(255,255,255,0.08),transparent_55%),radial-gradient(ellipse_at_bottom_right,rgba(99,102,241,0.35),transparent_60%)]" />

        <div className="relative flex h-full flex-col justify-between p-12">
          {/* Brand */}
          <div className="flex items-center gap-3">
            <Image
              src="/logo_lumo.png"
              alt="Lumo"
              width={1536}
              height={1024}
              priority
              className="h-16 w-auto shrink-0 rounded-lg object-contain"
            />
          </div>

          {/* Messaging */}
          <div>
            <Badge variant="muted" className="border-white/15 bg-white/10 px-3 py-1 text-white/70">
              The operating system for modern schools
            </Badge>

            <motion.h1
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6 }}
              className="mt-6 max-w-md text-4xl font-bold leading-tight text-white"
            >
              Run your school the modern way.
            </motion.h1>
            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.1 }}
              className="mt-4 max-w-md text-[15px] leading-relaxed text-white/85"
            >
              The complete school management platform — from admissions and academics to results and finance, all in one secure workspace.
            </motion.p>

            <div className="mt-12 space-y-6">
              {FEATURES.map(({ icon: Icon, title, text }, i) => (
                <motion.div
                  key={title}
                  initial={{ opacity: 0, x: -16 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.5, delay: 0.2 + i * 0.1 }}
                  className="flex items-start gap-4"
                >
                  <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-white/15 bg-white/10">
                    <Icon className="h-4 w-4 text-white" />
                  </span>
                  <div>
                    <p className="text-sm font-semibold text-white">{title}</p>
                    <p className="mt-0.5 text-sm leading-relaxed text-white/70">{text}</p>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>

          {/* Footer */}
          <p className="text-sm text-white/60">
            © {new Date().getFullYear()} Lumo. Built for schools that mean business.
          </p>
        </div>
      </div>

      {/* Right: form */}
      <div className="flex w-full items-center justify-center bg-gradient-to-b from-background to-muted/40 p-6 lg:w-[54%]">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="w-full max-w-[26rem]"
        >
          {/* Mobile logo */}
          <div className="mb-8 flex items-center justify-center gap-2 lg:hidden">
            <Image
              src="/logo_lumo.png"
              alt="Lumo"
              width={1536}
              height={1024}
              priority
              className="h-12 w-auto rounded-lg object-contain"
            />
          </div>

          <div className="rounded-2xl border bg-card p-8 shadow-card">
            <h2 className="text-[22px] font-bold tracking-tight">Welcome back</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Sign in to your school workspace
            </p>

            <form onSubmit={handleSubmit(onSubmit)} className="mt-7 space-y-5" noValidate>
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <div className="relative">
                  <Mail className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground transition-colors peer-focus:text-primary" />
                  <Input
                    id="email"
                    type="email"
                    autoComplete="email"
                    autoFocus
                    placeholder="you@school.edu"
                    className="peer h-11 pl-10"
                    {...register("email")}
                  />
                </div>
                {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}
              </div>

              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <div className="relative">
                  <Lock className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    autoComplete="current-password"
                    placeholder="••••••••"
                    className="h-11 pl-10 pr-11"
                    {...register("password")}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                    className="focus-ring absolute right-3 top-1/2 -translate-y-1/2 rounded-md p-0.5 text-muted-foreground hover:text-foreground"
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                {errors.password && <p className="text-xs text-destructive">{errors.password.message}</p>}
              </div>

              <div className="flex items-center justify-between text-sm">
                <label className="flex cursor-pointer items-center gap-2 text-muted-foreground">
                  <input
                    type="checkbox"
                    checked={remember}
                    onChange={(e) => setRemember(e.target.checked)}
                    className="h-4 w-4 rounded border-input accent-primary"
                  />
                  Remember me
                </label>
                <button
                  type="button"
                  onClick={() => {
                    setShowForgot(true);
                    setForgotMessage(null);
                    setForgotToken(null);
                    setForgotEmail(getValues("email") || savedEmail);
                  }}
                  className="focus-ring rounded font-medium text-primary hover:underline"
                >
                  Forgot password?
                </button>
              </div>

              {showForgot && (
                <div className="space-y-3 rounded-lg border bg-muted/40 px-3 py-3">
                  <p className="text-xs leading-relaxed text-muted-foreground">
                    Enter the email for your account. If it exists, we will send a reset link.
                  </p>
                  <div className="flex gap-2">
                    <Input
                      type="email"
                      autoComplete="email"
                      placeholder="you@school.edu"
                      value={forgotEmail}
                      onChange={(e) => setForgotEmail(e.target.value)}
                      className="h-9"
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
                          const result = await api.requestPasswordReset(forgotEmail);
                          setForgotMessage(result.message);
                          setForgotToken(result.reset_token);
                        } catch (e) {
                          setForgotMessage(e instanceof Error ? e.message : "Could not send reset");
                        } finally {
                          setForgotBusy(false);
                        }
                      }}
                    >
                      {forgotBusy ? "Sending…" : "Send"}
                    </Button>
                  </div>
                  {forgotMessage && (
                    <p className="text-xs leading-relaxed text-muted-foreground">{forgotMessage}</p>
                  )}
                  {forgotToken && (
                    <p className="text-xs">
                      <Link
                        href={`/reset-password?token=${encodeURIComponent(forgotToken)}`}
                        className="font-medium text-primary hover:underline"
                      >
                        Continue to choose a new password
                      </Link>
                      <span className="text-muted-foreground"> (shown in development only)</span>
                    </p>
                  )}
                </div>
              )}

              {error && (
                <div className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  <AlertCircle className="h-4 w-4 shrink-0" />
                  {error}
                </div>
              )}

              <Button type="submit" className="h-11 w-full text-base" disabled={isSubmitting}>
                {isSubmitting ? "Signing in…" : "Sign in"}
                <ArrowRight className="ml-1 h-4 w-4" />
              </Button>
            </form>

            <div className="my-6 flex items-center gap-3">
              <Separator className="flex-1" />
              <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">New to Lumo?</span>
              <Separator className="flex-1" />
            </div>

            <div className="space-y-1.5 text-center text-sm text-muted-foreground">
              <p>
                <Link href="/register" className="font-semibold text-primary hover:underline">
                  Register your school
                </Link>{" "}
                — set up in minutes.
              </p>
            </div>
          </div>

          <div className="mt-5 flex items-center justify-center gap-1.5 text-xs text-muted-foreground">
            <ShieldCheck className="h-3.5 w-3.5" />
            Your workspace is secured and tenant-isolated.
          </div>
        </motion.div>
      </div>
    </div>
  );
}
