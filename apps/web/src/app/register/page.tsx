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
        <div className="pointer-events-none absolute inset-0 overflow-hidden">
          <div className="absolute -left-[20%] -top-[20%] h-[600px] w-[600px] rounded-full bg-primary/[0.04] blur-[120px]" />
          <div className="absolute -bottom-[20%] -right-[20%] h-[500px] w-[500px] rounded-full bg-primary/[0.03] blur-[100px]" />
        </div>
        <div className="absolute right-4 top-4 sm:right-6 sm:top-6">
          <ThemeSwitch />
        </div>
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="relative z-10 w-full max-w-[520px]"
        >
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
          <div className="rounded-2xl border border-border/60 bg-card p-8 shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
            <div className="flex items-center gap-3">
              <span className="flex h-11 w-11 items-center justify-center rounded-full bg-success/10 text-success">
                <Check className="h-5 w-5" />
              </span>
              <div>
                <p className="text-[13px] font-semibold text-success">
                  Registration complete
                </p>
                <h1 className="text-[22px] font-bold tracking-tight">
                  {values.school_name} is ready
                </h1>
              </div>
            </div>
            <p className="mt-4 text-[14px] leading-relaxed text-muted-foreground">
              We created your secure school workspace. Your administrator
              account is ready, and school verification can be completed from
              your workspace.
            </p>
            <div className="mt-6 grid gap-2.5 sm:grid-cols-2">
              {[
                "Complete school profile",
                "Create academic session",
                "Add classes and subjects",
                "Invite teachers",
                "Add students",
                "Configure grading",
              ].map((item) => (
                <div
                  key={item}
                  className="flex items-center gap-2.5 rounded-xl border border-border/60 px-3.5 py-2.5 text-[13px]"
                >
                  <Check className="h-4 w-4 shrink-0 text-primary" />
                  {item}
                </div>
              ))}
            </div>
            {logoNotice && (
              <p className="mt-4 text-[13px] text-warning">{logoNotice}</p>
            )}
            <Button
              className="mt-7 h-11 w-full text-[14px] font-semibold"
              onClick={() => router.replace("/dashboard")}
            >
              Open your workspace
              <ArrowRight className="ml-1.5 h-4 w-4" />
            </Button>
          </div>
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
            className="h-12 w-auto object-contain"
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
