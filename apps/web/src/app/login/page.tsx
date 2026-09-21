"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { api } from "@clearis/shared";
import { AnimatePresence, motion } from "framer-motion";
import {
  AlertCircle,
  ArrowRight,
  Award,
  Building2,
  Eye,
  EyeOff,
  Loader2,
  Lock,
  LogIn,
  Mail,
  Ticket,
} from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { FlintwireCredit } from "@/components/flintwire-credit";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ThemeSwitch } from "@/components/theme-switch";
import { savePortalSession } from "@/lib/portal-session";

const schema = z.object({
  email: z.string().email("Enter a valid email"),
  password: z.string().min(1, "Password is required"),
});
type LoginForm = z.infer<typeof schema>;

const EMAIL_KEY = "clearis.login.email";

/**
 * The login screen is the front door for three different people: a parent with a
 * result code, a staff member with an account, and a school that has not joined
 * yet. One card, one switcher — nobody has to guess where they belong.
 */
type Mode = "result" | "login" | "register";

const TABS: { id: Mode; label: string; icon: typeof Award }[] = [
  { id: "result", label: "Check result", icon: Award },
  { id: "login", label: "Sign in", icon: LogIn },
  { id: "register", label: "Register a school", icon: Building2 },
];

const ease = [0.25, 0.46, 0.45, 0.94] as const;

/** Uppercase, drop anything that isn't part of a code, keep it short. */
function cleanCode(raw: string): string {
  return raw
    .toUpperCase()
    .replace(/[^A-Z0-9-]/g, "")
    .replace(/--+/g, "-")
    .slice(0, 10);
}

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("login");

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

  // --- Result check state ---
  const [code, setCode] = useState("");
  const [resultBusy, setResultBusy] = useState(false);
  const [resultError, setResultError] = useState<string | null>(null);

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
      const me = await api.me();
      // Hard navigation on purpose. A route-only change would keep this tab's
      // client alive, and with it any data cached while somebody else was
      // signed in here; only a fresh document is guaranteed to start clean.
      window.location.replace(
        me.user.is_superadmin && me.memberships.length === 0
          ? "/super-admin"
          : "/dashboard",
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Sign in failed");
    }
  };

  const onCheckResult = async () => {
    setResultError(null);
    if (!code.trim()) {
      setResultError("Enter the result code your school issued.");
      return;
    }
    setResultBusy(true);
    try {
      const session = await api.schoolResultCheck({ pin: code.trim() });
      savePortalSession({
        token: session.token,
        student: session.student,
        school: session.school,
      });
      router.push("/check-result");
    } catch (e) {
      setResultError(
        e instanceof Error && e.message
          ? e.message
          : "We could not find a published result for those details.",
      );
    } finally {
      setResultBusy(false);
    }
  };

  const switchMode = (next: Mode) => {
    setMode(next);
    setError(null);
    setResultError(null);
    setShowForgot(false);
  };

  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-background px-4 py-12">
      {/* Background treatment: soft brand glow + faint grid for depth. */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -left-[20%] -top-[20%] h-[620px] w-[620px] rounded-full bg-primary/[0.07] blur-[130px]" />
        <div className="absolute -bottom-[25%] -right-[15%] h-[520px] w-[520px] rounded-full bg-primary/[0.05] blur-[110px]" />
        <div
          className="absolute inset-0 opacity-[0.35] [mask-image:radial-gradient(ellipse_at_center,black,transparent_72%)]"
          style={{
            backgroundImage:
              "linear-gradient(to right, hsl(var(--border) / 0.5) 1px, transparent 1px), linear-gradient(to bottom, hsl(var(--border) / 0.5) 1px, transparent 1px)",
            backgroundSize: "46px 46px",
          }}
        />
      </div>

      <div className="absolute right-4 top-4 sm:right-6 sm:top-6">
        <ThemeSwitch />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease }}
        className="relative z-10 w-full max-w-[430px]"
      >
        {/* Brand */}
        <div className="mb-7 flex flex-col items-center gap-3">
          <Image
            src="/clearisbg.png"
            alt="Clearis"
            width={1536}
            height={1024}
            priority
            className="h-16 w-auto object-contain"
          />
          <p className="text-[12.5px] font-medium tracking-wide text-muted-foreground/70">
            School management, results and reporting
          </p>
        </div>

        <div className="overflow-hidden rounded-3xl border border-border/60 bg-card/80 shadow-[0_24px_70px_-30px_rgba(15,23,42,0.45)] backdrop-blur-xl">
          {/* Accent hairline — a bit of polish that reads instantly as premium. */}
          <div className="h-[3px] w-full bg-gradient-to-r from-primary/0 via-primary to-primary/0" />

          {/* Mode switcher */}
          <div className="px-6 pt-6">
            <div
              role="tablist"
              aria-label="Choose how to continue"
              className="relative grid grid-cols-3 gap-1 rounded-2xl border border-border/50 bg-muted/40 p-1"
            >
              {TABS.map((tab) => {
                const active = mode === tab.id;
                const Icon = tab.icon;
                return (
                  <button
                    key={tab.id}
                    role="tab"
                    type="button"
                    aria-selected={active}
                    onClick={() => switchMode(tab.id)}
                    className={`relative z-10 flex flex-col items-center gap-1 rounded-xl px-1.5 py-2.5 text-[11px] font-semibold transition-colors duration-200 ${
                      active
                        ? "text-primary"
                        : "text-muted-foreground/70 hover:text-foreground"
                    }`}
                  >
                    {active && (
                      <motion.span
                        layoutId="auth-tab-pill"
                        transition={{ type: "spring", stiffness: 420, damping: 34 }}
                        className="absolute inset-0 -z-10 rounded-xl border border-border/60 bg-card shadow-[0_1px_3px_rgba(15,23,42,0.08)]"
                      />
                    )}
                    <Icon className="h-3.5 w-3.5" />
                    <span className="leading-tight text-center">{tab.label}</span>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="px-6 pb-7 pt-6 sm:px-8">
            <AnimatePresence mode="wait" initial={false}>
              {/* ---------------------------------------------------------- */}
              {/* 1. Check result                                            */}
              {/* ---------------------------------------------------------- */}
              {mode === "result" && (
                <motion.div
                  key="result"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.22, ease }}
                  className="space-y-5"
                >
                  <h1 className="text-[19px] font-bold tracking-tight">
                    Check your result
                  </h1>

                  <form
                    onSubmit={(e) => {
                      e.preventDefault();
                      void onCheckResult();
                    }}
                    className="space-y-4"
                    noValidate
                  >
                    <div className="space-y-2">
                      <Label htmlFor="result-code" className="text-[13px] font-medium">
                        Result code
                      </Label>
                      <div className="group relative">
                        <Ticket className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground/50 transition-colors group-focus-within:text-primary" />
                        <Input
                          id="result-code"
                          value={code}
                          onChange={(e) => {
                            setCode(cleanCode(e.target.value));
                            setResultError(null);
                          }}
                          placeholder="GVS-7K42Q"
                          autoComplete="off"
                          autoFocus
                          spellCheck={false}
                          aria-invalid={Boolean(resultError)}
                          className="h-12 rounded-xl pl-11 font-mono text-[16px] font-semibold uppercase tracking-[0.18em] placeholder:font-sans placeholder:text-[13px] placeholder:font-normal placeholder:tracking-normal"
                        />
                      </div>
                    </div>

                    {resultError && (
                      <motion.div
                        initial={{ opacity: 0, y: -4 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="flex items-start gap-2 rounded-xl border border-destructive/20 bg-destructive/5 px-3.5 py-2.5 text-[12.5px] leading-relaxed text-destructive"
                      >
                        <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                        <span>{resultError}</span>
                      </motion.div>
                    )}

                    <Button
                      type="submit"
                      className="h-11 w-full text-[14px] font-semibold"
                      isLoading={resultBusy}
                    >
                      {resultBusy ? "Checking…" : "View result"}
                      {!resultBusy && <ArrowRight className="ml-1 h-4 w-4" />}
                    </Button>
                  </form>
                </motion.div>
              )}

              {/* ---------------------------------------------------------- */}
              {/* 2. Sign in                                                  */}
              {/* ---------------------------------------------------------- */}
              {mode === "login" && (
                <motion.div
                  key="login"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.22, ease }}
                >
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
                          aria-label={showPassword ? "Hide password" : "Show password"}
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
                                const result =
                                  await api.requestPasswordReset(forgotEmail);
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
                      disabled={isSubmitting}
                      isLoading={isSubmitting}
                    >
                      {isSubmitting ? "Signing in…" : "Sign in"}
                      {!isSubmitting && <ArrowRight className="ml-1 h-4 w-4" />}
                    </Button>
                  </form>
                </motion.div>
              )}

              {/* ---------------------------------------------------------- */}
              {/* 3. Register a school                                        */}
              {/* ---------------------------------------------------------- */}
              {mode === "register" && (
                <motion.div
                  key="register"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.22, ease }}
                  className="space-y-5"
                >
                  <div className="space-y-1">
                    <h1 className="text-[19px] font-bold tracking-tight">
                      Bring your school to Clearis
                    </h1>
                    <p className="text-[12.5px] leading-relaxed text-muted-foreground">
                      Set up your workspace in a few minutes.
                    </p>
                  </div>

                  <Button asChild className="h-11 w-full text-[14px] font-semibold">
                    <Link href="/register">
                      Create a school workspace
                      <ArrowRight className="ml-1 h-4 w-4" />
                    </Link>
                  </Button>

                  <p className="text-center text-[12px] text-muted-foreground">
                    Already have a workspace?{" "}
                    <button
                      type="button"
                      onClick={() => switchMode("login")}
                      className="font-semibold text-primary hover:text-primary/80 transition-colors"
                    >
                      Sign in
                    </button>
                  </p>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

        <div className="mt-6 text-center">
          <p className="text-[11px] tracking-wide text-muted-foreground/60">
            Secure school management for modern institutions
          </p>
        </div>

        <div className="mt-5">
          <FlintwireCredit />
        </div>
      </motion.div>
    </div>
  );
}
