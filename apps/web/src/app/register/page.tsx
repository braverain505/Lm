"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { api } from "@schoolos/shared";
import { motion } from "framer-motion";
import { ArrowLeft, ArrowRight, Check, ImagePlus, ShieldCheck } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const schema = z.object({
  school_name: z.string().min(2, "School name is required"),
  school_type: z.string().min(2, "School type is required"),
  established_year: z.string().optional(),
  website: z.string().optional(),
  school_email: z.string().email("Enter a valid school email").optional().or(z.literal("")),
  phone: z.string().optional(),
  address: z.string().optional(),
  state: z.string().optional(),
  admin_full_name: z.string().min(2, "Your full name is required"),
  admin_email: z.string().email("Enter a valid email"),
  password: z.string().min(8, "Password must be at least 8 characters"),
  confirm: z.string(),
  authorized: z.boolean().refine(Boolean, "Please confirm you are authorized to manage this school"),
}).refine((data) => data.password === data.confirm, { message: "Passwords do not match", path: ["confirm"] });

type RegisterForm = z.infer<typeof schema>;

const steps = ["School profile", "Administrator", "Preview & confirm"];

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

  useEffect(() => () => { if (logoPreview) URL.revokeObjectURL(logoPreview); }, [logoPreview]);

  async function nextStep() {
    const fields: (keyof RegisterForm)[][] = [
      ["school_name", "school_type", "established_year", "website", "school_email", "phone", "address", "state"],
      ["admin_full_name", "admin_email", "password", "confirm", "authorized"],
    ];
    if (await trigger(fields[step])) setStep((current) => current + 1);
  }

  function pickLogo(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (!file.type.match(/^image\/(jpeg|png|webp)$/) || file.size > 5 * 1024 * 1024) {
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
        established_year: data.established_year ? Number(data.established_year) : undefined,
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
          setLogoNotice("Your account is ready. You can add the logo later in School Settings.");
        }
      }
      setComplete(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Registration failed");
    }
  };

  if (complete) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-primary/[0.08] via-background to-cyan-400/[0.08] p-6">
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="w-full max-w-2xl rounded-2xl border bg-card p-8 shadow-xl sm:p-10">
          <div className="flex items-center gap-3"><span className="flex h-11 w-11 items-center justify-center rounded-full bg-success/10 text-success"><Check /></span><div><p className="text-sm font-semibold text-success">Registration complete</p><h1 className="text-2xl font-bold">{values.school_name} is ready</h1></div></div>
          <p className="mt-4 text-sm leading-relaxed text-muted-foreground">We created your secure school workspace. Your administrator account is ready, and school verification can be completed from your workspace.</p>
          <div className="mt-7 grid gap-3 sm:grid-cols-2">
            {[
              "Complete school profile",
              "Create academic session",
              "Add classes and subjects",
              "Invite teachers",
              "Add students",
              "Configure grading",
            ].map((item) => <div key={item} className="flex items-center gap-2 rounded-lg border px-3 py-2.5 text-sm"><Check className="h-4 w-4 text-primary" />{item}</div>)}
          </div>
          {logoNotice && <p className="mt-4 text-sm text-warning">{logoNotice}</p>}
          <Button className="mt-8 w-full" onClick={() => router.replace("/dashboard")}>Open your workspace <ArrowRight className="ml-2 h-4 w-4" /></Button>
          <p className="mt-6 text-center text-xs text-muted-foreground">BraveEdge Technology · Secure school management for modern institutions</p>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-background">
      <div className="relative hidden w-1/2 overflow-hidden bg-gradient-to-br from-primary via-primary/90 to-cyan-950 lg:block">
        <div className="absolute inset-0 opacity-20 [background-image:radial-gradient(circle_at_20%_20%,white_1px,transparent_1px)] [background-size:28px_28px]" />
        <div className="relative flex h-full flex-col justify-between p-12 text-primary-foreground">
          <Image src="/clearis.png" alt="Clearis" width={1536} height={1024} priority className="h-11 w-auto rounded-lg object-contain object-left" />
          <div><h1 className="max-w-md text-4xl font-bold leading-tight">Your school, on one platform.</h1><p className="mt-4 max-w-md text-primary-foreground/80">Build a trusted digital home for your school, from first setup to everyday operations.</p></div>
          <p className="text-sm text-primary-foreground/65">BraveEdge Technology · Built for schools that mean business.</p>
        </div>
      </div>
      <div className="flex w-full items-center justify-center bg-gradient-to-b from-background to-muted/30 p-5 sm:p-8 lg:w-1/2">
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="w-full max-w-xl">
          <Link href="/login" className="mb-6 inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"><ArrowLeft className="h-4 w-4" /> Back to sign in</Link>
          <div className="mb-5 flex items-center gap-2"><ShieldCheck className="h-5 w-5 text-primary" /><span className="text-sm font-semibold">Create a verified school workspace</span></div>
          <div className="mb-6 flex items-center gap-2">{steps.map((label, index) => <div key={label} className="flex flex-1 items-center gap-2"><span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ${index <= step ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"}`}>{index < step ? <Check className="h-4 w-4" /> : index + 1}</span><span className={`hidden text-xs sm:block ${index === step ? "font-semibold" : "text-muted-foreground"}`}>{label}</span>{index < steps.length - 1 && <span className="h-px flex-1 bg-border" />}</div>)}</div>
          <div className="rounded-2xl border bg-card p-6 shadow-xl shadow-primary/5 sm:p-8">
            <h2 className="text-2xl font-bold tracking-tight">{steps[step]}</h2>
            <p className="mt-1 text-sm text-muted-foreground">{step === 0 ? "Tell us about your institution." : step === 1 ? "Create the trusted owner account." : "Review the details before creating your workspace."}</p>
            <form onSubmit={handleSubmit(onSubmit)} className="mt-7 space-y-4">
              {step === 0 && <>
                <div className="grid gap-4 sm:grid-cols-2"><Field label="School name" error={errors.school_name?.message}><Input placeholder="Brightfield Academy" {...register("school_name")} /></Field><Field label="School type" error={errors.school_type?.message}><Input placeholder="Primary or Secondary" {...register("school_type")} /></Field></div>
                <div className="grid gap-4 sm:grid-cols-2"><Field label="Established year"><Input type="number" placeholder="2008" {...register("established_year")} /></Field><Field label="School website"><Input placeholder="https://school.edu" {...register("website")} /></Field></div>
                <div className="grid gap-4 sm:grid-cols-2"><Field label="School email" error={errors.school_email?.message}><Input type="email" placeholder="office@school.edu" {...register("school_email")} /></Field><Field label="Phone"><Input placeholder="+234 800 000 0000" {...register("phone")} /></Field></div>
                <Field label="Address"><Input placeholder="Street address" {...register("address")} /></Field><Field label="State / region"><Input placeholder="Lagos" {...register("state")} /></Field>
                <div className="rounded-xl border border-dashed p-4"><div className="flex items-center gap-3"><ImagePlus className="h-5 w-5 text-primary" /><div className="min-w-0 flex-1"><p className="text-sm font-semibold">School logo <span className="font-normal text-muted-foreground">(optional)</span></p><p className="text-xs text-muted-foreground">Your logo replaces the Clearis logo across the school workspace.</p></div><label className="cursor-pointer rounded-md bg-primary/10 px-3 py-2 text-xs font-semibold text-primary">Choose<input type="file" accept="image/jpeg,image/png,image/webp" onChange={pickLogo} className="sr-only" /></label></div>{logoPreview && <img src={logoPreview} alt="School logo preview" className="mt-3 h-16 w-16 rounded-lg border bg-white object-contain" />}{logoNotice && <p className="mt-2 text-xs text-warning">{logoNotice}</p>}</div>
              </>}
              {step === 1 && <><Field label="Your full name" error={errors.admin_full_name?.message}><Input placeholder="Jane Doe" {...register("admin_full_name")} /></Field><Field label="Work email" error={errors.admin_email?.message}><Input type="email" placeholder="you@school.edu" {...register("admin_email")} /></Field><div className="grid gap-4 sm:grid-cols-2"><Field label="Password" error={errors.password?.message}><Input type="password" placeholder="At least 8 characters" {...register("password")} /></Field><Field label="Confirm password" error={errors.confirm?.message}><Input type="password" {...register("confirm")} /></Field></div><label className="flex gap-3 rounded-xl border bg-muted/30 p-4 text-sm"><input type="checkbox" className="mt-0.5 h-4 w-4 accent-primary" {...register("authorized")} /><span>I confirm that I am authorized to create and manage this school workspace on behalf of the institution.</span></label>{errors.authorized && <p className="text-xs text-destructive">{errors.authorized.message}</p>}</>}
              {step === 2 && <div className="space-y-4"><div className="rounded-xl border bg-gradient-to-r from-primary/10 to-cyan-400/10 p-5"><div className="flex items-center gap-4">{logoPreview ? <img src={logoPreview} alt="School logo" className="h-16 w-16 rounded-xl border bg-white object-contain" /> : <Image src="/clearis.png" alt="Clearis" width={160} height={55} className="h-12 w-auto object-contain" />}<div><p className="text-lg font-bold">{values.school_name || "Your school"}</p><p className="text-sm capitalize text-muted-foreground">{values.school_type || "School"} · {values.state || "Nigeria"}</p></div></div><p className="mt-5 text-xs text-muted-foreground">This is how your school identity will appear to staff, families, and on official reports.</p></div><div className="grid gap-2 text-sm sm:grid-cols-2">{[values.website, values.school_email, values.phone, values.address].filter(Boolean).map((item) => <p key={item} className="rounded-lg border px-3 py-2 text-muted-foreground">{item}</p>)}</div><p className="text-xs text-muted-foreground">By creating this workspace, you agree to Clearis&apos;s terms and privacy practices. Verification status will be visible in School Settings.</p></div>}
              {error && <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</div>}
              <div className="flex gap-3 pt-2">{step > 0 && <Button type="button" variant="outline" onClick={() => setStep((current) => current - 1)}><ArrowLeft className="mr-2 h-4 w-4" /> Back</Button>}{step < 2 ? <Button type="button" className="ml-auto" onClick={nextStep}>Continue <ArrowRight className="ml-2 h-4 w-4" /></Button> : <Button type="submit" className="ml-auto" disabled={isSubmitting}>{isSubmitting ? "Creating workspace..." : "Create workspace"} <ArrowRight className="ml-2 h-4 w-4" /></Button>}</div>
            </form>
          </div>
          <p className="mt-5 text-center text-xs text-muted-foreground">Secure school data · Role-based access · Automated backups · BraveEdge Technology</p>
        </motion.div>
      </div>
    </div>
  );
}

function Field({ label, error, children }: { label: string; error?: string; children: React.ReactNode }) {
  return <div className="space-y-1.5"><Label>{label}</Label>{children}{error && <p className="text-xs text-destructive">{error}</p>}</div>;
}