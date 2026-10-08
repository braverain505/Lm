"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Building2, CalendarRange, Globe, ImagePlus, KeyRound, LayoutTemplate, Lock, Mail, Phone, Plus, Power, ShieldCheck, Timer, Trash2, Unlock } from "lucide-react";
import Link from "next/link";
import { useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

import { api, type ReportTheme, type Term } from "@clearis/shared";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useActiveSchoolId, useSchoolMe, useOverview, useSessions, useTerms, useCloseTerm, useReportCardDesign, useCreateReportCardTemplate, useUpdateReportCardTemplate } from "@/hooks/use-api";
import { useAuth } from "@/providers/auth-provider";
import { useSessionTerm } from "@/providers/session-context";
import { isSchoolAdminRole } from "@/lib/roles";
import { Avatar } from "@/components/ui/avatar";
import { useToast } from "@/components/toast";
import { ReportTemplatePicker } from "@/components/report-template-picker";

export default function SettingsPage() {
  const { user, activeSchool } = useAuth();
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  const { data: school, isLoading } = useSchoolMe();
  const { data: overview } = useOverview();
  const { data: sessions = [], isLoading: loadingSessions } = useSessions();
  const { session: activeSession, setTerm, setSession } = useSessionTerm();
  const closeTerm = useCloseTerm();

  const [logoUploading, setLogoUploading] = useState(false);
  const logoInputRef = useRef<HTMLInputElement>(null);

  // The school's card style lives on its saved report card design, so changing it
  // here writes the design (everyone's cards then match) rather than a browser
  // preference.
  const { data: design } = useReportCardDesign();
  const updateCardTemplate = useUpdateReportCardTemplate();
  const createCardTemplate = useCreateReportCardTemplate();
  const themeBusy = updateCardTemplate.isPending || createCardTemplate.isPending;

  function handleThemeChange(theme: ReportTheme) {
    if (!design || design.theme === theme || themeBusy) return;
    const layout = { ...design.layout, theme };
    const onError = () => toast("Could not update the card style", "error");
    if (design.template_id) {
      updateCardTemplate.mutate(
        { templateId: design.template_id, layout },
        { onSuccess: () => toast("Card style updated for the school"), onError },
      );
      return;
    }
    createCardTemplate.mutate(
      { name: "School report card", layout, is_default: true },
      { onSuccess: () => toast("Card style saved for the school"), onError },
    );
  }

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["sessions"] });
    void queryClient.invalidateQueries({ queryKey: ["terms"] });
    // Removing a session or term changes the structure below it too — the
    // classes, their offerings/assignments and the term's components.
    void queryClient.invalidateQueries({ queryKey: ["arms"] });
    void queryClient.invalidateQueries({ queryKey: ["offerings"] });
    void queryClient.invalidateQueries({ queryKey: ["assignments"] });
    void queryClient.invalidateQueries({ queryKey: ["components"] });
  };

  // Track which session's terms we're showing
  const [selectedSessionId, setSelectedSessionId] = useState<string>(
    () => sessions.find((s) => s.is_current)?.id ?? sessions[0]?.id ?? ""
  );
  const { data: settingsTerms = [], isLoading: termsLoading } = useTerms(selectedSessionId || null);

  const onPickLogo = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !schoolId) return;
    setLogoUploading(true);
    try {
      await api.uploadSchoolLogo(schoolId, file);
      void queryClient.invalidateQueries({ queryKey: ["school", schoolId] });
      toast("School logo updated");
    } catch (e) {
      toast(e instanceof Error && e.message ? e.message : "Failed to upload logo", "error");
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

  const { toast } = useToast();

  const changePasswordMutation = useMutation({
    mutationFn: api.changePassword,
    onSuccess: () => { cpReset(); toast("Password changed successfully"); },
    onError: (error: any) => { toast(error?.response?.data?.message ?? "Failed to change password", "error"); },
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
    onSuccess: () => { ceReset(); toast("Email changed successfully"); },
    onError: (error: any) => { toast(error?.response?.data?.message ?? "Failed to change email", "error"); },
  });

  const onCeSubmit = (data: z.infer<typeof changeEmailSchema>) => {
    changeEmailMutation.mutate(data);
  };

  const handleCloseTerm = async (termId: string, termName: string) => {
    const confirmed = window.confirm(
      `Are you sure you want to close the ${termName} term?\n\n` +
      `This will:\n` +
      `• Prevent all score entries and result modifications\n` +
      `• Lock attendance records for this term\n` +
      `• Make all data read-only\n\n` +
      `This action cannot be undone. Continue?`
    );
    if (!confirmed) return;
    try {
      await closeTerm.mutateAsync(termId);
      void queryClient.invalidateQueries({ queryKey: ["terms"] });
      toast("Term closed successfully");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Failed to close term", "error");
    }
  };

  // --- Session creation ---
  const [sessionName, setSessionName] = useState("");
  const [sessionError, setSessionError] = useState<string | null>(null);
  const createSession = useMutation({
    mutationFn: async () => {
      if (!schoolId) throw new Error("No active school");
      return api.schoolFetch<{ id: string }>(schoolId, "/academics/sessions", {
        method: "POST",
        body: JSON.stringify({ name: sessionName, is_current: sessions.length === 0 }),
      });
    },
    onSuccess: () => {
      invalidate();
      setSessionName("");
      setSessionError(null);
      toast("Session created successfully");
    },
    onError: (err: Error) => {
      setSessionError(err.message || "Failed to create session.");
    },
  });

  const activateSession = useMutation({
    mutationFn: async (sessionId: string) => {
      if (!schoolId) throw new Error("No active school");
      return api.activateSession(schoolId, sessionId);
    },
    onSuccess: () => {
      invalidate();
      toast("Session activated");
    },
    onError: (err: Error) => toast(err.message || "Failed to activate session", "error"),
  });

  // Deleting is the undo for a session/term created by mistake. The API refuses
  // anything in use, so the confirmation can promise the guard rather than
  // hide the button.
  const deleteSession = useMutation({
    mutationFn: async (sessionId: string) => {
      if (!schoolId) throw new Error("No active school");
      return api.deleteSession(schoolId, sessionId);
    },
    onSuccess: (_data, sessionId) => {
      invalidate();
      // Keep the terms panel pointed at a session that still exists.
      if (selectedSessionId === sessionId) {
        setSelectedSessionId(sessions.find((s) => s.id !== sessionId)?.id ?? "");
      }
      toast("Session deleted");
    },
    onError: (err: Error) => toast(err.message || "Failed to delete session", "error"),
  });

  const handleDeleteSession = (sessionId: string, sessionName: string) => {
    const confirmed = window.confirm(
      `Delete the ${sessionName} session?\n\n` +
      `Its terms and classes will be removed too.\n` +
      `A session that is active or has students enrolled cannot be deleted.\n\n` +
      `This action cannot be undone. Continue?`
    );
    if (!confirmed) return;
    deleteSession.mutate(sessionId);
  };

  // --- Term creation ---
  const [termName, setTermName] = useState("");
  const [termNo, setTermNo] = useState(0);
  const [termError, setTermError] = useState<string | null>(null);
  const createTerm = useMutation({
    mutationFn: async () => {
      if (!schoolId) throw new Error("No active school");
      if (!selectedSessionId) throw new Error("Select a session first");
      return api.schoolFetch(schoolId, "/academics/terms", {
        method: "POST",
        body: JSON.stringify({ session_id: selectedSessionId, term_no: termNo, name: termName }),
      });
    },
    onSuccess: () => {
      invalidate();
      setTermName("");
      setTermNo(0);
      setTermError(null);
      toast("Term created successfully");
    },
    onError: (err: Error) => {
      setTermError(err.message || "Failed to create term.");
    },
  });

  // Switching terms is the admin's action. A term only accepts results work
  // when its session is open too, so opening the session is folded into the
  // same click — otherwise the admin activates a term that still refuses every
  // score save. The whole app is then pointed at the term they chose.
  const activateTerm = useMutation({
    mutationFn: async (term: Term) => {
      if (!schoolId) throw new Error("No active school");
      const parentSession =
        sessions.find((s) => s.id === term.academic_session_id) ?? null;
      const openedSession = !!parentSession && parentSession.status !== "open";
      if (openedSession) await api.activateSession(schoolId, parentSession!.id);
      await api.activateTerm(schoolId, term.id);
      return { term, parentSession, openedSession };
    },
    onSuccess: ({ term: activated, parentSession, openedSession }) => {
      // Point the app (header, score grids, everything) at the chosen term.
      if (parentSession && parentSession.id !== activeSession?.id) {
        setSelectedSessionId(parentSession.id);
        setSession(parentSession);
      } else {
        setTerm(activated);
      }
      invalidate();
      toast(
        openedSession
          ? `${activated.name} is now the active term (its session was opened too)`
          : `${activated.name} is now the active term`,
      );
    },
    onError: (err: Error) => toast(err.message || "Failed to activate term", "error"),
  });

  const deleteTerm = useMutation({
    mutationFn: async (termId: string) => {
      if (!schoolId) throw new Error("No active school");
      return api.deleteTerm(schoolId, termId);
    },
    onSuccess: () => {
      invalidate();
      toast("Term deleted");
    },
    onError: (err: Error) => toast(err.message || "Failed to delete term", "error"),
  });

  const handleDeleteTerm = (termId: string, termName: string) => {
    const confirmed = window.confirm(
      `Delete the ${termName} term?\n\n` +
      `A term with results or assessment components cannot be deleted — close it instead.\n\n` +
      `This action cannot be undone. Continue?`
    );
    if (!confirmed) return;
    deleteTerm.mutate(termId);
  };

  const canManage = activeSchool?.permissions?.includes("school.manage") ?? false;

  // School Settings is admin/principal only — teachers and other staff should
  // not be able to reach it even by URL.
  if (activeSchool && !isSchoolAdminRole(activeSchool?.role?.code)) {
    return (
      <div className="mx-auto max-w-xl py-16 text-center">
        <h2 className="text-xl font-semibold">School Settings</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Only school admins can manage settings.
        </p>
      </div>
    );
  }

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
              <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-primary/20">
                <Building2 className="h-4 w-4 text-primary" />
              </span>
              School profile
            </CardTitle>
            <CardDescription>Identifiers used across Clearis</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {isLoading ? (
              <Skeleton className="h-40 w-full" />
            ) : (
              <>
                <div className="flex items-center gap-3 rounded-xl border border-border/60 bg-muted/40 p-4">
                  <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/20 text-primary">
                    <Building2 className="h-5 w-5" />
                  </span>
                  <div>
                    <p className="text-[13px] font-semibold">{school?.name ?? activeSchool?.school_name}</p>
                    <p className="text-[11px] capitalize text-muted-foreground">
                      {school?.school_type ?? "School"}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3 rounded-xl border border-border/60 bg-muted/40 p-4">
                  {school?.logo_url ? (
                    <img src={school.logo_url} alt="School logo" className="h-12 w-12 rounded-xl border object-contain bg-white" />
                  ) : (
                    <span className="flex h-12 w-12 items-center justify-center rounded-xl border border-dashed border-border bg-background text-muted-foreground/65">
                      <ImagePlus className="h-5 w-5" />
                    </span>
                  )}
                  <div className="min-w-0">
                    <p className="text-[13px] font-medium">School logo</p>
                    <p className="text-[11px] text-muted-foreground/90">
                      Shown on report cards and sidebar. JPEG, PNG or WebP up to 5 MB.
                    </p>
                    <input
                      ref={logoInputRef}
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      onChange={onPickLogo}
                      className="mt-1 block w-full max-w-56 text-[11px] text-muted-foreground file:mr-2 file:rounded-lg file:border-0 file:bg-primary/20 file:px-2.5 file:py-1 file:text-[11px] file:font-semibold file:text-primary hover:file:bg-primary/35"
                    />
                    {logoUploading && (
                      <p className="mt-1 text-[11px] text-muted-foreground/85">Uploading logo…</p>
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
                      <Icon className="h-4 w-4 text-muted-foreground/75" />
                      <dt className="w-36 text-muted-foreground/90">{label}</dt>
                      <dd className="font-medium">{value ?? "—"}</dd>
                    </div>
                  ))}
                </dl>
              </>
            )}
          </CardContent>
        </Card>

        {/* Report Card Style */}
        <Card className="premium-card">
          <CardHeader>
            <CardTitle className="text-[15px]">Report card style</CardTitle>
            <CardDescription>Set the card style, and design the card itself</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <ReportTemplatePicker
              value={design?.theme ?? "classic"}
              onChange={handleThemeChange}
              disabled={themeBusy}
            />
            <Button variant="outline" asChild>
              <Link href="/reports/designer">
                <LayoutTemplate className="h-4 w-4" /> Design the card (blocks &amp; layout)
              </Link>
            </Button>
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
              <div className="flex items-center justify-between rounded-xl border border-border/60 px-3 py-2.5 text-[13px]">
                <span className="text-muted-foreground/90">School</span>
                <span className="font-medium">{activeSchool?.school_name}</span>
              </div>
              <div className="flex items-center justify-between rounded-xl border border-border/60 px-3 py-2.5 text-[13px]">
                <span className="text-muted-foreground/90">Role</span>
                <Badge variant="default" className="capitalize">{activeSchool?.role?.name ?? "Member"}</Badge>
              </div>
            </div>
            <div className="flex items-center gap-3 text-[11.5px] text-muted-foreground/90">
              <Mail className="h-3.5 w-3.5" /> {user?.email}
              <Phone className="h-3.5 w-3.5" /> {school?.phone ?? "—"}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Academic Sessions — admin only */}
      {canManage && (
        <Card className="premium-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-[15px]">
              <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-primary/20">
                <CalendarRange className="h-4 w-4 text-primary" />
              </span>
              Academic sessions &amp; terms
            </CardTitle>
            <CardDescription>
              Create and manage sessions and terms. Terms control when results are locked.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-5">
              {/* Sessions list + create */}
              <div className="space-y-3">
                <h3 className="text-[12px] font-semibold uppercase tracking-wide text-muted-foreground/85">Sessions</h3>
                {loadingSessions ? (
                  <Skeleton className="h-20 w-full" />
                ) : sessions.length === 0 ? (
                  <p className="text-[13px] text-muted-foreground/90">No sessions yet — create your first.</p>
                ) : (
                  <ul className="divide-y divide-border/60">
                    {sessions.map((s) => (
                      <li key={s.id} className="flex items-center justify-between py-3 text-[13px]">
                        <div>
                          <p className="font-medium">{s.name}</p>
                          <p className="text-[11px] text-muted-foreground/85">
                            {s.start_date ?? "—"} → {s.end_date ?? "—"}
                          </p>
                        </div>
                        <div className="flex items-center gap-2">
                          {/* "Current" means the session has actually been
                              activated (open), not merely created as the current
                              one — otherwise the badge claims a session is ready
                              while every score save in its terms still fails. */}
                          {s.is_current && s.status === "open" ? (
                            <Badge variant="success">Current</Badge>
                          ) : (
                            <Badge variant="outline">{s.status}</Badge>
                          )}
                          {/* Activation is what flips a session to `open`; result
                              work is blocked until it does. A session created as
                              the current one still starts `planned`, so the button
                              must key off status, not off `is_current`. */}
                          {s.status !== "open" && (
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={activateSession.isPending}
                              onClick={() => activateSession.mutate(s.id)}
                            >
                              <Power className="h-3 w-3" /> Activate
                            </Button>
                          )}
                          {/* Undo a session created by mistake. The API refuses
                              an active session or one with students enrolled. */}
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-8 w-8 p-0 text-destructive hover:text-destructive"
                            title={`Delete ${s.name}`}
                            disabled={deleteSession.isPending || activateSession.isPending}
                            onClick={() => handleDeleteSession(s.id, s.name)}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
                <div className="flex gap-2 pt-2">
                  <Input
                    placeholder="2026/2027"
                    value={sessionName}
                    onChange={(e) => { setSessionName(e.target.value); setSessionError(null); }}
                    onKeyDown={(e) => { if (e.key === "Enter" && sessionName) createSession.mutate(); }}
                  />
                  <Button
                    size="sm"
                    onClick={() => createSession.mutate()}
                    disabled={!sessionName || createSession.isPending}
                    isLoading={createSession.isPending}
                  >
                    <Plus className="h-3.5 w-3.5" />
                  </Button>
                </div>
                {sessionError && <p className="text-[12px] text-destructive">{sessionError}</p>}
              </div>

              {/* Terms list + create */}
              <div className="space-y-3">
                <h3 className="text-[12px] font-semibold uppercase tracking-wide text-muted-foreground/85">Terms</h3>
                <div className="space-y-1.5">
                  <Label className="text-[11px] text-muted-foreground/85">Session</Label>
                  <select
                    className="flex h-9 w-full rounded-xl border border-border/90 bg-background/70 px-3 text-[13px] shadow-sm transition-all md:w-72"
                    value={selectedSessionId}
                    onChange={(e) => setSelectedSessionId(e.target.value)}
                  >
                    {sessions.map((s) => (
                      <option key={s.id} value={s.id}>{s.name}{s.is_current ? " (current)" : ""}</option>
                    ))}
                  </select>
                </div>
                {termsLoading ? (
                  <Skeleton className="h-20 w-full" />
                ) : settingsTerms.length === 0 ? (
                  <p className="text-[13px] text-muted-foreground/90">No terms in this session.</p>
                ) : (
                  <div className="space-y-2">
                    {settingsTerms.map((t) => {
                      // A term is active exactly when it is open — the only state
                      // the API accepts results work in. Deriving the label from
                      // status (instead of from whichever term this browser is
                      // viewing) is what stops the first term being shown as
                      // "active" while its badge reads "planned".
                      const isOpen = t.status === "open";
                      const isActive = isOpen;
                      const isClosed = t.status === "closed";
                      const parentSession = sessions.find(
                        (s) => s.id === t.academic_session_id,
                      );
                      const sessionOpen = parentSession?.status === "open";
                      return (
                        <div
                          key={t.id}
                          className="flex items-center justify-between rounded-xl border border-border/60 bg-muted/40 px-4 py-3"
                        >
                          <div className="flex items-center gap-3">
                            <div className={`flex h-8 w-8 items-center justify-center rounded-lg ${
                              isClosed
                                ? "bg-muted text-muted-foreground"
                                : isOpen
                                  ? "bg-success/25 text-success"
                                  : "bg-primary/20 text-primary"
                            }`}>
                              {isClosed ? <Lock className="h-4 w-4" /> : <Unlock className="h-4 w-4" />}
                            </div>
                            <div>
                              <p className="text-[13px] font-semibold">
                                {t.name}
                                {isActive && <span className="ml-2 text-primary">(active)</span>}
                              </p>
                              <p className="text-[11px] text-muted-foreground/85">
                                {t.start_date ?? "—"} → {t.end_date ?? "—"}
                              </p>
                              {!isClosed && !sessionOpen && (
                                <p className="text-[11px] text-warning">
                                  Session not activated — scores can&apos;t be saved yet.
                                </p>
                              )}
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <Badge variant={isClosed ? "muted" : isActive ? "success" : "outline"}>
                              {isClosed ? "closed" : isActive ? "active" : "planned"}
                            </Badge>
                            {/* Choose the current/active term: a planned term can
                                be made the active one. Activating also opens the
                                term's session so the teacher's save path is
                                unblocked in the same click. */}
                            {!isClosed && !isOpen && (
                              <Button
                                variant="outline"
                                size="sm"
                                className="gap-1"
                                onClick={() => activateTerm.mutate(t)}
                                disabled={activateTerm.isPending || closeTerm.isPending}
                              >
                                <Power className="h-3.5 w-3.5" />
                                Set as active
                              </Button>
                            )}
                            {/* Close is reachable for every term that is not
                                already closed, so the active term can always be
                                ended (and a term created by mistake retired). */}
                            {!isClosed && (
                              <Button
                                variant="outline"
                                size="sm"
                                className="gap-1 text-warning hover:text-warning hover:border-warning/50"
                                onClick={() => handleCloseTerm(t.id, t.name)}
                                disabled={closeTerm.isPending || activateTerm.isPending}
                              >
                                <Lock className="h-3.5 w-3.5" />
                                Close term
                              </Button>
                            )}
                            {/* Undo a term created by mistake. A term with
                                results or components is refused server-side. */}
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-8 w-8 p-0 text-destructive hover:text-destructive"
                              title={`Delete ${t.name}`}
                              onClick={() => handleDeleteTerm(t.id, t.name)}
                              disabled={deleteTerm.isPending || closeTerm.isPending || activateTerm.isPending}
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* Create term form */}
                {selectedSessionId && (
                  <div className="pt-2 space-y-3">
                    <Input
                      placeholder="Term name (e.g. First Term)"
                      value={termName}
                      onChange={(e) => setTermName(e.target.value)}
                      onKeyDown={(e) => { if (e.key === "Enter" && termName && termNo > 0) createTerm.mutate(); }}
                    />
                    <Input
                      type="number"
                      placeholder="Term number (e.g. 1)"
                      value={termNo || ""}
                      onChange={(e) => setTermNo(Number(e.target.value) || 0)}
                      min="1"
                    />
                    <Button
                      size="sm"
                      onClick={() => createTerm.mutate()}
                      disabled={!termName || termNo <= 0 || createTerm.isPending}
                      isLoading={createTerm.isPending}
                      className="w-full"
                    >
                      <Plus className="h-3.5 w-3.5" /> Add term
                    </Button>
                    {termError && <p className="text-[12px] text-destructive">{termError}</p>}
                  </div>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Sign-in credentials */}
      <Card className="premium-card">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-[15px]">
            <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-primary/20">
              <KeyRound className="h-4 w-4 text-primary" />
            </span>
            Sign-in credentials
          </CardTitle>
          <CardDescription>
            Update the login used to access Clearis. Your current password is required to make any change.
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
            <Button type="submit" disabled={!cpIsValid} className="w-full" isLoading={changePasswordMutation.isPending}>
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
              <Label htmlFor="ce_current_password">Current Password</Label>
              <Input
                id="ce_current_password"
                type="password"
                {...ceRegister("current_password")}
                className={ceErrors.current_password ? "border-destructive" : undefined}
                placeholder="Enter current password"
              />
              {ceErrors.current_password && (
                <p className="text-[11px] text-destructive">{ceErrors.current_password.message}</p>
              )}
            </div>
            <Button type="submit" disabled={Object.keys(ceErrors).length > 0} className="w-full" isLoading={changeEmailMutation.isPending}>
              Change Email
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
