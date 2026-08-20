"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { ArrowUpRight, Plus, Search, UserPlus } from "lucide-react";
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
} from "@/hooks/use-api";

export default function StudentsPage() {
  const schoolId = useActiveSchoolId();
  const { data = [], isLoading } = useStudents();
  const queryClient = useQueryClient();

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
  const { data: sessions = [] } = useSessions();
  const currentSessionId = sessions.find((s) => s.is_current)?.id ?? sessions[0]?.id ?? null;
  const { data: arms = [] } = useArms(currentSessionId);

  // --- Promote ---------------------------------------------------------------
  const [promoteOpen, setPromoteOpen] = useState(false);
  const [promoteFrom, setPromoteFrom] = useState("");
  const [promoteTo, setPromoteTo] = useState("");
  const [armMappings, setArmMappings] = useState<Record<string, string>>({});
  const promote = usePromoteStudents();
  const [promoteResult, setPromoteResult] = useState<string | null>(null);
  const { data: fromArms = [] } = useArms(promoteFrom || null);
  const { data: toArms = [] } = useArms(promoteTo || null);

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
    },
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
    },
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
    await enrollStudent.mutateAsync({ student_id: enrollFor, arm_id: enrollArm, session_id: currentSessionId });
    setEnrollFor(null);
    setEnrollArm("");
  };

  const onPromote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!promoteFrom || !promoteTo) return;
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
  };

  const otherSessions = sessions.filter((s) => s.id !== promoteFrom);

  const onPromoteFromChange = (sessionId: string) => {
    setPromoteFrom(sessionId);
    setArmMappings({});
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Students</h1>
          <p className="text-sm text-muted-foreground">{data.length} student records</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setPromoteOpen((v) => !v)}>
            <ArrowUpRight className="h-4 w-4" /> Promote to next session
          </Button>
          <Button onClick={() => setAddOpen((v) => !v)}>
            <Plus className="h-4 w-4" /> {addOpen ? "Close" : "Add student"}
          </Button>
        </div>
      </div>

      {/* Add student */}
      {addOpen && (
        <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
          <Card className="premium-card">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <UserPlus className="h-4 w-4 text-primary" /> New student
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
                <div className="space-y-2">
                  <Label>Admission no.</Label>
                  <Input placeholder="STU-001" value={form.admission_no} onChange={(e) => setForm({ ...form, admission_no: e.target.value })} required />
                </div>
                <div className="space-y-2">
                  <Label>Photo (optional)</Label>
                  <div className="flex items-center gap-3">
                    {form.photo_url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={form.photo_url}
                        alt="Student preview"
                        className="h-14 w-14 rounded-full border object-cover"
                      />
                    ) : (
                      <div className="flex h-14 w-14 items-center justify-center rounded-full border bg-muted/40 text-muted-foreground">
                        <UserPlus className="h-5 w-5" />
                      </div>
                    )}
                    <input
                      ref={photoInputRef}
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      onChange={onPickPhoto}
                      className="block w-full text-sm text-muted-foreground file:mr-3 file:rounded-md file:border-0 file:bg-primary/10 file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-primary hover:file:bg-primary/20"
                    />
                  </div>
                  {photoUploading && <p className="text-xs text-muted-foreground">Uploading photo…</p>}
                </div>
                <div className="space-y-2">
                  <Label>First name</Label>
                  <Input placeholder="Aisha" value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} required />
                </div>
                <div className="space-y-2">
                  <Label>Last name</Label>
                  <Input placeholder="Bello" value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} required />
                </div>
                <div className="space-y-2">
                  <Label>Gender</Label>
                  <select className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm" value={form.gender} onChange={(e) => setForm({ ...form, gender: e.target.value })}>
                    <option value="male">Male</option>
                    <option value="female">Female</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <Label>State (optional)</Label>
                  <Input placeholder="Lagos" value={form.state} onChange={(e) => setForm({ ...form, state: e.target.value })} />
                </div>
                <div className="flex items-end gap-2">
                  <Button type="submit" disabled={createStudent.isPending}>
                    {createStudent.isPending ? "Saving…" : "Create"}
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
        <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
          <Card className="premium-card">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ArrowUpRight className="h-4 w-4 text-primary" /> Promote students
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="mb-4 text-sm text-muted-foreground">
                Move all actively-enrolled students from one session into the next. For each source
                class, choose the class they move to in the new session.
              </p>
              <form onSubmit={onPromote} className="space-y-4">
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label>From session</Label>
                    <select
                      className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
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
                  <div className="space-y-2">
                    <Label>To session</Label>
                    <select
                      className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
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
                  <div className="space-y-2 rounded-lg border p-3">
                    <p className="text-xs font-medium text-muted-foreground">
                      Class mappings (from {sessions.find((s) => s.id === promoteFrom)?.name})
                    </p>
                    {fromArms.map((arm) => (
                      <div key={arm.id} className="flex flex-wrap items-center gap-2 text-sm">
                        <span className="min-w-40 font-medium">{arm.full_name}</span>
                        <span className="text-muted-foreground">→</span>
                        <select
                          className="h-8 w-52 rounded-md border border-input bg-transparent px-2 text-sm"
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
                    <p className="pt-1 text-xs text-muted-foreground">
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
                  >
                    {promote.isPending ? "Promoting…" : "Promote"}
                  </Button>
                  <Button type="button" variant="ghost" onClick={() => setPromoteOpen(false)}>Cancel</Button>
                </div>
              </form>
            </CardContent>
          </Card>
        </motion.div>
      )}

      {promoteResult && (
        <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-600 dark:text-emerald-400">
          {promoteResult}
        </div>
      )}

      {/* Enroll inline panel */}
      {enrollFor && (
        <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
          <Card className="premium-card">
            <CardHeader>
              <CardTitle>Enroll {data.find((s) => s.id === enrollFor)?.full_name}</CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={onEnroll} className="flex flex-wrap items-end gap-3">
                <div className="min-w-56 space-y-2">
                  <Label>Class arm ({sessions.find((s) => s.id === currentSessionId)?.name ?? "current session"})</Label>
                  <select className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm" value={enrollArm} onChange={(e) => setEnrollArm(e.target.value)} required>
                    <option value="">Choose arm…</option>
                    {arms.map((a) => (
                      <option key={a.id} value={a.id}>{a.full_name}</option>
                    ))}
                  </select>
                </div>
                <Button type="submit" disabled={enrollStudent.isPending}>
                  {enrollStudent.isPending ? "Enrolling…" : "Enroll"}
                </Button>
                <Button type="button" variant="ghost" onClick={() => setEnrollFor(null)}>Cancel</Button>
              </form>
            </CardContent>
          </Card>
        </motion.div>
      )}

      {/* PIN inline panel */}
      {pinFor && (
        <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
          <Card className="premium-card">
            <CardHeader>
              <CardTitle>Set result-portal PIN for {data.find((s) => s.id === pinFor)?.full_name}</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="mb-4 text-sm text-muted-foreground">
                A 4–6 digit PIN lets this student view their published report cards on the public portal.
              </p>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  setPin.mutate(pinValue);
                }}
                className="flex flex-wrap items-end gap-3"
              >
                <div className="w-40 space-y-2">
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

      {/* Table */}
      <Card className="premium-card">
        <CardContent className="p-4">
          <div className="relative mb-4">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search students…"
              className="pl-9"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="pb-2 font-medium">Admission</th>
                  <th className="pb-2 font-medium">Name</th>
                  <th className="pb-2 font-medium">Gender</th>
                  <th className="pb-2 font-medium">State</th>
                  <th className="pb-2 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {isLoading ? (
                  <tr><td colSpan={5}><Skeleton className="my-2 h-6 w-full" /></td></tr>
                ) : filtered.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-8 text-center text-muted-foreground">
                      {data.length === 0 ? "No students yet. Add your first student." : "No matches."}
                    </td>
                  </tr>
                ) : (
                  filtered.map((s) => (
                    <tr key={s.id} className="border-b last:border-0 hover:bg-accent/40">
                      <td className="py-3 font-mono text-xs">{s.admission_no}</td>
                      <td className="py-3 font-medium">{s.full_name}</td>
                      <td className="py-3 capitalize">{s.gender}</td>
                      <td className="py-3">{s.state ?? "—"}</td>
                      <td className="py-3">
                        <div className="flex justify-end gap-2">
                          <Button variant="outline" size="sm" onClick={() => setPinFor(s.id)}>
                            {pinFor === s.id ? "Close" : "Portal PIN"}
                          </Button>
                          <Button variant="outline" size="sm" onClick={() => setEnrollFor(s.id)}>
                            {enrollFor === s.id ? "Close" : "Enroll"}
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}