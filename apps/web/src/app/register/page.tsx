"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { api } from "@schoolos/shared";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  ImagePlus,
  Loader2,
  ShieldCheck,
} from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ThemeSwitch } from "@/components/theme-switch";

const schema = z
  .object({
    school_name: z.string().min(2, "School name is required"),
    school_type: z.string().min(2, "School type is required"),
    established_year: z.string().optional(),
    website: z.string().optional(),
    school_email: z
      .string()
      .email("Enter a valid school email")
      .optional()
      .or(z.literal("")),
    phone: z.string().optional(),
    address: z.string().optional(),
    state: z.string().optional(),
    admin_full_name: z.string().min(2, "Your full name is required"),
    admin_email: z.string().email("Enter a valid email"),
    password: z
      .string()
      .min(8, "Password must be at least 8 characters"),
    confirm: z.string(),
    authorized: z
      .boolean()
      .refine(Boolean, "Please confirm you are authorized to manage this school"),
  })
  .refine((data) => data.password === data.confirm, {
    message: "Passwords do not match",
    path: ["confirm"],
  });

type RegisterForm = z.infer<typeof schema>;

const STEPS = ["School profile", "Administrator", "Review"];

export default function RegisterPage() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [logo, setLogo] = useState<File | null>(null);
  const [logoPreview, setLogoPreview] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [logoNotice, setLogoNotice] = useState<string | null>(null);
  const [complete, setComplete] = useState(false);
  const {
    register,
    handleSubmit,
    trigger,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<RegisterForm>({
    resolver: zodResolver(schema),
    defaultValues: { country: "NG", authorized: false } as Partial<RegisterForm>,
  });
  const values = watch();

  useEffect(() => {
    return () => {
      if (logoPreview) URL.revokeObjectURL(logoPreview);
    };
  }, [logoPreview]);

  async function nextStep() {
    const fields: (keyof RegisterForm)[][] = [
      [
        "school_name",
        "school_type",
        "established_year",
        "website",
        "school_email",
        "phone",
        "address",
        "state",
      ],
      ["admin_full_name", "admin_email", "password", "confirm", "authorized"],
    ];
    if (await trigger(fields[step])) setStep((current) => current + 1);
  }

  function pickLogo(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (
      !file.type.match(/^image\/(jpeg|png|webp)$/) ||
      file.size > 5 * 1024 * 1024
    ) {
      setLogoNotice("Choose a JPEG, PNG or WebP image up to 5 MB.");
      return;
    }
    setLogoNotice(null);
    setLogo(file);
    setLogoPreview(URL.createObjectURL(file));
  }

  const onSubmit = async (data: RegisterForm) => {
    setError(null);
    setLogoNotice(null);
    try {
      await api.registerSchool({
        school_name: data.school_name,
        school_type: data.school_type,
        established_year: data.established_year
          ? Number(data.established_year)
          : undefined,
        website: data.website || undefined,
        school_email: data.school_email || undefined,
        phone: data.phone || undefined,
        address: data.address || undefined,
        state: data.state || undefined,
        admin_email: data.admin_email,
        admin_full_name: data.admin_full_name,
        password: data.password,
      });
      if (logo) {
        try {
          const session = await api.me();
          const schoolId = session.memberships[0]?.school_id;
          if (schoolId) await api.uploadSchoolLogo(schoolId, logo);
        } catch {
          setLogoNotice(
            "Your account is ready. You can add the logo later in School Settings.",
          );
        }
      }
      setComplete(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Registration failed");
    }
  };

  // --- Success state ---
  if (complete) {
    return (
      <div className="relative flex min-h-screen flex-col items-center justify-center bg-background px-4 py-12">
        {/* Animated background orbs */}
        <div className="pointer-events-none absolute inset-0 overflow-hidden">
          <motion.div
            animate={{ scale: [1, 1.1, 1], opacity: [0.04, 0.06, 0.04] }}
            transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
            className="absolute -left-[20%] -top-[20%] h-[600px] w-[600px] rounded-full bg-success/[0.06] blur-[120px]"
          />
          <motion.div
            animate={{ scale: [1, 1.15, 1], opacity: [0.03, 0.05, 0.03] }}
            transition={{ duration: 10, repeat: Infinity, ease: "easeInOut", delay: 1 }}
            className="absolute -bottom-[20%] -right-[20%] h-[500px] w-[500px] rounded-full bg-primary/[0.04] blur-[100px]"
          />
          {/* Confetti-like floating dots */}
          {[...Array(6)].map((_, i) => (
            <motion.div
              key={i}
              animate={{ y: [-20, 20, -20], opacity: [0.15, 0.3, 0.15] }}
              transition={{ duration: 4 + i, repeat: Infinity, ease: "easeInOut", delay: i * 0.5 }}
              className="absolute h-2 w-2 rounded-full bg-success/20"
              style={{
                left: `${15 + i * 14}%`,
                top: `${10 + (i % 3) * 25}%`,
              }}
            />
          ))}
        </div>

        <div className="absolute right-4 top-4 sm:right-6 sm:top-6">
          <ThemeSwitch />
        </div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.25, 0.46, 0.45, 0.94] }}
          className="relative z-10 w-full max-w-[520px]"
        >
          {/* Logo */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.2, duration: 0.5 }}
            className="mb-8 flex flex-col items-center gap-3"
          >
            <Image
              src="/clearisbg.png"
              alt="Clearis"
              width={1536}
              height={1024}
              priority
              className="h-20 w-auto object-contain"
            />
          </motion.div>

          {/* Card */}
          <motion.div
            initial={{ opacity: 0, y: 12, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ delay: 0.3, duration: 0.5, ease: [0.25, 0.46, 0.45, 0.94] }}
            className="rounded-2xl border border-border/40 bg-white/80 p-8 shadow-[0_2px_8px_rgba(0,0,0,0.04)] backdrop-blur-sm dark:bg-white/5 sm:p-10"
          >
            {/* Success badge */}
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ delay: 0.5, type: "spring", stiffness: 200, damping: 15 }}
              className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-50 to-green-50 ring-1 ring-emerald-100/80"
            >
              <Check className="h-7 w-7 text-emerald-600" />
            </motion.div>

            {/* Title */}
            <div className="text-center">
              <motion.div
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.6 }}
              >
                <p className="mb-1 text-[12px] font-semibold uppercase tracking-wider text-emerald-600">
                  Registration Complete
                </p>
              </motion.div>
              <motion.h1
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.7 }}
                className="text-[24px] font-bold tracking-tight text-foreground"
              >
                {values.school_name}
              </motion.h1>
              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.8 }}
                className="mt-1 text-[14px] text-muted-foreground"
              >
                Your workspace is ready to go
              </motion.p>
            </div>

            {/* Divider */}
            <motion.div
              initial={{ scaleX: 0 }}
              animate={{ scaleX: 1 }}
              transition={{ delay: 0.9, duration: 0.4 }}
              className="my-7 h-px bg-gradient-to-r from-transparent via-border to-transparent"
            />

            {/* What to do next */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 1.0 }}
            >
              <p className="mb-4 text-center text-[12px] font-semibold uppercase tracking-wider text-muted-foreground/70">
                What to do next
              </p>
              <div className="grid gap-2.5 sm:grid-cols-2">
                {[
                  { icon: "1", text: "Complete school profile", color: "text-blue-600 bg-blue-50" },
                  { icon: "2", text: "Create academic session", color: "text-violet-600 bg-violet-50" },
                  { icon: "3", text: "Add classes and subjects", color: "text-amber-600 bg-amber-50" },
                  { icon: "4", text: "Invite teachers", color: "text-emerald-600 bg-emerald-50" },
                  { icon: "5", text: "Add students", color: "text-rose-600 bg-rose-50" },
                  { icon: "6", text: "Configure grading", color: "text-cyan-600 bg-cyan-50" },
                ].map((item, i) => (
                  <motion.div
                    key={item.text}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 1.1 + i * 0.08 }}
                    className="flex items-center gap-2.5 rounded-xl border border-border/40 bg-white/60 px-3.5 py-2.5 backdrop-blur-sm dark:bg-white/5"
                  >
                    <span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[10px] font-bold ${item.color}`}>
                      {item.icon}
                    </span>
                    <span className="text-[13px] text-muted-foreground">{item.text}</span>
                  </motion.div>
                ))}
              </div>
            </motion.div>

            {logoNotice && (
              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="mt-4 rounded-lg bg-amber-50 px-3 py-2 text-[12px] text-amber-600 dark:bg-amber-500/10"
              >
                {logoNotice}
              </motion.p>
            )}

            {/* CTA */}
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 1.3 }}
              className="mt-8"
            >
              <Button
                className="h-12 w-full text-[14px] font-semibold shadow-sm shadow-primary/10 transition-all hover:shadow-md hover:shadow-primary/15"
                onClick={() => router.replace("/dashboard")}
              >
                Open your workspace
                <ArrowRight className="ml-1.5 h-4 w-4" />
              </Button>
            </motion.div>
          </motion.div>

          {/* Trust bar */}
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 1.5 }}
            className="mt-6 text-center text-[11px] text-muted-foreground/50"
          >
            Secure school data · Role-based access · Automated backups
          </motion.p>
        </motion.div>
      </div>
    );
  }

  // --- Registration form ---
  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center bg-background px-4 py-12">
      {/* Background */}
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
        className="relative z-10 w-full max-w-[580px]"
      >
        {/* Logo */}
        <div className="mb-6 flex flex-col items-center gap-3">
          <Image
            src="/clearisbg.png"
            alt="Clearis"
            width={1536}
            height={1024}
            priority
            className="h-20 w-auto object-contain"
          />
        </div>

        {/* Heading */}
        <div className="mb-6 text-center">
          <h1 className="text-[28px] font-bold tracking-tight text-foreground">
            Create your workspace
          </h1>
          <p className="mt-2 text-[15px] text-muted-foreground">
            Set up your school and manage everything from one clear platform.
          </p>
        </div>

        {/* Step indicator */}
        <div className="mb-8 flex items-center justify-center gap-2">
          {STEPS.map((label, i) => (
            <div key={label} className="flex items-center gap-2">
              <div className="flex items-center gap-2">
                <span
                  className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[11px] font-bold transition-colors duration-200 ${
                    i < step
                      ? "bg-primary text-primary-foreground"
                      : i === step
                        ? "bg-primary text-primary-foreground shadow-sm shadow-primary/25"
                        : "bg-muted text-muted-foreground"
                  }`}
                >
                  {i < step ? <Check className="h-3.5 w-3.5" /> : i + 1}
                </span>
                <span
                  className={`hidden text-[12px] sm:block ${
                    i === step
                      ? "font-semibold text-foreground"
                      : "text-muted-foreground"
                  }`}
                >
                  {label}
                </span>
              </div>
              {i < STEPS.length - 1 && (
                <span
                  className={`mx-1 hidden h-px w-8 sm:block ${
                    i < step ? "bg-primary" : "bg-border"
                  }`}
                />
              )}
            </div>
          ))}
        </div>

        {/* Card */}
        <div className="rounded-2xl border border-border/60 bg-card p-7 shadow-[0_1px_3px_rgba(0,0,0,0.04)] sm:p-8">
          <AnimatePresence mode="wait">
            <motion.div
              key={step}
              initial={{ opacity: 0, x: 12 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -12 }}
              transition={{ duration: 0.2 }}
            >
              <h2 className="text-[20px] font-bold tracking-tight">
                {STEPS[step]}
              </h2>
              <p className="mt-1 text-[13px] text-muted-foreground">
                {step === 0
                  ? "Tell us about your institution."
                  : step === 1
                    ? "Create the trusted owner account."
                    : "Review the details before creating your workspace."}
              </p>

              <form
                onSubmit={handleSubmit(onSubmit)}
                className="mt-6 space-y-4"
              >
                {step === 0 && (
                  <>
                    <div className="grid gap-4 sm:grid-cols-2">
                      <Field label="School name" required error={errors.school_name?.message}>
                        <Input
                          placeholder="Brightfield Academy"
                          {...register("school_name")}
                          className="h-11 text-[14px]"
                        />
                      </Field>
                      <Field label="School type" required error={errors.school_type?.message}>
                        <Input
                          placeholder="Primary or Secondary"
                          {...register("school_type")}
                          className="h-11 text-[14px]"
                        />
                      </Field>
                    </div>
                    <div className="grid gap-4 sm:grid-cols-2">
                      <Field label="Established year">
                        <Input
                          type="number"
                          placeholder="2008"
                          {...register("established_year")}
                          className="h-11 text-[14px]"
                        />
                      </Field>
                      <Field label="School website">
                        <Input
                          placeholder="https://school.edu"
                          {...register("website")}
                          className="h-11 text-[14px]"
                        />
                      </Field>
                    </div>
                    <div className="grid gap-4 sm:grid-cols-2">
                      <Field label="School email" error={errors.school_email?.message}>
                        <Input
                          type="email"
                          placeholder="office@school.edu"
                          {...register("school_email")}
                          className="h-11 text-[14px]"
                        />
                      </Field>
                      <Field label="Phone">
                        <Input
                          placeholder="+234 800 000 0000"
                          {...register("phone")}
                          className="h-11 text-[14px]"
                        />
                      </Field>
                    </div>
                    <Field label="Address">
                      <Input
                        placeholder="Street address"
                        {...register("address")}
                        className="h-11 text-[14px]"
                      />
                    </Field>
                    <Field label="State / region">
                      <Input
                        placeholder="Lagos"
                        {...register("state")}
                        className="h-11 text-[14px]"
                      />
                    </Field>

                    {/* Logo upload */}
                    <div className="rounded-xl border border-dashed border-border/60 p-4">
                      <div className="flex items-center gap-3">
                        <ImagePlus className="h-5 w-5 text-muted-foreground" />
                        <div className="min-w-0 flex-1">
                          <p className="text-[13px] font-semibold">
                            School logo{" "}
                            <span className="font-normal text-muted-foreground">
                              (optional)
                            </span>
                          </p>
                          <p className="text-[12px] text-muted-foreground">
                            Your logo replaces the Clearis logo across the
                            school workspace.
                          </p>
                        </div>
                        <label className="cursor-pointer rounded-lg bg-primary/10 px-3 py-2 text-[12px] font-semibold text-primary transition-colors hover:bg-primary/15">
                          Choose
                          <input
                            type="file"
                            accept="image/jpeg,image/png,image/webp"
                            onChange={pickLogo}
                            className="sr-only"
                          />
                        </label>
                      </div>
                      {logoPreview && (
                        <img
                          src={logoPreview}
                          alt="School logo preview"
                          className="mt-3 h-14 w-14 rounded-lg border bg-white object-contain"
                        />
                      )}
                      {logoNotice && (
                        <p className="mt-2 text-[12px] text-warning">
                          {logoNotice}
                        </p>
                      )}
                    </div>
                  </>
                )}

                {step === 1 && (
                  <>
                    <Field
                      label="Your full name"
                      required
                      error={errors.admin_full_name?.message}
                    >
                      <Input
                        placeholder="Jane Doe"
                        {...register("admin_full_name")}
                        className="h-11 text-[14px]"
                      />
                    </Field>
                    <Field
                      label="Work email"
                      required
                      error={errors.admin_email?.message}
                    >
                      <Input
                        type="email"
                        placeholder="you@school.edu"
                        {...register("admin_email")}
                        className="h-11 text-[14px]"
                      />
                    </Field>
                    <div className="grid gap-4 sm:grid-cols-2">
                      <Field
                        label="Password"
                        required
                        error={errors.password?.message}
                      >
                        <Input
                          type="password"
                          placeholder="At least 8 characters"
                          {...register("password")}
                          className="h-11 text-[14px]"
                        />
                      </Field>
                      <Field
                        label="Confirm password"
                        required
                        error={errors.confirm?.message}
                      >
                        <Input
                          type="password"
                          placeholder="Confirm password"
                          {...register("confirm")}
                          className="h-11 text-[14px]"
                        />
                      </Field>
                    </div>
                    <label className="flex gap-3 rounded-xl border border-border/60 bg-muted/30 p-4 text-[13px]">
                      <input
                        type="checkbox"
                        className="mt-0.5 h-4 w-4 accent-primary"
                        {...register("authorized")}
                      />
                      <span className="text-muted-foreground">
                        I confirm that I am authorized to create and manage
                        this school workspace on behalf of the institution.
                      </span>
                    </label>
                    {errors.authorized && (
                      <p className="text-[12px] text-destructive">
                        {errors.authorized.message}
                      </p>
                    )}
                  </>
                )}

                {step === 2 && (
                  <div className="space-y-4">
                    <div className="rounded-xl border border-border/60 bg-muted/30 p-5">
                      <div className="flex items-center gap-4">
                        {logoPreview ? (
                          <img
                            src={logoPreview}
                            alt="School logo"
                            className="h-14 w-14 rounded-xl border bg-white object-contain"
                          />
                        ) : (
                          <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-primary/10 text-lg font-bold text-primary">
                            {(values.school_name ?? "S").charAt(0)}
                          </div>
                        )}
                        <div>
                          <p className="text-[16px] font-bold">
                            {values.school_name || "Your school"}
                          </p>
                          <p className="text-[13px] capitalize text-muted-foreground">
                            {values.school_type || "School"} ·{" "}
                            {values.state || "Nigeria"}
                          </p>
                        </div>
                      </div>
                    </div>
                    <div className="grid gap-2 text-[13px] sm:grid-cols-2">
                      {[
                        values.website,
                        values.school_email,
                        values.phone,
                        values.address,
                      ]
                        .filter(Boolean)
                        .map((item) => (
                          <p
                            key={item}
                            className="rounded-lg border border-border/60 px-3 py-2 text-muted-foreground"
                          >
                            {item}
                          </p>
                        ))}
                    </div>
                    <p className="text-[12px] text-muted-foreground">
                      By creating this workspace, you agree to
                      Clearis&apos;s terms and privacy practices.
                    </p>
                  </div>
                )}

                {/* Error */}
                {error && (
                  <motion.div
                    initial={{ opacity: 0, y: -4 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="rounded-xl border border-destructive/20 bg-destructive/5 px-3.5 py-2.5 text-[13px] text-destructive"
                  >
                    {error}
                  </motion.div>
                )}

                {/* Actions */}
                <div className="flex gap-3 pt-2">
                  {step > 0 && (
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => setStep((current) => current - 1)}
                      className="h-11 px-5"
                    >
                      <ArrowLeft className="mr-1.5 h-4 w-4" />
                      Back
                    </Button>
                  )}
                  <Button
                    type={step < 2 ? "button" : "submit"}
                    className="ml-auto h-11 px-6 text-[14px] font-semibold"
                    onClick={step < 2 ? nextStep : undefined}
                    disabled={isSubmitting}
                    isLoading={isSubmitting}
                  >
                    {step < 2 ? (
                      <>
                        Continue
                        <ArrowRight className="ml-1.5 h-4 w-4" />
                      </>
                    ) : isSubmitting ? (
                      "Creating workspace…"
                    ) : (
                      <>
                        Create workspace
                        <ArrowRight className="ml-1.5 h-4 w-4" />
                      </>
                    )}
                  </Button>
                </div>
              </form>
            </motion.div>
          </AnimatePresence>
        </div>

        {/* Footer */}
        <div className="mt-6 text-center">
          <p className="text-[13px] text-muted-foreground">
            Already have an account?{" "}
            <Link
              href="/login"
              className="font-semibold text-primary hover:text-primary/80 transition-colors"
            >
              Sign in
            </Link>
          </p>
        </div>

        <div className="mt-6 text-center">
          <p className="text-[11px] tracking-wide text-muted-foreground/60">
            Secure school data · Role-based access · Automated backups
          </p>
        </div>
      </motion.div>
    </div>
  );
}

function Field({
  label,
  required,
  error,
  children,
}: {
  label: string;
  required?: boolean;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <Label className="text-[13px] font-medium">
        {label}
        {required && <span className="ml-0.5 text-destructive">*</span>}
      </Label>
      {children}
      {error && <p className="text-[12px] text-destructive">{error}</p>}
    </div>
  );
}
