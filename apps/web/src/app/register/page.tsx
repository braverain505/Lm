"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { api } from "@schoolos/shared";
import { motion } from "framer-motion";
import { ArrowLeft, ArrowRight } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/providers/auth-provider";

const schema = z
  .object({
    school_name: z.string().min(2, "School name is required"),
    school_type: z.string().min(2, "School type is required"),
    admin_full_name: z.string().min(2, "Your full name is required"),
    admin_email: z.string().email("Enter a valid email"),
    password: z.string().min(8, "Password must be at least 8 characters"),
    confirm: z.string(),
  })
  .refine((d) => d.password === d.confirm, { message: "Passwords do not match", path: ["confirm"] });

type RegisterForm = z.infer<typeof schema>;

export default function RegisterPage() {
  const router = useRouter();
  const { refreshMe } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<RegisterForm>({ resolver: zodResolver(schema) });

  const onSubmit = async (values: RegisterForm) => {
    setError(null);
    try {
      await api.registerSchool({
        school_name: values.school_name,
        school_type: values.school_type,
        admin_email: values.admin_email,
        admin_full_name: values.admin_full_name,
        password: values.password,
      });
      await refreshMe();
      router.replace("/dashboard");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Registration failed");
    }
  };

  return (
    <div className="flex min-h-screen bg-background">
      {/* Left: brand */}
      <div className="relative hidden w-1/2 overflow-hidden bg-gradient-to-br from-primary via-primary/90 to-indigo-950 lg:block">
        <div className="absolute inset-0 opacity-20 [background-image:radial-gradient(circle_at_20%_20%,white_1px,transparent_1px)] [background-size:28px_28px]" />
        <div className="absolute -right-24 -top-24 h-96 w-96 rounded-full bg-white/10 blur-3xl" />
        <div className="absolute -bottom-32 -left-20 h-96 w-96 rounded-full bg-indigo-300/20 blur-3xl" />

        <div className="relative flex h-full flex-col justify-between p-12 text-primary-foreground">
          <div className="flex items-center gap-3">
            <Image
              src="/lumo-logo.png"
              alt="Lumo"
              width={1536}
              height={1024}
              priority
              className="h-11 w-auto rounded-lg object-contain"
            />
          </div>

          <div>
            <motion.h1
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6 }}
              className="max-w-md text-4xl font-bold leading-tight"
            >
              Your school, on one platform.
            </motion.h1>
            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.1 }}
              className="mt-4 max-w-md text-primary-foreground/80"
            >
              Set up your school in minutes — sessions, classes, students, staff, results and finance.
            </motion.p>
          </div>

          <p className="text-sm text-primary-foreground/50">
            © {new Date().getFullYear()} Lumo. Built for schools that mean business.
          </p>
        </div>
      </div>

      {/* Right: form */}
      <div className="flex w-full items-center justify-center bg-gradient-to-b from-background to-muted/30 p-6 lg:w-1/2">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="w-full max-w-md"
        >
          <div className="mb-6 flex items-center gap-2 text-sm text-muted-foreground">
            <Link href="/login" className="inline-flex items-center gap-1 font-medium text-primary hover:underline">
              <ArrowLeft className="h-4 w-4" /> Back to sign in
            </Link>
          </div>

          {/* Mobile logo */}
          <div className="mb-8 flex items-center justify-center gap-2 lg:hidden">
            <Image
              src="/lumo-logo.png"
              alt="Lumo"
              width={1536}
              height={1024}
              priority
              className="h-10 w-auto rounded-lg object-contain"
            />
          </div>

          <div className="rounded-2xl border bg-card p-8 shadow-xl shadow-primary/5">
            <h2 className="text-2xl font-bold tracking-tight">Create your school</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Start your free workspace — takes about a minute.
            </p>

            <form onSubmit={handleSubmit(onSubmit)} className="mt-8 space-y-4">
              <div className="space-y-2">
                <Label htmlFor="school_name">School name</Label>
                <Input id="school_name" placeholder="Brightfield Academy" className="h-11" {...register("school_name")} />
                {errors.school_name && <p className="text-xs text-destructive">{errors.school_name.message}</p>}
              </div>
              <div className="space-y-2">
                <Label htmlFor="school_type">School type</Label>
                <Input id="school_type" placeholder="e.g. Secondary" className="h-11" {...register("school_type")} />
                {errors.school_type && <p className="text-xs text-destructive">{errors.school_type.message}</p>}
              </div>
              <div className="space-y-2">
                <Label htmlFor="admin_full_name">Your full name</Label>
                <Input id="admin_full_name" placeholder="Jane Doe" className="h-11" {...register("admin_full_name")} />
                {errors.admin_full_name && <p className="text-xs text-destructive">{errors.admin_full_name.message}</p>}
              </div>
              <div className="space-y-2">
                <Label htmlFor="admin_email">Work email</Label>
                <Input id="admin_email" type="email" placeholder="you@school.edu" className="h-11" {...register("admin_email")} />
                {errors.admin_email && <p className="text-xs text-destructive">{errors.admin_email.message}</p>}
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="password">Password</Label>
                  <Input id="password" type="password" placeholder="••••••••" className="h-11" {...register("password")} />
                  {errors.password && <p className="text-xs text-destructive">{errors.password.message}</p>}
                </div>
                <div className="space-y-2">
                  <Label htmlFor="confirm">Confirm</Label>
                  <Input id="confirm" type="password" placeholder="••••••••" className="h-11" {...register("confirm")} />
                  {errors.confirm && <p className="text-xs text-destructive">{errors.confirm.message}</p>}
                </div>
              </div>

              {error && (
                <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {error}
                </div>
              )}

              <Button type="submit" className="h-11 w-full text-base" disabled={isSubmitting}>
                {isSubmitting ? "Creating…" : "Create school"}
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </form>
          </div>
        </motion.div>
      </div>
    </div>
  );
}