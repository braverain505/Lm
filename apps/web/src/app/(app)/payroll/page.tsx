"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { motion } from "framer-motion";
import { Plus } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useAssignStaffSalary,
  useCreatePayRun,
  useCreateSalaryStructure,
  useMarkPayRunPaid,
  usePayRun,
  usePayRuns,
  useSalaryStructures,
  useStaff,
  useStaffSalaries,
  useToggleSalaryStructure,
  useUpdateSalaryStructure,
} from "@/hooks/use-api";

const structureSchema = z.object({
  name: z.string().min(1, "Name required"),
  description: z.string().optional(),
  basic_salary: z.coerce.number().positive("Basic salary must be > 0"),
  tax_percent: z.coerce.number().min(0).max(100).default(0),
});
type StructureForm = z.infer<typeof structureSchema>;

const assignSchema = z.object({
  staff_id: z.string().min(1, "Choose a staff member"),
  structure_id: z.string().min(1, "Choose a structure"),
});
type AssignForm = z.infer<typeof assignSchema>;

const runSchema = z.object({
  month: z.string().regex(/^\d{4}-\d{2}$/, "Format: YYYY-MM"),
});
type RunForm = z.infer<typeof runSchema>;

const currency = (v: number) => `₦${v.toLocaleString(undefined, { minimumFractionDigits: 2 })}`;

export default function PayrollPage() {
  const { data: structures = [], isLoading: loadingStructures } = useSalaryStructures();
  const { data: staff = [] } = useStaff();
  const { data: assignments = [] } = useStaffSalaries();
  const { data: runs = [] } = usePayRuns();
  const [showStructureForm, setShowStructureForm] = useState(false);
  const [editingStructure, setEditingStructure] = useState<string | null>(null);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);

  const createStructure = useCreateSalaryStructure();
  const updateStructure = useUpdateSalaryStructure();
  const toggleStructure = useToggleSalaryStructure();
  const assignSalary = useAssignStaffSalary();
  const createRun = useCreatePayRun();
  const markPaid = useMarkPayRunPaid();

  const activeRun = runs.find((r) => r.id === activeRunId) ?? runs[0] ?? null;
  const { data: activeRunDetail } = usePayRun(activeRun?.id ?? null);

  const {
    register: regStructure,
    handleSubmit: submitStructure,
    reset: resetStructure,
    formState: { errors: structureErrors, isSubmitting: structureSubmitting },
  } = useForm<StructureForm>({ resolver: zodResolver(structureSchema), defaultValues: { tax_percent: 0 } });

  const {
    register: regAssign,
    handleSubmit: submitAssign,
    reset: resetAssign,
    formState: { errors: assignErrors, isSubmitting: assignSubmitting },
  } = useForm<AssignForm>({ resolver: zodResolver(assignSchema) });

  const {
    register: regRun,
    handleSubmit: submitRun,
    reset: resetRun,
    formState: { errors: runErrors, isSubmitting: runSubmitting },
  } = useForm<RunForm>({ resolver: zodResolver(runSchema) });

  const assignMap = new Map(assignments.map((a) => [a.staff_id, a]));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Payroll</h1>
          <p className="text-sm text-muted-foreground">
            Salary structures, staff pay assignments, and pay runs for {staff.length} staff.
          </p>
        </div>
        <Button onClick={() => { setEditingStructure(null); setShowStructureForm((v) => !v); }}>
          <Plus className="h-4 w-4" /> Add structure
        </Button>
      </div>

      {/* Salary structures */}
      <Card>
        <CardHeader>
          <CardTitle>Salary structures</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {showStructureForm && (
            <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
              <form
                onSubmit={submitStructure((v) => {
                  const editing = structures.find((s) => s.id === editingStructure);
                  const payload = {
                    ...v,
                    description: v.description || null,
                    is_active: editing ? editing.is_active : true,
                  };
                  const onSuccess = () => { resetStructure(); setShowStructureForm(false); setEditingStructure(null); };
                  if (editingStructure) {
                    updateStructure.mutate({ structureId: editingStructure, input: payload }, { onSuccess });
                  } else {
                    createStructure.mutate(payload, { onSuccess });
                  }
                })}
                className="grid gap-4 rounded-md border p-4 sm:grid-cols-2 lg:grid-cols-5"
              >
                <div className="space-y-2">
                  <Label>Name</Label>
                  <Input placeholder="Teacher" {...regStructure("name")} />
                  {structureErrors.name && <p className="text-xs text-destructive">{structureErrors.name.message}</p>}
                </div>
                <div className="space-y-2">
                  <Label>Basic salary</Label>
                  <Input type="number" step="0.01" placeholder="60000" {...regStructure("basic_salary")} />
                  {structureErrors.basic_salary && <p className="text-xs text-destructive">{structureErrors.basic_salary.message}</p>}
                </div>
                <div className="space-y-2">
                  <Label>Tax %</Label>
                  <Input type="number" step="0.01" min="0" max="100" placeholder="10" {...regStructure("tax_percent")} />
                  {structureErrors.tax_percent && <p className="text-xs text-destructive">{structureErrors.tax_percent.message}</p>}
                </div>
                <div className="space-y-2">
                  <Label>Description</Label>
                  <Input placeholder="Optional note" {...regStructure("description")} />
                </div>
                <div className="flex items-end gap-2">
                  <Button type="submit" disabled={structureSubmitting}>
                    {structureSubmitting ? "Saving…" : editingStructure ? "Update" : "Create"}
                  </Button>
                  {editingStructure && (
                    <Button type="button" variant="ghost" onClick={() => { setEditingStructure(null); }}>Cancel</Button>
                  )}
                </div>
              </form>
            </motion.div>
          )}

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="pb-2 font-medium">Name</th>
                  <th className="pb-2 font-medium">Basic salary</th>
                  <th className="pb-2 font-medium">Tax</th>
                  <th className="pb-2 font-medium">Net</th>
                  <th className="pb-2 font-medium">Status</th>
                  <th className="pb-2 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {loadingStructures ? (
                  <tr><td colSpan={6}><Skeleton className="my-2 h-6 w-full" /></td></tr>
                ) : structures.length === 0 ? (
                  <tr><td colSpan={6} className="py-8 text-center text-muted-foreground">
                    No salary structures yet. Add one above.
                  </td></tr>
                ) : (
                  structures.map((s) => (
                    <tr key={s.id} className="border-b last:border-0 hover:bg-accent/40">
                      <td className="py-2.5 font-medium">{s.name}</td>
                      <td className="py-2.5">{currency(s.basic_salary)}</td>
                      <td className="py-2.5">{s.tax_percent}%</td>
                      <td className="py-2.5">{currency(s.basic_salary * (1 - s.tax_percent / 100))}</td>
                      <td className="py-2.5">
                        <span className={`rounded-full px-2 py-0.5 text-xs ${s.is_active ? "bg-emerald-500/15 text-emerald-600" : "bg-muted text-muted-foreground"}`}>
                          {s.is_active ? "Active" : "Inactive"}
                        </span>
                      </td>
                      <td className="py-2.5 text-right">
                        <div className="flex justify-end gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => {
                              setEditingStructure(s.id);
                              setShowStructureForm(true);
                              resetStructure({
                                name: s.name,
                                description: s.description ?? "",
                                basic_salary: s.basic_salary,
                                tax_percent: s.tax_percent,
                              });
                            }}
                          >
                            Edit
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => toggleStructure.mutate(s.id)}
                            disabled={toggleStructure.isPending}
                          >
                            {s.is_active ? "Deactivate" : "Activate"}
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

      {/* Staff assignments */}
      <Card>
        <CardHeader>
          <CardTitle>Staff pay assignments</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <form
            onSubmit={submitAssign((v) => {
              assignSalary.mutate({ ...v, effective_from: null }, { onSuccess: () => resetAssign() });
            })}
            className="grid gap-4 rounded-md border p-4 sm:grid-cols-2 lg:grid-cols-3"
          >
            <div className="space-y-2">
              <Label>Staff member</Label>
              <select className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm" {...regAssign("staff_id")}>
                <option value="">Choose…</option>
                {staff.map((m) => (
                  <option key={m.id} value={m.id}>{m.full_name}{assignMap.has(m.id) ? " (assigned)" : ""}</option>
                ))}
              </select>
              {assignErrors.staff_id && <p className="text-xs text-destructive">{assignErrors.staff_id.message}</p>}
            </div>
            <div className="space-y-2">
              <Label>Structure</Label>
              <select className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm" {...regAssign("structure_id")}>
                <option value="">Choose…</option>
                {structures.filter((s) => s.is_active).map((s) => (
                  <option key={s.id} value={s.id}>{s.name} — {currency(s.basic_salary)}</option>
                ))}
              </select>
              {assignErrors.structure_id && <p className="text-xs text-destructive">{assignErrors.structure_id.message}</p>}
            </div>
            <div className="flex items-end">
              <Button type="submit" disabled={assignSubmitting || assignSalary.isPending}>
                {assignSubmitting ? "Assigning…" : "Assign / update"}
              </Button>
            </div>
          </form>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="pb-2 font-medium">Staff</th>
                  <th className="pb-2 font-medium">Structure</th>
                  <th className="pb-2 font-medium">Effective from</th>
                </tr>
              </thead>
              <tbody>
                {assignments.length === 0 ? (
                  <tr><td colSpan={3} className="py-6 text-center text-muted-foreground">
                    No staff assigned to a structure yet.
                  </td></tr>
                ) : (
                  assignments.map((a) => (
                    <tr key={a.id} className="border-b last:border-0 hover:bg-accent/40">
                      <td className="py-2.5 font-medium">{a.staff_name ?? a.staff_id}</td>
                      <td className="py-2.5">{a.structure_name ?? a.structure_id}</td>
                      <td className="py-2.5">{a.effective_from ?? "—"}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Pay runs */}
      <Card>
        <CardHeader>
          <CardTitle>Pay runs</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <form
            onSubmit={submitRun((v) => {
              createRun.mutate(v, { onSuccess: (run) => { resetRun(); setActiveRunId(run.id); } });
            })}
            className="flex flex-wrap items-end gap-4 rounded-md border p-4"
          >
            <div className="space-y-2">
              <Label>Month (YYYY-MM)</Label>
              <Input placeholder="2026-08" className="w-40" {...regRun("month")} />
              {runErrors.month && <p className="text-xs text-destructive">{runErrors.month.message}</p>}
            </div>
            <Button type="submit" disabled={runSubmitting || createRun.isPending}>
              {runSubmitting ? "Running…" : "Create pay run"}
            </Button>
          </form>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="pb-2 font-medium">Month</th>
                  <th className="pb-2 font-medium">Gross</th>
                  <th className="pb-2 font-medium">Tax</th>
                  <th className="pb-2 font-medium">Net</th>
                  <th className="pb-2 font-medium">Status</th>
                  <th className="pb-2 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {runs.length === 0 ? (
                  <tr><td colSpan={6} className="py-6 text-center text-muted-foreground">
                    No pay runs yet. Create one for the current month.
                  </td></tr>
                ) : (
                  runs.map((r) => (
                    <tr key={r.id} className="border-b last:border-0 hover:bg-accent/40">
                      <td className="py-2.5 font-medium">{r.month}</td>
                      <td className="py-2.5">{currency(r.total_gross)}</td>
                      <td className="py-2.5">{currency(r.total_tax)}</td>
                      <td className="py-2.5 font-semibold">{currency(r.total_net)}</td>
                      <td className="py-2.5">
                        <span className={`rounded-full px-2 py-0.5 text-xs capitalize ${r.status === "paid" ? "bg-emerald-500/15 text-emerald-600" : "bg-amber-500/15 text-amber-600"}`}>
                          {r.status}
                        </span>
                      </td>
                      <td className="py-2.5 text-right">
                        <div className="flex justify-end gap-2">
                          <Button variant="ghost" size="sm" onClick={() => setActiveRunId(r.id)}>
                            Payslips
                          </Button>
                          {r.status !== "paid" && (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => markPaid.mutate(r.id)}
                              disabled={markPaid.isPending}
                            >
                              Mark paid
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {activeRunDetail && (
            <div className="rounded-md border p-4">
              <h3 className="mb-3 text-sm font-semibold">Payslips — {activeRunDetail.month}</h3>
              {activeRunDetail.payslips.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No payslips generated (no staff are assigned to a salary structure yet).
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                        <th className="pb-2 font-medium">Staff</th>
                        <th className="pb-2 font-medium">Gross</th>
                        <th className="pb-2 font-medium">Tax</th>
                        <th className="pb-2 font-medium">Net</th>
                      </tr>
                    </thead>
                    <tbody>
                      {activeRunDetail.payslips.map((p) => (
                        <tr key={p.id} className="border-b last:border-0">
                          <td className="py-2 font-medium">{p.staff_name ?? p.staff_id}</td>
                          <td className="py-2">{currency(p.gross)}</td>
                          <td className="py-2">{currency(p.tax)}</td>
                          <td className="py-2 font-semibold">{currency(p.net)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}