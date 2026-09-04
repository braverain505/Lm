"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, BookOpen, Plus, Power, Star } from "lucide-react";
import { motion } from "framer-motion";
import Link from "next/link";
import { useState } from "react";

import { api } from "@schoolos/shared";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { useActiveSchoolId, useArms, useOfferings, useSessions, useSubjects, useTerms } from "@/hooks/use-api";
import { cn } from "@/lib/utils";

const ease = [0.25, 0.46, 0.45, 0.94] as const;

export default function ClassesPage() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  const { data: sessions = [], isLoading: loadingSessions } = useSessions();
  const { data: subjects = [] } = useSubjects();

  const [sessionName, setSessionName] = useState("");
  const [armName, setArmName] = useState("");
  const [offeringsArmId, setOfferingsArmId] = useState("");
  const [subjectName, setSubjectName] = useState("");
  const [subjectCode, setSubjectCode] = useState("");
  const [termName, setTermName] = useState("");
  const [termNo, setTermNo] = useState(0);
  const manageSessionId =
    sessions.find((s) => s.is_current)?.id ?? sessions[0]?.id ?? null;
  const { data: terms = [], isLoading: loadingTerms } = useTerms(manageSessionId);

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["sessions"] });
    void queryClient.invalidateQueries({ queryKey: ["terms"] });
    void queryClient.invalidateQueries({ queryKey: ["subjects"] });
    void queryClient.invalidateQueries({ queryKey: ["arms"] });
    void queryClient.invalidateQueries({ queryKey: ["offerings"] });
  };

  const activateSession = useMutation({
    mutationFn: async (sessionId: string) => {
      if (!schoolId) throw new Error("No active school");
      return api.activateSession(schoolId, sessionId);
    },
    onSuccess: invalidate,
  });

  const activateTerm = useMutation({
    mutationFn: async (termId: string) => {
      if (!schoolId) throw new Error("No active school");
      return api.activateTerm(schoolId, termId);
    },
    onSuccess: invalidate,
  });

  const [sessionError, setSessionError] = useState<string | null>(null);
  const createSession = useMutation({
    mutationFn: async () => {
      if (!schoolId) throw new Error("No active school");
      const res = await api.schoolFetch<{ id: string }>(schoolId, "/academics/sessions", {
        method: "POST",
        body: JSON.stringify({ name: sessionName, is_current: sessions.length === 0 }),
      });
      return res;
    },
    onSuccess: () => {
      invalidate();
      setSessionName("");
      setSessionError(null);
    },
    onError: (err: Error) => {
      setSessionError(err.message || "Failed to create session. Please try again.");
    },
  });

  const createSubject = useMutation({
    mutationFn: async () => {
      if (!schoolId) throw new Error("No active school");
      return api.schoolFetch(schoolId, "/academics/subjects", {
        method: "POST",
        body: JSON.stringify({ name: subjectName, code: subjectCode }),
      });
    },
    onSuccess: () => {
      invalidate();
      setSubjectName("");
      setSubjectCode("");
    },
  });

  const createArm = useMutation({
    mutationFn: async () => {
      if (!schoolId) throw new Error("No active school");
      if (!manageSessionId) throw new Error("Create an academic session first");
      return api.schoolFetch(schoolId, "/academics/arms", {
        method: "POST",
        body: JSON.stringify({
          session_id: manageSessionId,
          name: armName,
        }),
      });
    },
    onSuccess: () => {
      invalidate();
      setArmName("");
    },
  });

  const [termError, setTermError] = useState<string | null>(null);
  const createTerm = useMutation({
    mutationFn: async () => {
      if (!schoolId) throw new Error("No active school");
      if (!manageSessionId) throw new Error("Create an academic session first");
      return api.schoolFetch(schoolId, "/academics/terms", {
        method: "POST",
        body: JSON.stringify({
          session_id: manageSessionId,
          term_no: termNo,
          name: termName,
        }),
      });
    },
    onSuccess: () => {
      invalidate();
      setTermName("");
      setTermNo(0);
      setTermError(null);
    },
    onError: (err: Error) => {
      setTermError(err.message || "Failed to create term. Please try again.");
    },
  });

  // Core subjects drive the "Best in Core Subject" award on report cards.
  const toggleCore = useMutation({
    mutationFn: async ({ subjectId, isCore }: { subjectId: string; isCore: boolean }) => {
      if (!schoolId) throw new Error("No active school");
      return api.schoolFetch(schoolId, `/academics/subjects/${subjectId}`, {
        method: "PATCH",
        body: JSON.stringify({ is_core: isCore }),
      });
    },
    onSuccess: () => invalidate(),
  });

  const addOffering = useMutation({
    mutationFn: async ({ armId, subjectId }: { armId: string; subjectId: string }) => {
      if (!schoolId) throw new Error("No active school");
      return api.schoolFetch(schoolId, "/academics/offerings", {
        method: "POST",
        body: JSON.stringify({ arm_id: armId, subject_id: subjectId }),
      });
    },
    onSuccess: invalidate,
  });

  const removeOffering = useMutation({
    mutationFn: async (offeringId: string) => {
      if (!schoolId) throw new Error("No active school");
      return api.schoolFetch(schoolId, `/academics/offerings/${offeringId}`, {
        method: "DELETE",
      });
    },
    onSuccess: invalidate,
  });

  const currentSession = sessions.find((s) => s.is_current) ?? sessions[0] ?? null;
  const { data: arms = [], isLoading: loadingArms } = useArms(currentSession?.id ?? null);
  const { data: armOfferings = [] } = useOfferings(offeringsArmId || null);
  const offeringSubjectIds = new Set(armOfferings.map((o) => o.subject_id));
  const arm = arms.find((a) => a.id === offeringsArmId);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Classes"
        description="Pick a class to view its students — enroll, move, or remove them."
      />

      {/* Class list */}
      <div className="space-y-4">
        {loadingArms || loadingSessions ? (
          <Skeleton className="h-32 w-full" />
        ) : arms.length === 0 ? (
          <Card>
            <CardContent className="py-10 text-center text-sm text-muted-foreground">
              No classes yet for {currentSession?.name ?? "the current session"}. Add a class below.
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {arms.map((arm, idx) => (
              <motion.div
                key={arm.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.35, delay: 0.04 + idx * 0.04, ease }}
              >
                <Link
                  href={`/classes/${arm.id}`}
                  className="group flex items-center justify-between rounded-xl border bg-card p-4 shadow-sm transition-all hover:-translate-y-[1px] hover:shadow-card hover:border-primary/50"
                >
                  <div className="flex min-w-0 items-center gap-3">
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-primary/10">
                      <BookOpen className="h-4 w-4 text-primary" />
                    </div>
                    <div>
                      <p className="truncate font-medium">{arm.full_name}</p>
                      <p className="text-xs text-muted-foreground/50">{currentSession?.name}</p>
                    </div>
                  </div>
                  <ArrowRight className="h-4 w-4 text-muted-foreground/50 transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
                </Link>
              </motion.div>
            ))}
          </div>
        )}
      </div>

      {/* Academic setup */}
      <div className="pt-2">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground/50">
          Academic setup
        </h2>
        <div className="grid gap-4 lg:grid-cols-3">
          {/* Sessions */}
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: 0.08, ease }}
          >
            <Card className="transition-all hover:-translate-y-[1px] hover:shadow-card">
              <CardHeader className="px-5 py-3.5">
                <CardTitle>Academic sessions</CardTitle>
              </CardHeader>
            <CardContent className="space-y-3">
              {loadingSessions ? (
                <Skeleton className="h-8 w-full" />
              ) : sessions.length === 0 ? (
                <p className="text-sm text-muted-foreground/50">No sessions yet — create your first.</p>
              ) : (
                sessions.map((s) => (
                  <div key={s.id} className="flex items-center justify-between gap-2 rounded-md border px-3 py-2 text-sm">
                    <span className="truncate font-medium">{s.name}</span>
                    <div className="flex shrink-0 items-center gap-2">
                      {s.status === "open" ? (
                        <Badge variant="success">active</Badge>
                      ) : (
                        <Badge variant="muted">inactive</Badge>
                      )}
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
                    </div>
                  </div>
                ))
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
              {sessionError && (
                <p className="text-[12px] text-destructive mt-1">{sessionError}</p>
              )}
            </CardContent>
          </Card>
          </motion.div>

          {/* Terms */}
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: 0.12, ease }}
          >
            <Card className="transition-all hover:-translate-y-[1px] hover:shadow-card">
              <CardHeader className="px-5 py-3.5">
                <CardTitle>Terms</CardTitle>
                <CardDescription className="text-xs">
                  {manageSessionId ? (
                    sessions.find((s) => s.id === manageSessionId)?.name ?? "Session"
                  ) : (
                    "No session yet"
                  )}
                </CardDescription>
              </CardHeader>
            <CardContent className="space-y-3">
              {loadingTerms ? (
                <Skeleton className="h-8 w-full" />
              ) : terms.length === 0 ? (
                <p className="text-sm text-muted-foreground/50">No terms in this session yet.</p>
              ) : (
                terms.map((t) => (
                  <div key={t.id} className="flex items-center justify-between gap-2 rounded-md border px-3 py-2 text-sm">
                    <span className="truncate font-medium">{t.name}</span>
                    <div className="flex shrink-0 items-center gap-2">
                      {t.status === "open" ? (
                        <Badge variant="success">active</Badge>
                      ) : (
                        <Badge variant="muted">inactive</Badge>
                      )}
                      {t.status !== "open" && (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={activateTerm.isPending}
                          onClick={() => activateTerm.mutate(t.id)}
                        >
                          <Power className="h-3 w-3" /> Activate
                        </Button>
                      )}
                    </div>
                  </div>
                ))
              )}
              {/* Create term form */}
              {manageSessionId ? (
                <div className="pt-4 space-y-3">
                  <Input
                    placeholder="Term name (e.g. First Term)"
                    value={termName}
                    onChange={(e) => setTermName(e.target.value)}
                  />
                  <Input
                    type="number"
                    placeholder="Term number (e.g. 1)"
                    value={termNo}
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
                  {termError && (
                    <p className="text-[12px] text-destructive">{termError}</p>
                  )}
                </div>
              ) : (
                <p className="text-xs text-muted-foreground/50">Create a session first.</p>
              )}
            </CardContent>
          </Card>
          </motion.div>

          {/* Add a class */}
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: 0.16, ease }}
          >
            <Card className="transition-all hover:-translate-y-[1px] hover:shadow-card">
              <CardHeader className="px-5 py-3.5">
                <CardTitle>Add a class</CardTitle>
                <CardDescription className="text-xs">
                  {manageSessionId
                    ? sessions.find((s) => s.id === manageSessionId)?.name ?? "Session"
                    : "Create a session first"}
                </CardDescription>
              </CardHeader>
            <CardContent className="space-y-3">
              <Input
                placeholder="Full class name (e.g. JSS 1 A)"
                value={armName}
                onChange={(e) => setArmName(e.target.value)}
                disabled={!manageSessionId}
              />
              <Button
                size="sm"
                onClick={() => createArm.mutate()}
                disabled={!armName || !manageSessionId || createArm.isPending}
                className="w-full"
              >
                <Plus className="h-3.5 w-3.5" /> Add class
              </Button>
            </CardContent>
          </Card>
          </motion.div>

          {/* Offerings */}
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: 0.08, ease }}
          >
            <Card className="transition-all hover:-translate-y-[1px] hover:shadow-card">
              <CardHeader className="px-5 py-3.5">
                <CardTitle>Class subjects</CardTitle>
                <CardDescription className="text-xs">
                  Choose a class to add or remove the subjects it offers.
                </CardDescription>
              </CardHeader>
            <CardContent className="space-y-3">
              <select
                className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
                value={offeringsArmId}
                onChange={(e) => setOfferingsArmId(e.target.value)}
              >
                <option value="">Choose a class…</option>
                {arms.map((a) => (
                  <option key={a.id} value={a.id}>{a.full_name}</option>
                ))}
              </select>
              {offeringsArmId && (
                <div className="space-y-2">
                  <p className="text-xs font-medium text-muted-foreground">
                    Offered in {arm?.full_name}
                  </p>
                  {subjects.map((s, idx) => {
                    const isOffered = offeringSubjectIds.has(s.id);
                    return (
                      <motion.div
                        key={s.id}
                        initial={{ opacity: 0, y: 4 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.3, delay: idx * 0.04, ease }}
                        className="flex items-center justify-between rounded-md border px-3 py-2 text-sm"
                      >
                        <span className="truncate font-medium">{s.name}</span>
                        <Button
                          size="sm"
                          variant={isOffered ? "outline" : "default"}
                          disabled={
                            (isOffered ? removeOffering : addOffering).isPending
                          }
                          onClick={() => {
                            if (isOffered) {
                              const offering = armOfferings.find(
                                (o) => o.subject_id === s.id,
                              );
                              if (offering) removeOffering.mutate(offering.id);
                            } else {
                              addOffering.mutate({ armId: offeringsArmId, subjectId: s.id });
                            }
                          }}
                        >
                          {isOffered ? "Remove" : "Add"}
                        </Button>
                      </motion.div>
                    );
                  })}
                </div>
              )}
              {arms.length === 0 && (
                <p className="text-xs text-muted-foreground/50">Add a class first.</p>
              )}
            </CardContent>
          </Card>
          </motion.div>

          {/* Subjects */}
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: 0.12, ease }}
          >
            <Card className="transition-all hover:-translate-y-[1px] hover:shadow-card">
              <CardHeader className="px-5 py-3.5">
                <CardTitle>Subjects</CardTitle>
              </CardHeader>
            <CardContent className="space-y-3">
              {subjects.map((s, idx) => (
                <motion.div
                  key={s.id}
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3, delay: idx * 0.04, ease }}
                  className="flex items-center justify-between gap-2 rounded-md border px-3 py-2 text-sm"
                >
                  <div className="flex min-w-0 items-center gap-2">
                    <button
                      onClick={() => toggleCore.mutate({ subjectId: s.id, isCore: !s.is_core })}
                      disabled={toggleCore.isPending}
                      title={s.is_core ? "Remove from core subjects" : "Make a core subject (Best in Subject award)"}
                      className={cn(
                        "shrink-0 transition-colors",
                        s.is_core ? "text-amber-500" : "text-muted-foreground/40 hover:text-muted-foreground",
                      )}
                    >
                      <Star className="h-4 w-4" fill={s.is_core ? "currentColor" : "none"} />
                    </button>
                    <span className="truncate font-medium">{s.name}</span>
                    {s.is_core && <Badge variant="warning">core</Badge>}
                  </div>
                  <span className="font-mono text-xs text-muted-foreground/50">{s.code}</span>
                </motion.div>
              ))}
              <div className="grid grid-cols-2 gap-2 pt-2">
                <Input placeholder="Mathematics" value={subjectName} onChange={(e) => setSubjectName(e.target.value)} />
                <Input placeholder="MTH" value={subjectCode} onChange={(e) => setSubjectCode(e.target.value)} />
              </div>
              <Button size="sm" onClick={() => createSubject.mutate()} disabled={!subjectName} className="w-full">
                <Plus className="h-3.5 w-3.5" /> Add subject
              </Button>
            </CardContent>
          </Card>
          </motion.div>
        </div>
      </div>
    </div>
  );
}