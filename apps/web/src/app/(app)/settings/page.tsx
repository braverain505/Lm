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

  // Change Password Form
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
    defaultValues: {
      current_password: "",
      new_password: "",
      confirm_password: "",
    },
  });

  const changePasswordMutation = useMutation({
    mutationFn: api.changePassword,
    onSuccess: () => {
      cpReset();
      alert("Password changed successfully");
    },
    onError: (error: any) => {
      alert(error?.response?.data?.message ?? "Failed to change password");
    },
  });

  const onCpSubmit = (data: z.infer<typeof changePasswordSchema>) => {
    changePasswordMutation.mutate(data);
  };

  // Change Email Form
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
    defaultValues: {
      new_email: "",
      current_password: "",
    },
  });

  const changeEmailMutation = useMutation({
    mutationFn: api.changeEmail,
    onSuccess: () => {
      ceReset();
      alert("Email changed successfully");
    },
    onError: (error: any) => {
      alert(error?.response?.data?.message ?? "Failed to change email");
    },
  });

  const onCeSubmit = (data: z.infer<typeof changeEmailSchema>) => {
    changeEmailMutation.mutate(data);
  };

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h2 className="text-xl font-bold tracking-tight">School Settings</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          School profile, academic structure and your account.
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {/* School profile */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Building2 className="h-4 w-4 text-primary" /> School profile
            </CardTitle>
            <CardDescription>Identifiers used across Lumo</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {isLoading ? (
              <Skeleton className="h-40 w-full" />
            ) : (
              <>
                <div className="flex items-center gap-3 rounded-xl border bg-muted/30 p-4">
                  <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10 text-primary">
                    <Building2 className="h-5 w-5" />
                  </span>
                  <div>
                    <p className="font-semibold">{school?.name ?? activeSchool?.school_name}</p>
                    <p className="text-xs capitalize text-muted-foreground">
                      {school?.school_type ?? "School"}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3 rounded-xl border bg-muted/30 p-4">
                  {school?.logo_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={school.logo_url}
                      alt="School logo"
                      className="h-14 w-14 rounded-xl border object-contain bg-white"
                    />
                  ) : (
                    <span className="flex h-14 w-14 items-center justify-center rounded-xl border bg-background text-muted-foreground">
                      <ImagePlus className="h-6 w-6" />
                    </span>
                  )}
                  <div className="min-w-0">
                    <p className="text-sm font-medium">School logo</p>
                    <p className="text-xs text-muted-foreground">
                      Shown on the report card header. JPEG, PNG or WebP up to 5 MB.
                    </p>
                    <input
                      ref={logoInputRef}
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      onChange={onPickLogo}
                      className="mt-1 block w-full max-w-56 text-xs text-muted-foreground file:mr-2 file:rounded-md file:border-0 file:bg-primary/10 file:px-2.5 file:py-1 file:text-xs file:font-medium file:text-primary hover:file:bg-primary/20"
                    />
                    {logoUploading && (
                      <p className="mt-1 text-xs text-muted-foreground">Uploading logo…</p>
                    )}
                  </div>
                </div>
                <dl className="space-y-2 text-sm">
                  {[
                    { icon: Globe, label: "Slug", value: school?.slug },
                    { icon: Timer, label: "Timezone", value: school?.timezone },
                    { icon: CalendarRange, label: "Current session", value: overview?.current_session ?? "—" },
                    { icon: ShieldCheck, label: "Currency", value: school?.currency },
                  ].map(({ icon: Icon, label, value }) => (
                    <div key={label} className="flex items-center gap-3">
                      <Icon className="h-4 w-4 text-muted-foreground" />
                      <dt className="w-36 text-muted-foreground">{label}</dt>
                      <dd className="font-medium">{value ?? "—"}</dd>
                    </div>
                  ))}
                </dl>
              </>
            )}
          </CardContent>
        </Card>

        {/* Account */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Your account</CardTitle>
            <CardDescription>Signed in identity and role</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center gap-3">
              <Avatar name={user?.full_name} className="h-12 w-12" />
              <div className="min-w-0">
                <p className="font-semibold">{user?.full_name}</p>
                <p className="truncate text-xs text-muted-foreground">{user?.email}</p>
              </div>
            </div>
            <div className="space-y-1.5">
              <div className="flex items-center justify-between rounded-lg border px-3 py-2 text-sm">
                <span className="text-muted-foreground">School</span>
                <span className="font-medium">{activeSchool?.school_name}</span>
              </div>
              <div className="flex items-center justify-between rounded-lg border px-3 py-2 text-sm">
                <span className="text-muted-foreground">Role</span>
                <Badge variant="default" className="capitalize">{activeSchool?.role?.name ?? "Member"}</Badge>
              </div>
            </div>
            <div className="flex items-center gap-3 text-xs text-muted-foreground">
              <Mail className="h-3.5 w-3.5" /> {user?.email}
              <Phone className="h-3.5 w-3.5" /> {school?.phone ?? "—"}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Sign-in credentials */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <KeyRound className="h-4 w-4 text-primary" /> Sign-in credentials
          </CardTitle>
          <CardDescription>
            Update the login used to access Lumo. Your current password is
            required to make any change.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-6 md:grid-cols-2">
          <form onSubmit={cpHandleSubmit(onCpSubmit)} className="space-y-4">
            <div>
              <Label htmlFor="current_password">Current Password</Label>
              <Input
                id="current_password"
                type="password"
                {...cpRegister("current_password")}
                className={cpErrors.current_password ? "border-destructive" : undefined}
                placeholder="Enter current password"
              />
              {cpErrors.current_password && (
                <p className="text-xs text-destructive">{cpErrors.current_password.message}</p>
              )}
            </div>
            <div>
              <Label htmlFor="new_password">New Password</Label>
              <Input
                id="new_password"
                type="password"
                {...cpRegister("new_password")}
                className={cpErrors.new_password ? "border-destructive" : undefined}
                placeholder="Enter new password"
              />
              {cpErrors.new_password && (
                <p className="text-xs text-destructive">{cpErrors.new_password.message}</p>
              )}
            </div>
            <div>
              <Label htmlFor="confirm_password">Confirm Password</Label>
              <Input
                id="confirm_password"
                type="password"
                {...cpRegister("confirm_password")}
                className={cpErrors.confirm_password ? "border-destructive" : undefined}
                placeholder="Confirm new password"
              />
              {cpErrors.confirm_password && (
                <p className="text-xs text-destructive">{cpErrors.confirm_password.message}</p>
              )}
            </div>
            <Button
              type="submit"
              disabled={!cpIsValid}
              className="w-full"
            >
              Change Password
            </Button>
          </form>

          <form onSubmit={ceHandleSubmit(onCeSubmit)} className="space-y-4">
            <div>
              <Label htmlFor="new_email">New Email</Label>
              <Input
                id="new_email"
                type="email"
                {...ceRegister("new_email")}
                className={ceErrors.new_email ? "border-destructive" : undefined}
                placeholder="Enter new email"
              />
              {ceErrors.new_email && (
                <p className="text-xs text-destructive">{ceErrors.new_email.message}</p>
              )}
            </div>
            <div>
              <Label htmlFor="current_password">Current Password</Label>
              <Input
                id="current_password"
                type="password"
                {...ceRegister("current_password")}
                className={ceErrors.current_password ? "border-destructive" : undefined}
                placeholder="Enter current password"
              />
              {ceErrors.current_password && (
                <p className="text-xs text-destructive">{ceErrors.current_password.message}</p>
              )}
            </div>
            <Button
              type="submit"
              disabled={Object.keys(ceErrors).length > 0}
              className="w-full"
            >
              Change Email
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Sessions */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <CalendarRange className="h-4 w-4 text-primary" /> Academic sessions
          </CardTitle>
          <CardDescription>Sessions configured for this school</CardDescription>
        </CardHeader>
        <CardContent>
          {sessions.length === 0 ? (
            <p className="text-sm text-muted-foreground">No sessions have been created yet.</p>
          ) : (
            <ul className="divide-y">
              {sessions.map((s) => (
                <li key={s.id} className="flex items-center justify-between py-3 text-sm">
                  <div>
                    <p className="font-medium">{s.name}</p>
                    <p className="text-xs text-muted-foreground">
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