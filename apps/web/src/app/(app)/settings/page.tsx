"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Building2, CalendarRange, Globe, ImagePlus, KeyRound, Mail, Phone, ShieldCheck, Timer } from "lucide-react";
import { useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

import { api } from "@schoolos/shared";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useActiveSchoolId, useSchoolMe, useOverview, useSessions } from "@/hooks/use-api";
import { useAuth } from "@/providers/auth-provider";
import { Avatar } from "@/components/ui/avatar";

export default function SettingsPage() {
  const { user, activeSchool } = useAuth();
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  const { data: school, isLoading } = useSchoolMe();
  const { data: overview } = useOverview();
  const { data: sessions = [] } = useSessions();

  const [logoUploading, setLogoUploading] = useState(false);
  const logoInputRef = useRef<HTMLInputElement>(null);

  const onPickLogo = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !schoolId) return;
    setLogoUploading(true);
    try {
      await api.uploadSchoolLogo(schoolId, file);
      void queryClient.invalidateQueries({ queryKey: ["school", schoolId] });
    } finally {
      setLogoUploading(false);
      if (logoInputRef.current) logoInputRef.current.value = "";
    }
  };

  const changePasswordSchema = z.object({
    current_password: z.string().min(1, "Current password is required"),
    new_password: z.string().min(8, "New password must be at least 8 characters"),
    confirm_password: z.string(),
  }).refine(data => data.new_password === data.confirm_password, {
    message: "Passwords must match",
    path: ["confirm_password"],
  });

  const {
    register: cpRegister,
    handleSubmit: cpHandleSubmit,
    formState: { errors: cpErrors, isValid: cpIsValid },
    reset: cpReset,
  } = useForm<z.infer<typeof changePasswordSchema>>({
    resolver: zodResolver(changePasswordSchema),
    defaultValues: { current_password: "", new_password: "", confirm_password: "" },
  });

  const changePasswordMutation = useMutation({
    mutationFn: api.changePassword,
    onSuccess: () => { cpReset(); alert("Password changed successfully"); },
    onError: (error: any) => { alert(error?.response?.data?.message ?? "Failed to change password"); },
  });

  const onCpSubmit = (data: z.infer<typeof changePasswordSchema>) => {
    changePasswordMutation.mutate(data);
  };

  const changeEmailSchema = z.object({
    new_email: z.string().email("Invalid email address"),
    current_password: z.string().min(1, "Current password is required"),
  });

  const {
    register: ceRegister,
    handleSubmit: ceHandleSubmit,
    formState: { errors: ceErrors },
    reset: ceReset,
  } = useForm<z.infer<typeof changeEmailSchema>>({
    resolver: zodResolver(changeEmailSchema),
    defaultValues: { new_email: "", current_password: "" },
  });

  const changeEmailMutation = useMutation({
    mutationFn: api.changeEmail,
    onSuccess: () => { ceReset(); alert("Email changed successfully"); },
    onError: (error: any) => { alert(error?.response?.data?.message ?? "Failed to change email"); },
  });

  const onCeSubmit = (data: z.infer<typeof changeEmailSchema>) => {
    changeEmailMutation.mutate(data);
  };

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <div>
        <h2 className="text-[22px] font-bold tracking-tight text-foreground">School Settings</h2>
        <p className="mt-1 text-[13px] text-muted-foreground">
          School profile, academic structure and your account.
        </p>
      </div>

      <div className="grid gap-5 md:grid-cols-2">
        {/* School profile */}
        <Card className="premium-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-[15px]">
              <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-primary/10">
                <Building2 className="h-4 w-4 text-primary" />
              </span>
              School profile
            </CardTitle>
            <CardDescription>Identifiers used across Lumo</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {isLoading ? (
              <Skeleton className="h-40 w-full" />
            ) : (
              <>
                <div className="flex items-center gap-3 rounded-xl border border-border/40 bg-muted/20 p-4">
                  <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
                    <Building2 className="h-5 w-5" />
                  </span>
                  <div>
                    <p className="text-[13px] font-semibold">{school?.name ?? activeSchool?.school_name}</p>
                    <p className="text-[11px] capitalize text-muted-foreground">
                      {school?.school_type ?? "School"}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3 rounded-xl border border-border/40 bg-muted/20 p-4">
                  {school?.logo_url ? (
                    <img src={school.logo_url} alt="School logo" className="h-12 w-12 rounded-xl border object-contain bg-white" />
                  ) : (
                    <span className="flex h-12 w-12 items-center justify-center rounded-xl border border-dashed border-border bg-background text-muted-foreground/40">
                      <ImagePlus className="h-5 w-5" />
                    </span>
                  )}
                  <div className="min-w-0">
                    <p className="text-[13px] font-medium">School logo</p>
                    <p className="text-[11px] text-muted-foreground/70">
                      Shown on report card header. JPEG, PNG or WebP up to 5 MB.
                    </p>
                    <input
                      ref={logoInputRef}
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      onChange={onPickLogo}
                      className="mt-1 block w-full max-w-56 text-[11px] text-muted-foreground file:mr-2 file:rounded-lg file:border-0 file:bg-primary/10 file:px-2.5 file:py-1 file:text-[11px] file:font-semibold file:text-primary hover:file:bg-primary/20"
                    />
                    {logoUploading && (
                      <p className="mt-1 text-[11px] text-muted-foreground/60">Uploading logo…</p>
                    )}
                  </div>
                </div>
                <dl className="space-y-2 text-[13px]">
                  {[
                    { icon: Globe, label: "Slug", value: school?.slug },
                    { icon: Timer, label: "Timezone", value: school?.timezone },
                    { icon: CalendarRange, label: "Current session", value: overview?.current_session ?? "—" },
                    { icon: ShieldCheck, label: "Currency", value: school?.currency },
                  ].map(({ icon: Icon, label, value }) => (
                    <div key={label} className="flex items-center gap-3">
                      <Icon className="h-4 w-4 text-muted-foreground/50" />
                      <dt className="w-36 text-muted-foreground/70">{label}</dt>
                      <dd className="font-medium">{value ?? "—"}</dd>
                    </div>
                  ))}
                </dl>
              </>
            )}
          </CardContent>
        </Card>

        {/* Account */}
        <Card className="premium-card">
          <CardHeader>
            <CardTitle className="text-[15px]">Your account</CardTitle>
            <CardDescription>Signed in identity and role</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center gap-3">
              <Avatar name={user?.full_name} className="h-11 w-11" />
              <div className="min-w-0">
                <p className="text-[14px] font-semibold">{user?.full_name}</p>
                <p className="truncate text-[11.5px] text-muted-foreground">{user?.email}</p>
              </div>
            </div>
            <div className="space-y-1.5">
              <div className="flex items-center justify-between rounded-xl border border-border/40 px-3 py-2.5 text-[13px]">
                <span className="text-muted-foreground/70">School</span>
                <span className="font-medium">{activeSchool?.school_name}</span>
              </div>
              <div className="flex items-center justify-between rounded-xl border border-border/40 px-3 py-2.5 text-[13px]">
                <span className="text-muted-foreground/70">Role</span>
                <Badge variant="default" className="capitalize">{activeSchool?.role?.name ?? "Member"}</Badge>
              </div>
            </div>
            <div className="flex items-center gap-3 text-[11.5px] text-muted-foreground/70">
              <Mail className="h-3.5 w-3.5" /> {user?.email}
              <Phone className="h-3.5 w-3.5" /> {school?.phone ?? "—"}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Sign-in credentials */}
      <Card className="premium-card">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-[15px]">
            <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-primary/10">
              <KeyRound className="h-4 w-4 text-primary" />
            </span>
            Sign-in credentials
          </CardTitle>
          <CardDescription>
            Update the login used to access Lumo. Your current password is required to make any change.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-6 md:grid-cols-2">
          <form onSubmit={cpHandleSubmit(onCpSubmit)} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="current_password">Current Password</Label>
              <Input
                id="current_password"
                type="password"
                {...cpRegister("current_password")}
                className={cpErrors.current_password ? "border-destructive" : undefined}
                placeholder="Enter current password"
              />
              {cpErrors.current_password && (
                <p className="text-[11px] text-destructive">{cpErrors.current_password.message}</p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="new_password">New Password</Label>
              <Input
                id="new_password"
                type="password"
                {...cpRegister("new_password")}
                className={cpErrors.new_password ? "border-destructive" : undefined}
                placeholder="Enter new password"
              />
              {cpErrors.new_password && (
                <p className="text-[11px] text-destructive">{cpErrors.new_password.message}</p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="confirm_password">Confirm Password</Label>
              <Input
                id="confirm_password"
                type="password"
                {...cpRegister("confirm_password")}
                className={cpErrors.confirm_password ? "border-destructive" : undefined}
                placeholder="Confirm new password"
              />
              {cpErrors.confirm_password && (
                <p className="text-[11px] text-destructive">{cpErrors.confirm_password.message}</p>
              )}
            </div>
            <Button type="submit" disabled={!cpIsValid} className="w-full">
              Change Password
            </Button>
          </form>

          <form onSubmit={ceHandleSubmit(onCeSubmit)} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="new_email">New Email</Label>
              <Input
                id="new_email"
                type="email"
                {...ceRegister("new_email")}
                className={ceErrors.new_email ? "border-destructive" : undefined}
                placeholder="Enter new email"
              />
              {ceErrors.new_email && (
                <p className="text-[11px] text-destructive">{ceErrors.new_email.message}</p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="current_password">Current Password</Label>
              <Input
                id="current_password"
                type="password"
                {...ceRegister("current_password")}
                className={ceErrors.current_password ? "border-destructive" : undefined}
                placeholder="Enter current password"
              />
              {ceErrors.current_password && (
                <p className="text-[11px] text-destructive">{ceErrors.current_password.message}</p>
              )}
            </div>
            <Button type="submit" disabled={Object.keys(ceErrors).length > 0} className="w-full">
              Change Email
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Sessions */}
      <Card className="premium-card">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-[15px]">
            <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-primary/10">
              <CalendarRange className="h-4 w-4 text-primary" />
            </span>
            Academic sessions
          </CardTitle>
          <CardDescription>Sessions configured for this school</CardDescription>
        </CardHeader>
        <CardContent>
          {sessions.length === 0 ? (
            <p className="text-[13px] text-muted-foreground/70">No sessions have been created yet.</p>
          ) : (
            <ul className="divide-y divide-border/40">
              {sessions.map((s) => (
                <li key={s.id} className="flex items-center justify-between py-3 text-[13px]">
                  <div>
                    <p className="font-medium">{s.name}</p>
                    <p className="text-[11px] text-muted-foreground/60">
                      {s.start_date ?? "—"} → {s.end_date ?? "—"}
                    </p>
                  </div>
                  {s.is_current ? (
                    <Badge variant="success">Current</Badge>
                  ) : (
                    <Badge variant="outline">{s.status}</Badge>
                  )}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
