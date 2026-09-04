"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { ArrowUpRight, MessageSquare, Plus, Search, UserPlus } from "lucide-react";
import { useMemo, useRef, useState } from "react";

import { api } from "@schoolos/shared";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useActiveSchoolId,
  useArms,
  useEnrollStudent,
  usePromoteStudents,
  useSessions,
  useStudents,
  useTerms,
  useUpdateStudent,
} from "@/hooks/use-api";
import { useToast } from "@/components/toast";

export default function StudentsPage() {
  const schoolId = useActiveSchoolId();
  const { data = [], isLoading } = useStudents();
  const queryClient = useQueryClient();
  const { toast } = useToast();

  // --- Comment status for current term ---
  const { data: sessions = [] } = useSessions();
  const currentSessionId = sessions.find((s) => s.is_current)?.id ?? sessions[0]?.id ?? null;
  const { data: terms = [] } = useTerms(currentSessionId);
  const currentTermId = terms.find((t) => t.is_current)?.id ?? terms[0]?.id ?? null;
  const { data: arms = [] } = useArms(currentSessionId);

  // Fetch report cards for all arms to build comment status map
  // We fetch each arm's cards and merge into a single map
  const [commentMap, setCommentMap] = useState<Record<string, boolean>>({});

  // Use a ref to track which arms we've already fetched
  const fetchedArmsRef = useRef<Set<string>>(new Set());

  // Fetch comment status for each arm when data loads
  // Using individual fetch calls to build the comment map
  useMemo(() => {
    if (!schoolId || !currentTermId || arms.length === 0) return;
    const armsToFetch = arms.filter((a) => !fetchedArmsRef.current.has(a.id));
    if (armsToFetch.length === 0) return;

    armsToFetch.forEach((arm) => {
      fetchedArmsRef.current.add(arm.id);
      api.fetchReportCards(schoolId, arm.id, currentTermId)
        .then((cards) => {
          setCommentMap((prev) => {
            const next = { ...prev };
            cards.forEach((card) => {
              next[card.student.student_id] = Boolean(card.comments.homeroom);
            });
            return next;
          });
        })
        .catch(() => {
          // Silently ignore — comments just won't show
        });
    });
  }, [schoolId, currentTermId, arms]);

  // --- Add student form ------------------------------------------------------
  const [addOpen, setAddOpen] = useState(false);
  const [form, setForm] = useState({ admission_no: "", first_name: "", last_name: "", gender: "male", state: "", photo_url: "" });
  const [photoUploading, setPhotoUploading] = useState(false);
  const photoInputRef = useRef<HTMLInputElement>(null);

  const onPickPhoto = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !schoolId) return;
    setPhotoUploading(true);
    try {
      const url = await api.uploadStudentPhoto(schoolId, file);
      setForm((f) => ({ ...f, photo_url: url }));
    } finally {
      setPhotoUploading(false);
      if (photoInputRef.current) photoInputRef.current.value = "";
    }
  };

  // --- Enroll ----------------------------------------------------------------
  const [enrollFor, setEnrollFor] = useState<string | null>(null);
  const [enrollArm, setEnrollArm] = useState("");
  const enrollStudent = useEnrollStudent();

  // --- Promote ---------------------------------------------------------------
  const [promoteOpen, setPromoteOpen] = useState(false);
  const [promoteFrom, setPromoteFrom] = useState("");
  const [promoteTo, setPromoteTo] = useState("");
  const [armMappings, setArmMappings] = useState<Record<string, string>>({});
  const promote = usePromoteStudents();
  const [promoteResult, setPromoteResult] = useState<string | null>(null);
  const { data: fromArms = [] } = useArms(promoteFrom || null);
  const { data: toArms = [] } = useArms(promoteTo || null);

  // --- Edit student -----------------------------------------------------------
  const [editFor, setEditFor] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({ first_name: "", last_name: "", gender: "male", state: "", photo_url: "" });
  const [editPhotoUploading, setEditPhotoUploading] = useState(false);
  const editPhotoInputRef = useRef<HTMLInputElement>(null);
  const updateStudent = useUpdateStudent();

  const openEdit = (student: typeof data[0]) => {
    setEditFor(student.id);
    setEditForm({
      first_name: student.full_name.split(" ")[0] ?? "",
      last_name: student.full_name.split(" ").slice(1).join(" ") ?? "",
      gender: student.gender,
      state: student.state ?? "",
      photo_url: student.photo_url ?? "",
    });
  };

  const onPickEditPhoto = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !schoolId) return;
    setEditPhotoUploading(true);
    try {
      const url = await api.uploadStudentPhoto(schoolId, file);
      setEditForm((f) => ({ ...f, photo_url: url }));
    } finally {
      setEditPhotoUploading(false);
      if (editPhotoInputRef.current) editPhotoInputRef.current.value = "";
    }
  };

  const saveEdit = () => {
    if (!editFor) return;
    updateStudent.mutate(
      { studentId: editFor, data: editForm },
      {
        onSuccess: () => {
          toast("Student updated successfully");
          setEditFor(null);
        },
        onError: () => toast("Failed to update student", "error"),
      },
    );
  };

  // --- Portal PIN -------------------------------------------------------------
  const [pinFor, setPinFor] = useState<string | null>(null);
  const [pinValue, setPinValue] = useState("");
  const setPin = useMutation({
    mutationFn: async (pin: string) => {
      if (!schoolId || !pinFor) throw new Error("No active school");
      await api.setStudentPin(schoolId, pinFor, pin);
    },
    onSuccess: () => {
      setPinFor(null);
      setPinValue("");
      toast("PIN set successfully");
    },
    onError: () => toast("Failed to set PIN", "error"),
  });

  const createStudent = useMutation({
    mutationFn: async (values: typeof form) => {
      if (!schoolId) throw new Error("No active school");
      await api.schoolFetch(schoolId, "/students", {
        method: "POST",
        body: JSON.stringify(values),
      });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["students"] });
      setAddOpen(false);
      setForm({ admission_no: "", first_name: "", last_name: "", gender: "male", state: "", photo_url: "" });
      toast("Student created successfully");
    },
    onError: (err: Error) => toast(err.message || "Failed to create student", "error"),
  });

  const [q, setQ] = useState("");

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return data;
    return data.filter(
      (s) =>
        s.full_name.toLowerCase().includes(needle) ||
        s.admission_no.toLowerCase().includes(needle),
    );
  }, [data, q]);

  const onEnroll = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!enrollFor || !enrollArm || !currentSessionId) return;
    try {
      await enrollStudent.mutateAsync({ student_id: enrollFor, arm_id: enrollArm, session_id: currentSessionId });
      setEnrollFor(null);
      setEnrollArm("");
      toast("Student enrolled successfully");
    } catch {
      toast("Failed to enroll student", "error");
    }
  };

  const onPromote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!promoteFrom || !promoteTo) return;
    try {
      const result = await promote.mutateAsync({
        from_session_id: promoteFrom,
        to_session_id: promoteTo,
        target_arms: fromArms
          .map((a) => ({ from_arm_id: a.id, to_arm_id: armMappings[a.id] }))
          .filter((pair) => pair.to_arm_id),
      });
      setPromoteResult(
        `Promoted ${result.promoted} student${result.promoted === 1 ? "" : "s"}` +
          (result.skipped.length > 0 ? ` · ${result.skipped.length} skipped (no target class assigned)` : ""),
      );
      setPromoteOpen(false);
      setPromoteFrom("");
      setPromoteTo("");
      setArmMappings({});
      toast(`Promoted ${result.promoted} student${result.promoted === 1 ? "" : "s"}`);
    } catch {
      toast("Failed to promote students", "error");
    }
  };

  const otherSessions = sessions.filter((s) => s.id !== promoteFrom);

  const onPromoteFromChange = (sessionId: string) => {
    setPromoteFrom(sessionId);
    setArmMappings({});
  };

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-[22px] font-bold tracking-tight text-foreground">Students</h1>
          <p className="mt-1 text-[13px] text-muted-foreground">{data.length} student records</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setPromoteOpen((v) => !v)} className="gap-1.5">
            <ArrowUpRight className="h-4 w-4" /> Promote
          </Button>
          <Button onClick={() => setAddOpen((v) => !v)} className="gap-1.5">
            <Plus className="h-4 w-4" /> {addOpen ? "Close" : "Add student"}
          </Button>
        </div>
      </div>

      {/* Add student */}
      {addOpen && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}>
          <Card className="premium-card">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-primary/10">
                  <UserPlus className="h-4 w-4 text-primary" />
                </span>
                New student
              </CardTitle>
            </CardHeader>
            <CardContent>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  createStudent.mutate(form);
                }}
                className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
              >
                <div className="space-y-1.5">
                  <Label>Admission no.</Label>
                  <Input placeholder="STU-001" value={form.admission_no} onChange={(e) => setForm({ ...form, admission_no: e.target.value })} required />
                </div>
                <div className="space-y-1.5">
                  <Label>Photo (optional)</Label>
                  <div className="flex items-center gap-3">
                    {form.photo_url ? (
                      <img src={form.photo_url} alt="Student preview" className="h-14 w-14 rounded-full border object-cover" />
                    ) : (
                      <div className="flex h-14 w-14 items-center justify-center rounded-full border border-dashed border-border bg-muted/40 text-muted-foreground/40">
                        <UserPlus className="h-5 w-5" />
                      </div>
                    )}
                    <input
                      ref={photoInputRef}
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      onChange={onPickPhoto}
                      className="block w-full text-[12px] text-muted-foreground file:mr-3 file:rounded-lg file:border-0 file:bg-primary/10 file:px-3 file:py-1.5 file:text-[11px] file:font-semibold file:text-primary hover:file:bg-primary/20"
                    />
                  </div>
                  {photoUploading && <p className="text-[11px] text-muted-foreground/60">Uploading photo…</p>}
                </div>
                <div className="space-y-1.5">
                  <Label>First name</Label>
                  <Input placeholder="Aisha" value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} required />
                </div>
                <div className="space-y-1.5">
                  <Label>Last name</Label>
                  <Input placeholder="Bello" value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} required />
                </div>
                <div className="space-y-1.5">
                  <Label>Gender</Label>
                  <select className="flex h-9 w-full rounded-xl border border-border/80 bg-background/50 px-3 text-[13px] shadow-sm transition-all" value={form.gender} onChange={(e) => setForm({ ...form, gender: e.target.value })}>
                    <option value="male">Male</option>
                    <option value="female">Female</option>
                  </select>
                </div>
                <div className="space-y-1.5">
                  <Label>State (optional)</Label>
                  <Input placeholder="Lagos" value={form.state} onChange={(e) => setForm({ ...form, state: e.target.value })} />
                </div>
                <div className="flex items-end gap-2">
                  <Button type="submit" disabled={createStudent.isPending} isLoading={createStudent.isPending}>
                    Create
                  </Button>
                  <Button type="button" variant="ghost" onClick={() => setAddOpen(false)}>Cancel</Button>
                </div>
              </form>
            </CardContent>
          </Card>
        </motion.div>
      )}

      {/* Promote */}
      {promoteOpen && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}>
          <Card className="premium-card">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-emerald-500/10">
                  <ArrowUpRight className="h-4 w-4 text-emerald-700" />
                </span>
                Promote students
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="mb-4 text-[13px] text-muted-foreground">
                Move all actively-enrolled students from one session into the next.
              </p>
              <form onSubmit={onPromote} className="space-y-4">
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-1.5">
                    <Label>From session</Label>
                    <select
                      className="flex h-9 w-full rounded-xl border border-border/80 bg-background/50 px-3 text-[13px] shadow-sm"
                      value={promoteFrom}
                      onChange={(e) => onPromoteFromChange(e.target.value)}
                      required
                    >
                      <option value="">Choose session…</option>
                      {sessions.map((s) => (
                        <option key={s.id} value={s.id}>{s.name}</option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-1.5">
                    <Label>To session</Label>
                    <select
                      className="flex h-9 w-full rounded-xl border border-border/80 bg-background/50 px-3 text-[13px] shadow-sm"
                      value={promoteTo}
                      onChange={(e) => {
                        setPromoteTo(e.target.value);
                        setArmMappings({});
                      }}
                      disabled={!promoteFrom}
                      required
                    >
                      <option value="">Choose session…</option>
                      {otherSessions.map((s) => (
                        <option key={s.id} value={s.id}>{s.name}</option>
                      ))}
                    </select>
                  </div>
                </div>

                {promoteFrom && promoteTo && fromArms.length > 0 && (
                  <div className="space-y-2 rounded-xl border border-border/40 bg-muted/20 p-4">
                    <p className="text-[11px] font-semibold text-muted-foreground/70">
                      Class mappings (from {sessions.find((s) => s.id === promoteFrom)?.name})
                    </p>
                    {fromArms.map((arm) => (
                      <div key={arm.id} className="flex flex-wrap items-center gap-2 text-[13px]">
                        <span className="min-w-40 font-medium">{arm.full_name}</span>
                        <span className="text-muted-foreground/50">→</span>
                        <select
                          className="flex h-8 w-52 rounded-lg border border-border/80 bg-background/50 px-2 text-[13px]"
                          value={armMappings[arm.id] ?? ""}
                          onChange={(e) =>
                            setArmMappings((m) => ({ ...m, [arm.id]: e.target.value }))
                          }
                        >
                          <option value="">Choose target class…</option>
                          {toArms.map((a) => (
                            <option key={a.id} value={a.id}>{a.full_name}</option>
                          ))}
                        </select>
                      </div>
                    ))}
                    <p className="pt-1 text-[11px] text-muted-foreground/60">
                      Classes without a target are skipped.
                    </p>
                  </div>
                )}

                <div className="flex items-end gap-2">
                  <Button
                    type="submit"
                    disabled={
                      promote.isPending ||
                      !promoteFrom ||
                      !promoteTo ||
                      !fromArms.some((a) => armMappings[a.id])
                    }
                    isLoading={promote.isPending}
                  >
                    Promote
                  </Button>
                  <Button type="button" variant="ghost" onClick={() => setPromoteOpen(false)}>Cancel</Button>
                </div>
              </form>
            </CardContent>
          </Card>
        </motion.div>
      )}

      {promoteResult && (
        <div className="rounded-xl border border-success/20 bg-success/5 px-4 py-3 text-[13px] text-success">
          {promoteResult}
        </div>
      )}

      {/* Enroll inline panel */}
      {enrollFor && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}>
          <Card className="premium-card">
            <CardHeader>
              <CardTitle>Enroll {data.find((s) => s.id === enrollFor)?.full_name}</CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={onEnroll} className="flex flex-wrap items-end gap-3">
                <div className="min-w-56 space-y-1.5">
                  <Label>Class arm ({sessions.find((s) => s.id === currentSessionId)?.name ?? "current session"})</Label>
                  <select className="flex h-9 w-full rounded-xl border border-border/80 bg-background/50 px-3 text-[13px] shadow-sm" value={enrollArm} onChange={(e) => setEnrollArm(e.target.value)} required>
                    <option value="">Choose arm…</option>
                    {arms.map((a) => (
                      <option key={a.id} value={a.id}>{a.full_name}</option>
                    ))}
                  </select>
                </div>
                <Button type="submit" disabled={enrollStudent.isPending} isLoading={enrollStudent.isPending}>
                  Enroll
                </Button>
                <Button type="button" variant="ghost" onClick={() => setEnrollFor(null)}>Cancel</Button>
              </form>
            </CardContent>
          </Card>
        </motion.div>
      )}

      {/* PIN inline panel */}
      {pinFor && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}>
          <Card className="premium-card">
            <CardHeader>
              <CardTitle>Set result-portal PIN for {data.find((s) => s.id === pinFor)?.full_name}</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="mb-4 text-[13px] text-muted-foreground">
                A 4–6 digit PIN lets this student view their published report cards on the public portal.
              </p>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  setPin.mutate(pinValue);
                }}
                className="flex flex-wrap items-end gap-3"
              >
                <div className="w-40 space-y-1.5">
                  <Label>PIN</Label>
                  <Input
                    inputMode="numeric"
                    maxLength={6}
                    placeholder="••••"
                    value={pinValue}
                    onChange={(e) => setPinValue(e.target.value.replace(/\D/g, ""))}
                    required
                  />
                </div>
                <Button type="submit" disabled={setPin.isPending || pinValue.length < 4}>
                  {setPin.isPending ? "Saving…" : "Set PIN"}
                </Button>
                <Button type="button" variant="ghost" onClick={() => setPinFor(null)}>Cancel</Button>
              </form>
            </CardContent>
          </Card>
        </motion.div>
      )}

      {/* Edit student panel */}
      {editFor && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}>
          <Card className="premium-card">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-primary/10">
                  <UserPlus className="h-4 w-4 text-primary" />
                </span>
                Edit student — {data.find((s) => s.id === editFor)?.full_name}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <div className="space-y-1.5">
                  <Label>First name</Label>
                  <Input
                    value={editForm.first_name}
                    onChange={(e) => setEditForm({ ...editForm, first_name: e.target.value })}
                    required
                  />
                </div>
                <div className="space-y-1.5">
                  <Label>Last name</Label>
                  <Input
                    value={editForm.last_name}
                    onChange={(e) => setEditForm({ ...editForm, last_name: e.target.value })}
                    required
                  />
                </div>
                <div className="space-y-1.5">
                  <Label>Gender</Label>
                  <select
                    className="flex h-9 w-full rounded-xl border border-border/80 bg-background/50 px-3 text-[13px] shadow-sm transition-all"
                    value={editForm.gender}
                    onChange={(e) => setEditForm({ ...editForm, gender: e.target.value })}
                  >
                    <option value="male">Male</option>
                    <option value="female">Female</option>
                  </select>
                </div>
                <div className="space-y-1.5">
                  <Label>State</Label>
                  <Input
                    value={editForm.state}
                    onChange={(e) => setEditForm({ ...editForm, state: e.target.value })}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label>Photo</Label>
                  <div className="flex items-center gap-3">
                    {editForm.photo_url ? (
                      <img
                        src={editForm.photo_url.startsWith("http") ? editForm.photo_url : `${(process.env.NEXT_PUBLIC_API_URL ?? "https://schoolos-api-5066.onrender.com/api").replace(/\/api$/, "")}${editForm.photo_url}`}
                        alt="Student preview"
                        className="h-14 w-14 rounded-full border object-cover"
                      />
                    ) : (
                      <div className="flex h-14 w-14 items-center justify-center rounded-full border border-dashed border-border bg-muted/40 text-muted-foreground/40">
                        <UserPlus className="h-5 w-5" />
                      </div>
                    )}
                    <input
                      ref={editPhotoInputRef}
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      onChange={onPickEditPhoto}
                      className="block w-full text-[12px] text-muted-foreground file:mr-3 file:rounded-lg file:border-0 file:bg-primary/10 file:px-3 file:py-1.5 file:text-[11px] file:font-semibold file:text-primary hover:file:bg-primary/20"
                    />
                  </div>
                  {editPhotoUploading && <p className="text-[11px] text-muted-foreground/60">Uploading photo…</p>}
                </div>
                <div className="flex items-end gap-2">
                  <Button onClick={saveEdit} disabled={updateStudent.isPending} isLoading={updateStudent.isPending}>
                    Save changes
                  </Button>
                  <Button variant="ghost" onClick={() => setEditFor(null)}>Cancel</Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      )}

      {/* Table */}
      <Card className="premium-card">
        <CardContent className="p-5">
          <div className="relative mb-4">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground/50" />
            <Input
              placeholder="Search students by name or admission number…"
              className="pl-9"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="border-b border-border/40 text-left text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground/60">
                  <th className="pb-2.5 font-semibold">Admission</th>
                  <th className="pb-2.5 font-semibold">Name</th>
                  <th className="pb-2.5 font-semibold">Gender</th>
                  <th className="pb-2.5 font-semibold">State</th>
                  <th className="pb-2.5 font-semibold">Comments</th>
                  <th className="pb-2.5 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {isLoading ? (
                  <tr><td colSpan={6}><Skeleton className="my-2 h-6 w-full" /></td></tr>
                ) : filtered.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-12 text-center">
                      <div className="flex flex-col items-center gap-2">
                        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-muted/60">
                          <UserPlus className="h-5 w-5 text-muted-foreground/40" />
                        </div>
                        <p className="text-[13px] font-medium text-muted-foreground/70">
                          {data.length === 0 ? "No students yet. Add your first student." : "No matches found."}
                        </p>
                      </div>
                    </td>
                  </tr>
                ) : (
                  filtered.map((s) => {
                    const hasComment = commentMap[s.id];
                    return (
                      <tr key={s.id} className="border-b border-border/30 last:border-0 transition-colors hover:bg-accent/40">
                        <td className="py-3 font-mono text-[11px] text-muted-foreground">{s.admission_no}</td>
                        <td className="py-3 font-medium">{s.full_name}</td>
                        <td className="py-3 capitalize text-muted-foreground">{s.gender}</td>
                        <td className="py-3 text-muted-foreground">{s.state ?? "—"}</td>
                        <td className="py-3">
                          {hasComment === true ? (
                            <Badge variant="success" className="gap-1 text-[10px]">
                              <MessageSquare className="h-3 w-3" /> Entered
                            </Badge>
                          ) : hasComment === false ? (
                            <Badge variant="warning" className="text-[10px]">Pending</Badge>
                          ) : (
                            <span className="text-[11px] text-muted-foreground/40">—</span>
                          )}
                        </td>
                        <td className="py-3">
                          <div className="flex justify-end gap-2">
                            <Button variant="outline" size="sm" onClick={() => openEdit(s)}>
                              Edit
                            </Button>
                            <Button variant="outline" size="sm" onClick={() => setPinFor(s.id)}>
                              PIN
                            </Button>
                            <Button variant="outline" size="sm" onClick={() => setEnrollFor(s.id)}>
                              Enroll
                            </Button>
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
