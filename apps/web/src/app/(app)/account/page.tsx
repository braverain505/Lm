"use client";

import { useMutation } from "@tanstack/react-query";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { KeyRound, Mail, ShieldCheck } from "lucide-react";
import { useForm } from "react-hook-form";

import { api } from "@clearis/shared";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/toast";
import { useAuth } from "@/providers/auth-provider";

const schema = z
  .object({
    current_password: z.string().min(1, "Enter your current password"),
    new_password: z.string().min(8, "At least 8 characters"),
    confirm_password: z.string().min(1, "Confirm the new password"),
  })
  .refine((v) => v.new_password === v.confirm_password, {
    path: ["confirm_password"],
    message: "Passwords must match",
  });
type Form = z.infer<typeof schema>;

/**
 * The signed-in person's own page — reachable by every role, unlike School
 * Settings. A teacher can see the username they sign in with and change their
 * password without an admin resetting it for them.
 */
export default function AccountPage() {
  const { user, activeSchool } = useAuth();
  const { toast } = useToast();

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isDirty },
  } = useForm<Form>({ resolver: zodResolver(schema) });

  const changePassword = useMutation({
    mutationFn: api.changePassword,
    onSuccess: () => {
      reset();
      toast("Password changed successfully");
    },
    onError: (e) => {
      toast(e instanceof Error && e.message ? e.message : "Could not change the password", "error");
    },
  });

  const onSubmit = (values: Form) =>
    changePassword.mutate({
      current_password: values.current_password,
      new_password: values.new_password,
    });

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">My account</h1>
        <p className="text-sm text-muted-foreground">
          Your sign-in details and password.
        </p>
      </div>

      <Card className="premium-card">
        <CardHeader>
          <CardTitle className="text-[15px]">Sign-in details</CardTitle>
          <CardDescription>Use either your email or your username to sign in.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-3">
            <Avatar name={user?.full_name} className="h-11 w-11" />
            <div className="min-w-0">
              <p className="text-[14px] font-semibold">{user?.full_name}</p>
              <p className="truncate text-[11.5px] text-muted-foreground">{user?.email}</p>
            </div>
          </div>

          <div className="space-y-1.5">
            <div className="flex items-center justify-between gap-3 rounded-xl border border-border/60 px-3 py-2.5 text-[13px]">
              <span className="flex items-center gap-2 text-muted-foreground/90">
                <Mail className="h-3.5 w-3.5" /> Email
              </span>
              <span className="truncate font-medium">{user?.email}</span>
            </div>
            <div className="flex items-center justify-between gap-3 rounded-xl border border-border/60 px-3 py-2.5 text-[13px]">
              <span className="flex items-center gap-2 text-muted-foreground/90">
                <KeyRound className="h-3.5 w-3.5" /> Username
              </span>
              <span className="truncate font-medium">
                {user?.username ? `@${user.username}` : "Not set"}
              </span>
            </div>
            <div className="flex items-center justify-between gap-3 rounded-xl border border-border/60 px-3 py-2.5 text-[13px]">
              <span className="flex items-center gap-2 text-muted-foreground/90">
                <ShieldCheck className="h-3.5 w-3.5" /> Role
              </span>
              <Badge variant="default" className="capitalize">
                {activeSchool?.role?.name ?? "Member"}
              </Badge>
            </div>
          </div>

          {!user?.username && (
            <p className="text-[12px] leading-relaxed text-muted-foreground/90">
              A username can be added to your login by a school administrator; until then,
              sign in with your email.
            </p>
          )}
        </CardContent>
      </Card>

      <Card className="premium-card">
        <CardHeader>
          <CardTitle className="text-[15px]">Change password</CardTitle>
          <CardDescription>
            Your current password is required. You stay signed in on this device.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="grid gap-4 sm:grid-cols-3">
            <div className="space-y-1.5">
              <Label htmlFor="current_password">Current password</Label>
              <Input
                id="current_password"
                type="password"
                autoComplete="current-password"
                {...register("current_password")}
                className={errors.current_password ? "border-destructive" : undefined}
              />
              {errors.current_password && (
                <p className="text-[11px] text-destructive">{errors.current_password.message}</p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="new_password">New password</Label>
              <Input
                id="new_password"
                type="password"
                autoComplete="new-password"
                {...register("new_password")}
                className={errors.new_password ? "border-destructive" : undefined}
              />
              {errors.new_password && (
                <p className="text-[11px] text-destructive">{errors.new_password.message}</p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="confirm_password">Confirm new password</Label>
              <Input
                id="confirm_password"
                type="password"
                autoComplete="new-password"
                {...register("confirm_password")}
                className={errors.confirm_password ? "border-destructive" : undefined}
              />
              {errors.confirm_password && (
                <p className="text-[11px] text-destructive">{errors.confirm_password.message}</p>
              )}
            </div>
            <div className="sm:col-span-3">
              <Button type="submit" disabled={!isDirty} isLoading={changePassword.isPending}>
                Change password
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
