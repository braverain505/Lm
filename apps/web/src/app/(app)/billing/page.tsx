"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { motion } from "framer-motion";
import { CheckCircle2, Lock, Plus, Printer, XCircle } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { ReceiptDialog } from "@/components/receipt-dialog";
import { useAuth } from "@/providers/auth-provider";
import {
  useArms,
  useCreateFeeStructure,
  useCreateInvoice,
  useFeeStatus,
  useFeeStructures,
  useInvoices,
  usePayments,
  useRecordPayment,
  useSessions,
  useStudentFeeBalance,
  useStudents,
  useTerms,
  useToggleFeeStructure,
} from "@/hooks/use-api";

const structureSchema = z.object({
  name: z.string().min(1, "Name required"),
  fee_type: z.string().min(1),
  amount: z.coerce.number().positive("Amount must be > 0"),
  billing_frequency: z.enum(["term", "month", "year", "one_time"]),
});
type StructureForm = z.infer<typeof structureSchema>;

const invoiceSchema = z.object({
  fee_structure_id: z.string().min(1, "Choose a fee structure"),
});
type InvoiceForm = z.infer<typeof invoiceSchema>;

const paymentSchema = z.object({
  amount: z.coerce.number().positive("Amount must be > 0"),
  payment_method: z.string().min(1),
  payment_reference: z.string().optional(),
});
type PaymentForm = z.infer<typeof paymentSchema>;

const PAYMENT_METHODS = ["cash", "bank_transfer", "card", "pos", "other"];

export default function BillingPage() {
  const { activeSchool } = useAuth();
  const canView = activeSchool?.permissions?.includes("fees.view") ?? false;

  const { data: structures = [], isLoading: loadingStructures } = useFeeStructures();
  const { data: students = [] } = useStudents();
  const [showStructureForm, setShowStructureForm] = useState(false);
  const [studentId, setStudentId] = useState("");
  const [statusTermId, setStatusTermId] = useState("");
  const [statusArmId, setStatusArmId] = useState("");
  const [receiptPaymentId, setReceiptPaymentId] = useState<string | null>(null);

  const createStructure = useCreateFeeStructure();
  const toggleStructure = useToggleFeeStructure();
  const createInvoice = useCreateInvoice();
  const recordPayment = useRecordPayment();

  const { data: sessions = [] } = useSessions();
  const statusSessionId = sessions.find((s) => s.is_current)?.id ?? sessions[0]?.id ?? null;
  const { data: statusTerms = [] } = useTerms(statusSessionId);
  const { data: statusArms = [] } = useArms(statusSessionId);
  const { data: payments = [] } = usePayments(studentId || undefined);
  const { data: feeStatus, isLoading: loadingStatus } = useFeeStatus({
    termId: statusTermId || undefined,
    armId: statusArmId || undefined,
  });

  const { data: invoices = [] } = useInvoices(studentId || null);
  const { data: balance } = useStudentFeeBalance(studentId || null);

  const {
    register: regStructure,
    handleSubmit: submitStructure,
    reset: resetStructure,
    formState: { errors: structureErrors, isSubmitting: structureSubmitting },
  } = useForm<StructureForm>({ resolver: zodResolver(structureSchema) });

  const {
    register: regInvoice,
    handleSubmit: submitInvoice,
    reset: resetInvoice,
    formState: { errors: invoiceErrors, isSubmitting: invoiceSubmitting },
  } = useForm<InvoiceForm>({ resolver: zodResolver(invoiceSchema) });

  const {
    register: regPayment,
    handleSubmit: submitPayment,
    reset: resetPayment,
    formState: { errors: paymentErrors, isSubmitting: paymentSubmitting },
  } = useForm<PaymentForm>({ resolver: zodResolver(paymentSchema) });

  const selectedStudent = students.find((s) => s.id === studentId);

  if (!canView) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 py-24 text-center">
        <Lock className="h-8 w-8 text-muted-foreground" />
        <h1 className="text-lg font-semibold">Accounting is Accountant-only</h1>
        <p className="max-w-sm text-sm text-muted-foreground">
          Only the school Accountant role can view fees, payments, and receipts.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Billing</h1>
          <p className="text-sm text-muted-foreground">
            Fee structures, invoices, and payments for {students.length} students.
          </p>
        </div>
        <Button onClick={() => setShowStructureForm((v) => !v)}>
          <Plus className="h-4 w-4" /> Add fee structure
        </Button>
      </div>

      {/* Fee structures */}
      <Card>
        <CardHeader>
          <CardTitle>Fee structures</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {showStructureForm && (
            <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
              <form
                onSubmit={submitStructure((v) => {
                  createStructure.mutate(
                    { ...v, currency: "NGN", is_mandatory: true, allow_override: false },
                    { onSuccess: () => { resetStructure(); setShowStructureForm(false); } },
                  );
                })}
                className="grid gap-4 rounded-md border p-4 sm:grid-cols-2 lg:grid-cols-5"
              >
                <div className="space-y-2">
                  <Label>Name</Label>
                  <Input placeholder="Tuition" {...regStructure("name")} />
                  {structureErrors.name && <p className="text-xs text-destructive">{structureErrors.name.message}</p>}
                </div>
                <div className="space-y-2">
                  <Label>Type</Label>
                  <select className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm" {...regStructure("fee_type")}>
                    {["tuition", "boarding", "activity", "examination", "library", "other"].map((t) => (
                      <option key={t} value={t}>{t}</option>
                    ))}
                  </select>
                </div>
                <div className="space-y-2">
                  <Label>Amount</Label>
                  <Input type="number" step="0.01" placeholder="100000" {...regStructure("amount")} />
                  {structureErrors.amount && <p className="text-xs text-destructive">{structureErrors.amount.message}</p>}
                </div>
                <div className="space-y-2">
                  <Label>Frequency</Label>
                  <select className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm" {...regStructure("billing_frequency")}>
                    {["term", "month", "year", "one_time"].map((f) => (
                      <option key={f} value={f}>{f}</option>
                    ))}
                  </select>
                </div>
                <div className="flex items-end gap-2">
                  <Button type="submit" disabled={structureSubmitting}>
                    {structureSubmitting ? "Saving…" : "Create"}
                  </Button>
                </div>
              </form>
            </motion.div>
          )}

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="pb-2 font-medium">Name</th>
                  <th className="pb-2 font-medium">Type</th>
                  <th className="pb-2 font-medium">Amount</th>
                  <th className="pb-2 font-medium">Frequency</th>
                  <th className="pb-2 font-medium">Status</th>
                  <th className="pb-2 font-medium text-right">Active</th>
                </tr>
              </thead>
              <tbody>
                {loadingStructures ? (
                  <tr><td colSpan={6}><Skeleton className="my-2 h-6 w-full" /></td></tr>
                ) : structures.length === 0 ? (
                  <tr><td colSpan={6} className="py-8 text-center text-muted-foreground">
                    No fee structures yet. Add one above.
                  </td></tr>
                ) : (
                  structures.map((s) => (
                    <tr key={s.id} className="border-b last:border-0 hover:bg-accent/40">
                      <td className="py-2.5 font-medium">{s.name}</td>
                      <td className="py-2.5 capitalize">{s.fee_type}</td>
                      <td className="py-2.5">₦{s.amount.toLocaleString()}</td>
                      <td className="py-2.5 capitalize">{s.billing_frequency}</td>
                      <td className="py-2.5">
                        <span className={`rounded-full px-2 py-0.5 text-xs ${s.is_active ? "bg-emerald-500/15 text-emerald-600" : "bg-muted text-muted-foreground"}`}>
                          {s.is_active ? "Active" : "Inactive"}
                        </span>
                      </td>
                      <td className="py-2.5 text-right">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => toggleStructure.mutate(s.id)}
                          disabled={toggleStructure.isPending}
                        >
                          {s.is_active ? "Deactivate" : "Activate"}
                        </Button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Invoices */}
      <Card>
        <CardHeader>
          <CardTitle>Invoices</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Student</Label>
              <select
                className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
                value={studentId}
                onChange={(e) => setStudentId(e.target.value)}
              >
                <option value="">Choose student…</option>
                {students.map((s) => (
                  <option key={s.id} value={s.id}>{s.admission_no} · {s.full_name}</option>
                ))}
              </select>
            </div>
          </div>

          {selectedStudent && structures.length > 0 && (
            <form
              onSubmit={submitInvoice((v) => {
                createInvoice.mutate(
                  { student_id: studentId, fee_structure_id: v.fee_structure_id, batch_number: `B-${Date.now().toString(36).toUpperCase()}` },
                  { onSuccess: () => resetInvoice() },
                );
              })}
              className="grid gap-4 rounded-md border p-4 sm:grid-cols-2 lg:grid-cols-3"
            >
              <div className="space-y-2">
                <Label>Fee structure</Label>
                <select className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm" {...regInvoice("fee_structure_id")}>
                  <option value="">Choose…</option>
                  {structures.filter((s) => s.is_active).map((s) => (
                    <option key={s.id} value={s.id}>{s.name} — ₦{s.amount.toLocaleString()}</option>
                  ))}
                </select>
                {invoiceErrors.fee_structure_id && <p className="text-xs text-destructive">{invoiceErrors.fee_structure_id.message}</p>}
              </div>
              <div className="flex items-end">
                <Button type="submit" disabled={invoiceSubmitting || createInvoice.isPending}>
                  {invoiceSubmitting ? "Creating…" : "Create invoice"}
                </Button>
              </div>
            </form>
          )}

          {balance && (
            <div className="grid gap-4 rounded-md border p-4 sm:grid-cols-4">
              <div>
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Owed</p>
                <p className="text-lg font-semibold">₦{balance.total_owed.toLocaleString()}</p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Paid</p>
                <p className="text-lg font-semibold text-emerald-600">₦{balance.total_paid.toLocaleString()}</p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Unpaid</p>
                <p className="text-lg font-semibold text-destructive">₦{balance.total_unpaid.toLocaleString()}</p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Current invoice</p>
                <p className="text-lg font-semibold">₦{balance.current_invoice_total.toLocaleString()}</p>
              </div>
            </div>
          )}

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="pb-2 font-medium">Ref</th>
                  <th className="pb-2 font-medium">Amount</th>
                  <th className="pb-2 font-medium">Status</th>
                  <th className="pb-2 font-medium">Due</th>
                  <th className="pb-2 font-medium text-right">Record payment</th>
                </tr>
              </thead>
              <tbody>
                {invoices.length === 0 ? (
                  <tr><td colSpan={5} className="py-6 text-center text-muted-foreground">
                    No invoices for this student yet.
                  </td></tr>
                ) : (
                  invoices.map((inv) => (
                    <tr key={inv.id} className="border-b last:border-0 hover:bg-accent/40">
                      <td className="py-2.5 font-mono text-xs">{inv.reference_number}</td>
                      <td className="py-2.5">₦{inv.total_amount.toLocaleString()}</td>
                      <td className="py-2.5">
                        <span className={`rounded-full px-2 py-0.5 text-xs capitalize ${
                          inv.status === "paid" ? "bg-emerald-500/15 text-emerald-600" :
                          inv.status === "partial" ? "bg-amber-500/15 text-amber-600" :
                          "bg-muted text-muted-foreground"
                        }`}>{inv.status}</span>
                      </td>
                      <td className="py-2.5">{inv.due_date}</td>
                      <td className="py-2.5 text-right">
                        {inv.status !== "paid" && (
                          <form
                            onSubmit={submitPayment((v) => {
                              recordPayment.mutate(
                                { invoice_id: inv.id, amount: v.amount, payment_method: v.payment_method, payment_reference: v.payment_reference },
                                { onSuccess: () => resetPayment() },
                              );
                            })}
                            className="flex flex-wrap items-center justify-end gap-2"
                          >
                            <Input type="number" step="0.01" placeholder="Amount" className="h-8 w-28" {...regPayment("amount")} />
                            <select className="h-8 w-32 rounded-md border border-input bg-transparent px-2 text-sm" {...regPayment("payment_method")}>
                              {PAYMENT_METHODS.map((m) => <option key={m} value={m}>{m}</option>)}
                            </select>
                            <Button type="submit" size="sm" variant="outline" disabled={paymentSubmitting}>
                              Pay
                            </Button>
                          </form>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Payment status — who has paid and who has not */}
      <Card>
        <CardHeader>
          <CardTitle>Payment status</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Term</Label>
              <select
                className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
                value={statusTermId}
                onChange={(e) => setStatusTermId(e.target.value)}
              >
                <option value="">All terms</option>
                {statusTerms.map((t) => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Class</Label>
              <select
                className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
                value={statusArmId}
                onChange={(e) => setStatusArmId(e.target.value)}
              >
                <option value="">All classes</option>
                {statusArms.map((a) => (
                  <option key={a.id} value={a.id}>{a.full_name}</option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Owing</Label>
              <div className="flex h-9 items-center gap-2 rounded-md border px-3 text-sm font-semibold text-destructive">
                <XCircle className="h-4 w-4" />
                {loadingStatus ? "…" : (feeStatus?.summary.unpaid ?? 0)} unpaid
              </div>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Cleared</Label>
              <div className="flex h-9 items-center gap-2 rounded-md border px-3 text-sm font-semibold text-emerald-600">
                <CheckCircle2 className="h-4 w-4" />
                {loadingStatus ? "…" : (feeStatus?.summary.paid ?? 0)} paid
              </div>
            </div>
          </div>

          {loadingStatus ? (
            <Skeleton className="h-40 w-full" />
          ) : feeStatus?.students.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No students in this scope yet. Create invoices or enroll students to see payment status.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="pb-2 font-medium">Student</th>
                    <th className="pb-2 font-medium">Class</th>
                    <th className="pb-2 font-medium">Invoiced</th>
                    <th className="pb-2 font-medium">Paid</th>
                    <th className="pb-2 font-medium">Balance</th>
                    <th className="pb-2 font-medium text-right">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {feeStatus?.students.map((s) => (
                    <tr key={s.student_id} className="border-b last:border-0 hover:bg-accent/40">
                      <td className="py-2.5">
                        <p className="font-medium">{s.full_name}</p>
                        <p className="font-mono text-xs text-muted-foreground">{s.admission_no}</p>
                      </td>
                      <td className="py-2.5">{s.arm_name ?? "—"}</td>
                      <td className="py-2.5 tabular-nums">{s.invoiced > 0 ? `₦${s.invoiced.toLocaleString()}` : "—"}</td>
                      <td className="py-2.5 tabular-nums text-emerald-600">
                        {s.paid > 0 ? `₦${s.paid.toLocaleString()}` : "—"}
                      </td>
                      <td className={`py-2.5 tabular-nums ${s.balance > 0 ? "font-semibold text-destructive" : "text-muted-foreground"}`}>
                        {s.balance > 0 ? `₦${s.balance.toLocaleString()}` : "—"}
                      </td>
                      <td className="py-2.5 text-right">
                        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                          s.status === "paid" ? "bg-emerald-500/15 text-emerald-600" :
                          s.status === "partial" ? "bg-amber-500/15 text-amber-600" :
                          "bg-muted text-muted-foreground"
                        }`}>
                          {s.status === "unpaid" ? "not paid" : s.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Payments received + receipts */}
      <Card>
        <CardHeader>
          <CardTitle>Payments received</CardTitle>
        </CardHeader>
        <CardContent>
          {payments.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">
              No payments recorded yet. Record a payment on an invoice above.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="pb-2 font-medium">Receipt no.</th>
                    <th className="pb-2 font-medium">Date</th>
                    <th className="pb-2 font-medium">Student</th>
                    <th className="pb-2 font-medium">Method</th>
                    <th className="pb-2 font-medium text-right">Amount</th>
                    <th className="pb-2 text-right font-medium">Receipt</th>
                  </tr>
                </thead>
                <tbody>
                  {payments.map((p) => {
                    const st = students.find((x) => x.id === p.student_id);
                    return (
                      <tr key={p.id} className="border-b last:border-0 hover:bg-accent/40">
                        <td className="py-2.5 font-mono text-xs">{p.receipt_number ?? "—"}</td>
                        <td className="py-2.5">{p.payment_date}</td>
                        <td className="py-2.5">{st?.full_name ?? "—"}</td>
                        <td className="py-2.5 capitalize">{p.payment_method}</td>
                        <td className="py-2.5 text-right tabular-nums">₦{p.amount.toLocaleString()}</td>
                        <td className="py-2.5 text-right">
                          <Button size="sm" variant="outline" onClick={() => setReceiptPaymentId(p.id)}>
                            <Printer className="h-3.5 w-3.5" /> View
                          </Button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <ReceiptDialog paymentId={receiptPaymentId} onClose={() => setReceiptPaymentId(null)} />
    </div>
  );
}
