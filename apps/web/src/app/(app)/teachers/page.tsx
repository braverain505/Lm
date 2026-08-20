"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Mail, Plus, Trash2, X } from "lucide-react";
import { useState } from "react";
import { z } from "zod";

import { api, type Staff } from "@schoolos/shared";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useActiveSchoolId,
  useArms,
  useCreateAssignment,
  useCreateStaff,
  useCreateStaffAccount,
  useDeleteAssignment,
  useDeleteStaff,
  useRoles,
  useSessions,
  useStaff,
  useStaffAssignments,
  useSubjects,
  useUpdateStaffAccount,
} from "@/hooks/use-api";

function ErrorNote({ message }: { message?: string | null }) {
  if (!message) return null;
  return <p className="text-xs text-destructive">{message}</p>;
}

const accountCreateSchema = z.object({
  email: z.string().email("Enter a valid email address"),
  password: z.string().min(8, "Password must be at least 8 characters"),
  role_id: z.string().uuid("Choose a role"),
});

const accountUpdateSchema = z.object({
  email: z.string().email("Enter a valid email address"),
  password: z
    .string()
    .optional()
    .refine((v) => !v || v.length >= 8, "Password must be at least 8 characters"),
  role_id: z.string().uuid("Choose a role"),
});

const assignmentSchema = z.object({
  arm_id: z.string().uuid("Choose a class arm"),
  subject_id: z.string().uuid("Choose a subject"),
});

export default function TeachersPage() {
  const schoolId = useActiveSchoolId();
  const queryClient = useQueryClient();
  const { data: staff = [], isLoading } = useStaff();

  // --- Add teacher form ------------------------------------------------------
  const [addOpen, setAddOpen] = useState(false);
  const [form, setForm] = useState({
    staff_no: "",
    full_name: "",
    membership_type: "teaching",
    gender: "",
    phone: "",
    email: "",
  });
  const createStaff = useCreateStaff();

  // --- Account (create or change login, per-row expansion) --------------------
  const [accountFor, setAccountFor] = useState<string | null>(null);
  const [accountMode, setAccountMode] = useState<"create" | "change">("create");
  const [accountEmail, setAccountEmail] = useState("");
  const [accountPassword, setAccountPassword] = useState("");
  const [accountRole, setAccountRole] = useState("");
  const [accountErrors, setAccountErrors] = useState<{ email?: string; password?: string; role?: string }>({});
  const createAccount = useCreateStaffAccount();
  const updateAccount = useUpdateStaffAccount();
  const { data: roles = [] } = useRoles();

  // --- Assignment (per-row expansion) -----------------------------------------
  const [assignFor, setAssignFor] = useState<string | null>(null);
  const [assignArm, setAssignArm] = useState("");
  const [assignSubject, setAssignSubject] = useState("");
  const [assignErrors, setAssignErrors] = useState<{ arm?: string; subject?: string }>({});
  const createAssignment = useCreateAssignment();
  const deleteAssignment = useDeleteAssignment();
  const deleteStaff = useDeleteStaff();

  const { data: sessions = [] } = useSessions();
  const currentSessionId = sessions.find((s) => s.is_current)?.id ?? sessions[0]?.id ?? null;
  const { data: arms = [] } = useArms(currentSessionId);
  const { data: subjects = [] } = useSubjects();

  const resetForm = () => {
    setForm({ staff_no: "", full_name: "", membership_type: "teaching", gender: "", phone: "", email: "" });
    setAddOpen(false);
  };

  const openAccountForm = (s: Staff) => {
    setAccountFor(s.id);
    setAccountMode(s.has_account ? "change" : "create");
    setAccountEmail(s.account_email ?? "");
    setAccountRole(s.account_role_id ?? "");
    setAccountPassword("");
    setAccountErrors({});
    setAssignFor(null);
  };

  const closeAccountForm = () => {
    setAccountFor(null);
    setAccountEmail("");
    setAccountPassword("");
    setAccountRole("");
    setAccountErrors({});
  };

  const onAddTeacher = async (e: React.FormEvent) => {
    e.preventDefault();
    await createStaff.mutateAsync({
      staff_no: form.staff_no,
      full_name: form.full_name,
      membership_type: form.membership_type,
      gender: form.gender || null,
      phone: form.phone || null,
      email: form.email || null,
    });
    resetForm();
  };

  const onSubmitAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!accountFor) return;
    if (accountMode === "change") {
      const parsed = accountUpdateSchema.safeParse({
        email: accountEmail,
        password: accountPassword,
        role_id: accountRole,
      });
      if (!parsed.success) {
        const fe = parsed.error.flatten().fieldErrors;
        setAccountErrors({
          email: fe.email?.[0],
          password: fe.password?.[0],
          role: fe.role_id?.[0],
        });
        return;
      }
      setAccountErrors({});
      await updateAccount.mutateAsync({
        staffId: accountFor,
        input: {
          email: accountEmail,
          ...(accountPassword ? { password: accountPassword } : {}),
          role_id: accountRole,
        },
      });
    } else {
      const parsed = accountCreateSchema.safeParse({
        email: accountEmail,
        password: accountPassword,
        role_id: accountRole,
      });
      if (!parsed.success) {
        const fe = parsed.error.flatten().fieldErrors;
        setAccountErrors({
          email: fe.email?.[0],
          password: fe.password?.[0],
          role: fe.role_id?.[0],
        });
        return;
      }
      setAccountErrors({});
      await createAccount.mutateAsync({
        staffId: accountFor,
        input: { email: accountEmail, password: accountPassword, role_id: accountRole },
      });
    }
    closeAccountForm();
  };

  const onAssign = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!assignFor) return;
    const parsed = assignmentSchema.safeParse({ arm_id: assignArm, subject_id: assignSubject });
    if (!parsed.success) {
      const fe = parsed.error.flatten().fieldErrors;
      setAssignErrors({ arm: fe.arm_id?.[0], subject: fe.subject_id?.[0] });
      return;
    }
    setAssignErrors({});
    await createAssignment.mutateAsync({
      arm_id: assignArm,
      subject_id: assignSubject,
      teacher_id: assignFor,
    });
    setAssignSubject("");
  };

  const onUnassign = async (assignmentId: string) => {
    await deleteAssignment.mutateAsync(assignmentId);
    queryClient.invalidateQueries({ queryKey: ["staff-assignments", schoolId, assignFor] });
  };

  const onDeleteStaff = async (s: Staff) => {
    const ok = window.confirm(
      `Delete ${s.full_name}? This removes them from the staff list, unassigns their subjects and revokes their login.`,
    );
    if (!ok) return;
    await deleteStaff.mutateAsync(s.id);
    if (accountFor === s.id) closeAccountForm();
    if (assignFor === s.id) setAssignFor(null);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Staff &amp; Teachers</h1>
          <p className="text-sm text-muted-foreground">
            {staff.length} staff records · add teachers, create their logins, assign classes &amp; subjects
          </p>
        </div>
        <Button onClick={() => setAddOpen((v) => !v)}>
          <Plus className="h-4 w-4" /> {addOpen ? "Close" : "Add teacher"}
        </Button>
      </div>

      {/* Add teacher form */}
      {addOpen && (
        <Card>
          <CardHeader>
            <CardTitle>New staff member</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={onAddTeacher} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <div className="space-y-2">
                <Label>Staff no.</Label>
                <Input
                  placeholder="TCH-001"
                  value={form.staff_no}
                  onChange={(e) => setForm({ ...form, staff_no: e.target.value })}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label>Full name</Label>
                <Input
                  placeholder="Adeola Johnson"
                  value={form.full_name}
                  onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label>Type</Label>
                <select
                  className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
                  value={form.membership_type}
                  onChange={(e) => setForm({ ...form, membership_type: e.target.value })}
                >
                  <option value="teaching">Teaching</option>
                  <option value="non-teaching">Non-teaching</option>
                </select>
              </div>
              <div className="space-y-2">
                <Label>Gender</Label>
                <select
                  className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
                  value={form.gender}
                  onChange={(e) => setForm({ ...form, gender: e.target.value })}
                >
                  <option value="">—</option>
                  <option value="male">Male</option>
                  <option value="female">Female</option>
                </select>
              </div>
              <div className="space-y-2">
                <Label>Phone (optional)</Label>
                <Input
                  placeholder="0803…"
                  value={form.phone}
                  onChange={(e) => setForm({ ...form, phone: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label>Email (optional)</Label>
                <Input
                  type="email"
                  placeholder="adeola@school.edu"
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                />
              </div>
              <div className="flex items-end gap-2">
                <Button type="submit" disabled={createStaff.isPending}>
                  {createStaff.isPending ? "Saving…" : "Create"}
                </Button>
                <Button type="button" variant="ghost" onClick={resetForm}>
                  Cancel
                </Button>
              </div>
              <ErrorNote message={createStaff.error?.message} />
            </form>
          </CardContent>
        </Card>
      )}

      {/* Staff table */}
      <Card>
        <CardContent className="overflow-x-auto p-4">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th className="pb-2 font-medium">Staff no.</th>
                <th className="pb-2 font-medium">Name</th>
                <th className="pb-2 font-medium">Type</th>
                <th className="pb-2 font-medium">Status</th>
                <th className="pb-2 font-medium">Login</th>
                <th className="pb-2 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={6}><Skeleton className="my-2 h-6 w-full" /></td>
                </tr>
              ) : staff.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-muted-foreground">
                    No staff yet. Use “Add teacher” to create your first staff record.
                  </td>
                </tr>
              ) : (
                staff.map((s) => (
                  <TeacherRow
                    key={s.id}
                    staff={s}
                    accountFor={accountFor}
                    openAccountForm={openAccountForm}
                    closeAccountForm={closeAccountForm}
                    accountMode={accountMode}
                    accountEmail={accountEmail}
                    setAccountEmail={setAccountEmail}
                    accountPassword={accountPassword}
                    setAccountPassword={setAccountPassword}
                    accountRole={accountRole}
                    setAccountRole={setAccountRole}
                    accountErrors={accountErrors}
                    setAccountErrors={setAccountErrors}
                    roles={roles}
                    onSubmitAccount={onSubmitAccount}
                    accountError={createAccount.error?.message ?? updateAccount.error?.message}
                    accountPending={createAccount.isPending || updateAccount.isPending}
                    assignFor={assignFor}
                    setAssignFor={setAssignFor}
                    assignArm={assignArm}
                    setAssignArm={setAssignArm}
                    assignSubject={assignSubject}
                    setAssignSubject={setAssignSubject}
                    assignErrors={assignErrors}
                    setAssignErrors={setAssignErrors}
                    arms={arms}
                    subjects={subjects}
                    onAssign={onAssign}
                    assignError={createAssignment.error?.message}
                    assignPending={createAssignment.isPending}
                    onUnassign={onUnassign}
                    onDeleteStaff={onDeleteStaff}
                    deletePending={deleteStaff.isPending}
                  />
                ))
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}

interface TeacherRowProps {
  staff: Staff;
  accountFor: string | null;
  openAccountForm: (s: Staff) => void;
  closeAccountForm: () => void;
  accountMode: "create" | "change";
  accountEmail: string;
  setAccountEmail: (v: string) => void;
  accountPassword: string;
  setAccountPassword: (v: string) => void;
  accountRole: string;
  setAccountRole: (v: string) => void;
  accountErrors: { email?: string; password?: string; role?: string };
  setAccountErrors: (e: { email?: string; password?: string; role?: string }) => void;
  roles: { id: string; code: string; name: string }[];
  onSubmitAccount: (e: React.FormEvent) => void;
  accountError?: string | null;
  accountPending: boolean;
  assignFor: string | null;
  setAssignFor: (id: string | null) => void;
  assignArm: string;
  setAssignArm: (v: string) => void;
  assignSubject: string;
  setAssignSubject: (v: string) => void;
  assignErrors: { arm?: string; subject?: string };
  setAssignErrors: (e: { arm?: string; subject?: string }) => void;
  arms: { id: string; full_name: string }[];
  subjects: { id: string; name: string }[];
  onAssign: (e: React.FormEvent) => void;
  assignError?: string | null;
  assignPending: boolean;
  onUnassign: (assignmentId: string) => void;
  onDeleteStaff: (s: Staff) => void;
  deletePending: boolean;
}

function TeacherRow(props: TeacherRowProps) {
  const {
    staff,
    accountFor, openAccountForm, closeAccountForm, accountMode,
    accountEmail, setAccountEmail, accountPassword, setAccountPassword, accountRole, setAccountRole,
    accountErrors, setAccountErrors,
    roles, onSubmitAccount, accountError, accountPending,
    assignFor, setAssignFor, assignArm, setAssignArm, assignSubject, setAssignSubject,
    assignErrors, setAssignErrors,
    arms, subjects, onAssign, assignError, assignPending, onUnassign,
    onDeleteStaff, deletePending,
  } = props;

  const staffId = staff.id;
  const { data: assignments = [] } = useStaffAssignments(staffId, assignFor === staffId);

  const showAccount = accountFor === staffId;
  const showAssign = assignFor === staffId;

  return (
    <>
      <tr className="border-b last:border-0 hover:bg-accent/40">
        <td className="py-2.5 font-mono text-xs">{staff.staff_no}</td>
        <td className="py-2.5 font-medium">{staff.full_name}</td>
        <td className="py-2.5 capitalize">{staff.membership_type.replace("_", " ")}</td>
        <td className="py-2.5">
          <Badge variant={staff.employment_status === "active" ? "default" : "muted"}>
            {staff.employment_status}
          </Badge>
        </td>
        <td className="py-2.5">
          {staff.has_account ? (
            <Badge variant="outline" className="gap-1.5">
              <Mail className="h-3 w-3 text-muted-foreground" />
              <span className="max-w-[180px] truncate">{staff.account_email ?? "Has login"}</span>
            </Badge>
          ) : (
            <Badge variant="muted">No login</Badge>
          )}
        </td>
        <td className="py-2.5">
          <div className="flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => { setAssignFor(showAssign ? null : staffId); closeAccountForm(); }}>
              {showAssign ? "Close" : "Assign subjects"}
            </Button>
            <Button
              variant={staff.has_account ? "outline" : "default"}
              size="sm"
              onClick={() => openAccountForm(staff)}
            >
              <KeyRound className="h-3.5 w-3.5" />
              {showAccount ? "Close" : staff.has_account ? "Change login" : "Create login"}
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="text-destructive hover:text-destructive"
              onClick={() => onDeleteStaff(staff)}
              disabled={deletePending}
              aria-label="Delete staff member"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </div>
        </td>
      </tr>

      {showAccount && (
        <tr>
          <td colSpan={6} className="border-b bg-muted/30 px-4 py-4">
            <form onSubmit={onSubmitAccount} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <div className="space-y-2">
                <Label>Email (login)</Label>
                <Input
                  type="email"
                  placeholder="teacher@school.edu"
                  value={accountEmail}
                  onChange={(e) => { setAccountEmail(e.target.value); setAccountErrors({}); }}
                  required
                />
                {accountErrors.email && <p className="text-xs text-destructive">{accountErrors.email}</p>}
              </div>
              <div className="space-y-2">
                <Label>Password {accountMode === "change" && "(blank = keep)"}</Label>
                <Input
                  type="password"
                  placeholder={accountMode === "change" ? "Leave blank to keep current" : "••••••••"}
                  value={accountPassword}
                  onChange={(e) => { setAccountPassword(e.target.value); setAccountErrors({}); }}
                  required={accountMode === "create"}
                  minLength={8}
                />
                {accountErrors.password && <p className="text-xs text-destructive">{accountErrors.password}</p>}
              </div>
              <div className="space-y-2">
                <Label>Role</Label>
                <select
                  className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
                  value={accountRole}
                  onChange={(e) => { setAccountRole(e.target.value); setAccountErrors({}); }}
                  required
                >
                  <option value="">Choose role…</option>
                  {roles.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.name}
                    </option>
                  ))}
                </select>
                {accountErrors.role && <p className="text-xs text-destructive">{accountErrors.role}</p>}
              </div>
              <div className="flex items-end gap-2">
                <Button type="submit" disabled={accountPending}>
                  {accountPending ? "Saving…" : accountMode === "change" ? "Save changes" : "Create login"}
                </Button>
                <Button type="button" variant="ghost" size="sm" onClick={closeAccountForm}>
                  <X className="h-4 w-4" />
                </Button>
              </div>
              <ErrorNote message={accountError} />
            </form>
          </td>
        </tr>
      )}

      {showAssign && (
        <tr>
          <td colSpan={6} className="border-b bg-muted/30 px-4 py-4">
            <div className="space-y-4">
              <form onSubmit={onAssign} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <div className="space-y-2">
                  <Label>Class arm</Label>
                  <select
                    className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
                    value={assignArm}
                    onChange={(e) => { setAssignArm(e.target.value); setAssignErrors({}); }}
                    required
                  >
                    <option value="">Choose arm…</option>
                    {arms.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.full_name}
                      </option>
                    ))}
                  </select>
                  {assignErrors.arm && <p className="text-xs text-destructive">{assignErrors.arm}</p>}
                </div>
                <div className="space-y-2">
                  <Label>Subject</Label>
                  <select
                    className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
                    value={assignSubject}
                    onChange={(e) => { setAssignSubject(e.target.value); setAssignErrors({}); }}
                    required
                  >
                    <option value="">Choose subject…</option>
                    {subjects.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name}
                      </option>
                    ))}
                  </select>
                  {assignErrors.subject && <p className="text-xs text-destructive">{assignErrors.subject}</p>}
                </div>
                <div className="flex items-end">
                  <Button type="submit" disabled={assignPending}>
                    {assignPending ? "Assigning…" : "Assign"}
                  </Button>
                </div>
                <ErrorNote message={assignError} />
              </form>

              <div>
                <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Currently teaching
                </p>
                {assignments.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No subjects assigned yet.</p>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {assignments.map((a) => (
                      <span
                        key={a.assignment_id}
                        className="inline-flex items-center gap-2 rounded-md border bg-background px-2.5 py-1 text-sm"
                      >
                        {a.arm_name} · {a.subject_name}
                        <button
                          onClick={() => onUnassign(a.assignment_id)}
                          className="text-muted-foreground hover:text-destructive"
                          aria-label="Remove assignment"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}