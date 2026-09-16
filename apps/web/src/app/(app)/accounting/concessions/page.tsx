"use client";

import { BadgePercent, Loader2, Plus, Receipt, RotateCcw, Trash2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useApplyCreditNote,
  useCreateCreditNote,
  useCreateDiscount,
  useCreateRefund,
  useCreditNotes,
  useDeleteDiscount,
  useDiscounts,
  useFeeStructures,
  useInvoices,
  usePayRefund,
  useRejectRefund,
  useApproveRefund,
  useRefunds,
  useStudents,
  useVoidCreditNote,
} from "@/hooks/use-api";
import { useAuth } from "@/providers/auth-provider";
import type { CreditNote, DiscountIn } from "@clearis/shared";
import { cn, formatMoney, todayIso } from "@/lib/utils";

const TABS = ["discounts", "credit-notes", "refunds"] as const;
type Tab = (typeof TABS)[number];

const TAB_LABELS: Record<Tab, string> = {
  discounts: "Discounts & waivers",
  "credit-notes": "Credit notes",
  refunds: "Refunds",
};

const DISCOUNT_KINDS = ["discount", "scholarship", "bursary", "staff_child", "sibling", "waiver"];
const REFUND_METHODS = ["cash", "bank_transfer", "cheque", "card", "other"];

function statusChip(status: string) {
  const map: Record<string, string> = {
    open: "bg-primary/10 text-primary",
    applied: "bg-success/10 text-success",
    void: "bg-muted text-muted-foreground",
    pending: "bg-warning/10 text-warning",
    approved: "bg-primary/10 text-primary",
    paid: "bg-success/10 text-success",
    rejected: "bg-destructive/10 text-destructive",
  };
  return map[status] ?? "bg-muted text-muted-foreground";
}

/** Pick an invoice to apply an open credit note to. */
function ApplyCreditNote({ note, onDone }: { note: CreditNote; onDone: () => void }) {
  const { data: invoices = [] } = useInvoices(note.student_id);
  const apply = useApplyCreditNote();
  const [invoiceId, setInvoiceId] = useState("");
  const open = invoices.filter((i) => i.status !== "paid");

  return (
    <div className="flex items-center gap-1.5">
      <select
        className="flex h-8 min-w-[150px] rounded-lg border border-border/80 bg-background/50 px-2 text-[12px]"
        value={invoiceId}
        onChange={(e) => setInvoiceId(e.target.value)}
      >
        <option value="">Apply to…</option>
        {open.map((inv) => (
          <option key={inv.id} value={inv.id}>
            {inv.reference_number.slice(-8)} — {formatMoney(inv.total_amount)}
          </option>
        ))}
      </select>
      <Button
        size="sm"
        disabled={!invoiceId || apply.isPending}
        onClick={() =>
          apply.mutate({ noteId: note.id, invoiceId }, { onSuccess: onDone })
        }
      >
        {apply.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Apply"}
      </Button>
    </div>
  );
}

export default function ConcessionsPage() {
  const { activeSchool } = useAuth();
  const permissions = activeSchool?.permissions ?? [];
  const canAmend = permissions.includes("accounting.amend");

  const [tab, setTab] = useState<Tab>("discounts");
  const [error, setError] = useState<string | null>(null);
  const [applyFor, setApplyFor] = useState<string | null>(null);

  const { data: students = [] } = useStudents();
  const { data: structures = [] } = useFeeStructures();
  const { data: discounts = [], isLoading: loadingDiscounts } = useDiscounts();
  const { data: notes = [], isLoading: loadingNotes } = useCreditNotes();
  const { data: refunds = [], isLoading: loadingRefunds } = useRefunds();

  const createDiscount = useCreateDiscount();
  const deleteDiscount = useDeleteDiscount();
  const createNote = useCreateCreditNote();
  const voidNote = useVoidCreditNote();
  const createRefund = useCreateRefund();
  const approveRefund = useApproveRefund();
  const rejectRefund = useRejectRefund();
  const payRefund = usePayRefund();

  const [discountForm, setDiscountForm] = useState({
    student_id: "",
    name: "",
    kind: "scholarship",
    mode: "percent" as "percent" | "amount",
    value: "",
    fee_structure_id: "",
    notes: "",
  });
  const [noteForm, setNoteForm] = useState({ student_id: "", amount: "", reason: "" });
  const [refundForm, setRefundForm] = useState({
    student_id: "",
    amount: "",
    method: "bank_transfer",
    reference: "",
    reason: "",
    mark_paid: false,
  });

  function studentName(id: string) {
    return students.find((s) => s.id === id)?.full_name ?? "—";
  }

  function submitDiscount(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    const value = Number(discountForm.value);
    createDiscount.mutate(
      {
        student_id: discountForm.student_id,
        name: discountForm.name,
        kind: discountForm.kind as DiscountIn["kind"],
        percent: discountForm.mode === "percent" ? value : null,
        amount: discountForm.mode === "amount" ? value : null,
        fee_structure_id: discountForm.fee_structure_id || null,
        notes: discountForm.notes || null,
      },
      {
        onSuccess: () =>
          setDiscountForm({
            student_id: "",
            name: "",
            kind: "scholarship",
            mode: "percent",
            value: "",
            fee_structure_id: "",
            notes: "",
          }),
        onError: (err) =>
          setError(err instanceof Error ? err.message : "Could not save the discount."),
      },
    );
  }

  function submitNote(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    createNote.mutate(
      {
        student_id: noteForm.student_id,
        amount: Number(noteForm.amount),
        reason: noteForm.reason || null,
      },
      {
        onSuccess: () => setNoteForm({ student_id: "", amount: "", reason: "" }),
        onError: (err) =>
          setError(err instanceof Error ? err.message : "Could not issue the credit note."),
      },
    );
  }

  function submitRefund(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    createRefund.mutate(
      {
        student_id: refundForm.student_id,
        amount: Number(refundForm.amount),
        method: refundForm.method,
        reference: refundForm.reference || null,
        reason: refundForm.reason || null,
        mark_paid: refundForm.mark_paid,
        refund_date: refundForm.mark_paid ? todayIso() : null,
      },
      {
        onSuccess: () =>
          setRefundForm({
            student_id: "",
            amount: "",
            method: "bank_transfer",
            reference: "",
            reason: "",
            mark_paid: false,
          }),
        onError: (err) =>
          setError(err instanceof Error ? err.message : "Could not record the refund."),
      },
    );
  }

  const studentSelect = (
    value: string,
    onChange: (v: string) => void,
  ) => (
    <select
      className="flex h-9 w-full rounded-xl border border-border/80 bg-background/50 px-3 text-[13px] shadow-sm"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      required
    >
      <option value="">Choose student…</option>
      {students.map((s) => (
        <option key={s.id} value={s.id}>
          {s.admission_no} · {s.full_name}
        </option>
      ))}
    </select>
  );

  return (
    <div className="space-y-5">
      <div className="min-w-0">
        <h1 className="text-[22px] font-bold tracking-tight text-foreground">
          Discounts, credit notes &amp; refunds
        </h1>
        <p className="mt-1 text-[13px] text-muted-foreground">
          Reduce what a student owes — scholarships, waivers and corrections — and pay money back
          out when it is due.
        </p>
      </div>

      <div className="flex gap-1.5">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => {
              setTab(t);
              setError(null);
            }}
            className={cn(
              "rounded-xl px-3.5 py-1.5 text-[12.5px] font-medium transition-colors",
              tab === t ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-accent/50",
            )}
          >
            {TAB_LABELS[t]}
          </button>
        ))}
      </div>

      {error && (
        <p className="rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-2.5 text-[12.5px] text-destructive">
          {error}
        </p>
      )}

      {/* ── Discounts ─────────────────────────────────────────────── */}
      {tab === "discounts" && (
        <>
          {canAmend && (
            <Card className="premium-card">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BadgePercent className="h-4 w-4 text-primary" /> New discount or waiver
                </CardTitle>
              </CardHeader>
              <CardContent>
                <form onSubmit={submitDiscount} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  <div className="space-y-1.5">
                    <Label className="text-[11px]">Student</Label>
                    {studentSelect(discountForm.student_id, (v) =>
                      setDiscountForm({ ...discountForm, student_id: v }),
                    )}
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-[11px]">Label</Label>
                    <Input
                      value={discountForm.name}
                      onChange={(e) => setDiscountForm({ ...discountForm, name: e.target.value })}
                      placeholder="Staff child 50%"
                      required
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-[11px]">Kind</Label>
                    <select
                      className="flex h-9 w-full rounded-xl border border-border/80 bg-background/50 px-3 text-[13px] shadow-sm"
                      value={discountForm.kind}
                      onChange={(e) => setDiscountForm({ ...discountForm, kind: e.target.value })}
                    >
                      {DISCOUNT_KINDS.map((k) => (
                        <option key={k} value={k}>
                          {k.replace("_", " ")}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-[11px]">Reduction</Label>
                    <div className="flex gap-2">
                      <select
                        className="flex h-9 w-24 rounded-xl border border-border/80 bg-background/50 px-2 text-[13px] shadow-sm"
                        value={discountForm.mode}
                        onChange={(e) =>
                          setDiscountForm({
                            ...discountForm,
                            mode: e.target.value as "percent" | "amount",
                          })
                        }
                      >
                        <option value="percent">%</option>
                        <option value="amount">Flat</option>
                      </select>
                      <Input
                        type="number"
                        step="0.01"
                        min="0.01"
                        value={discountForm.value}
                        onChange={(e) => setDiscountForm({ ...discountForm, value: e.target.value })}
                        placeholder={discountForm.mode === "percent" ? "50" : "25000"}
                        required
                      />
                    </div>
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-[11px]">Applies to</Label>
                    <select
                      className="flex h-9 w-full rounded-xl border border-border/80 bg-background/50 px-3 text-[13px] shadow-sm"
                      value={discountForm.fee_structure_id}
                      onChange={(e) =>
                        setDiscountForm({ ...discountForm, fee_structure_id: e.target.value })
                      }
                    >
                      <option value="">All fees</option>
                      {structures.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-[11px]">Note (optional)</Label>
                    <Input
                      value={discountForm.notes}
                      onChange={(e) => setDiscountForm({ ...discountForm, notes: e.target.value })}
                      placeholder="Approved by the board, 12 Sep"
                    />
                  </div>
                  <div className="flex items-end lg:col-span-3">
                    <Button
                      type="submit"
                      className="gap-1.5"
                      disabled={createDiscount.isPending}
                    >
                      {createDiscount.isPending ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Plus className="h-4 w-4" />
                      )}
                      Save discount
                    </Button>
                  </div>
                </form>
                <p className="mt-3 text-[11.5px] text-muted-foreground">
                  A discount is applied automatically the next time an invoice is raised for this
                  student — it is not a manual adjustment.
                </p>
              </CardContent>
            </Card>
          )}

          <Card className="premium-card">
            <CardHeader>
              <CardTitle>Active and past discounts</CardTitle>
            </CardHeader>
            <CardContent>
              {loadingDiscounts ? (
                <Skeleton className="h-32 w-full" />
              ) : discounts.length === 0 ? (
                <p className="py-8 text-center text-[13px] text-muted-foreground/70">
                  No discounts or waivers on record.
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-[13px]">
                    <thead>
                      <tr className="border-b border-border/40 text-left text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground/60">
                        <th className="pb-2.5">Student</th>
                        <th className="pb-2.5">Label</th>
                        <th className="pb-2.5">Kind</th>
                        <th className="pb-2.5">Reduction</th>
                        <th className="pb-2.5">Applies to</th>
                        {canAmend && <th className="pb-2.5 text-right">—</th>}
                      </tr>
                    </thead>
                    <tbody>
                      {discounts.map((d) => (
                        <tr
                          key={d.id}
                          className="border-b border-border/30 last:border-0 transition-colors hover:bg-accent/40"
                        >
                          <td className="py-3">
                            <p className="font-medium">{d.student_name ?? studentName(d.student_id)}</p>
                            <p className="font-mono text-[11px] text-muted-foreground">
                              {d.admission_no ?? ""}
                            </p>
                          </td>
                          <td className="py-3">{d.name}</td>
                          <td className="py-3 capitalize text-muted-foreground">
                            {d.kind.replace("_", " ")}
                          </td>
                          <td className="py-3 font-medium">
                            {d.percent != null
                              ? `${d.percent}%`
                              : formatMoney(d.amount ?? 0)}
                          </td>
                          <td className="py-3 text-muted-foreground">
                            {d.fee_structure_name ?? "All fees"}
                          </td>
                          {canAmend && (
                            <td className="py-3 text-right">
                              <Button
                                size="sm"
                                variant="ghost"
                                disabled={deleteDiscount.isPending}
                                onClick={() => deleteDiscount.mutate(d.id)}
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                              </Button>
                            </td>
                          )}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}

      {/* ── Credit notes ──────────────────────────────────────────── */}
      {tab === "credit-notes" && (
        <>
          {canAmend && (
            <Card className="premium-card">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Receipt className="h-4 w-4 text-primary" /> Issue a credit note
                </CardTitle>
              </CardHeader>
              <CardContent>
                <form onSubmit={submitNote} className="grid gap-4 sm:grid-cols-3">
                  <div className="space-y-1.5">
                    <Label className="text-[11px]">Student</Label>
                    {studentSelect(noteForm.student_id, (v) =>
                      setNoteForm({ ...noteForm, student_id: v }),
                    )}
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-[11px]">Amount</Label>
                    <Input
                      type="number"
                      step="0.01"
                      min="0.01"
                      value={noteForm.amount}
                      onChange={(e) => setNoteForm({ ...noteForm, amount: e.target.value })}
                      placeholder="15000"
                      required
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-[11px]">Reason</Label>
                    <Input
                      value={noteForm.reason}
                      onChange={(e) => setNoteForm({ ...noteForm, reason: e.target.value })}
                      placeholder="Over-billed for Third Term"
                    />
                  </div>
                  <div className="flex items-end sm:col-span-3">
                    <Button type="submit" disabled={createNote.isPending} className="gap-1.5">
                      {createNote.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                      Issue credit note
                    </Button>
                  </div>
                </form>
              </CardContent>
            </Card>
          )}

          <Card className="premium-card">
            <CardHeader>
              <CardTitle>Credit notes</CardTitle>
            </CardHeader>
            <CardContent>
              {loadingNotes ? (
                <Skeleton className="h-32 w-full" />
              ) : notes.length === 0 ? (
                <p className="py-8 text-center text-[13px] text-muted-foreground/70">
                  No credit notes issued.
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-[13px]">
                    <thead>
                      <tr className="border-b border-border/40 text-left text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground/60">
                        <th className="pb-2.5">Number</th>
                        <th className="pb-2.5">Student</th>
                        <th className="pb-2.5 text-right">Amount</th>
                        <th className="pb-2.5">Reason</th>
                        <th className="pb-2.5">Status</th>
                        <th className="pb-2.5 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {notes.map((n) => (
                        <tr
                          key={n.id}
                          className="border-b border-border/30 last:border-0 transition-colors hover:bg-accent/40"
                        >
                          <td className="py-3 font-mono text-[11px] text-muted-foreground">
                            {n.note_number}
                          </td>
                          <td className="py-3">
                            <p className="font-medium">{n.student_name ?? studentName(n.student_id)}</p>
                            <p className="text-[11px] text-muted-foreground">{n.issued_date}</p>
                          </td>
                          <td className="py-3 text-right font-medium tabular-nums">
                            {formatMoney(n.amount)}
                          </td>
                          <td className="py-3 text-muted-foreground">{n.reason ?? "—"}</td>
                          <td className="py-3">
                            <span
                              className={cn(
                                "inline-flex rounded-full px-2 py-0.5 text-[11px] font-semibold capitalize",
                                statusChip(n.status),
                              )}
                            >
                              {n.status}
                            </span>
                          </td>
                          <td className="py-3 text-right">
                            {n.status === "open" && canAmend ? (
                              applyFor === n.id ? (
                                <ApplyCreditNote note={n} onDone={() => setApplyFor(null)} />
                              ) : (
                                <div className="flex items-center justify-end gap-1.5">
                                  <Button size="sm" variant="outline" onClick={() => setApplyFor(n.id)}>
                                    Apply
                                  </Button>
                                  <Button
                                    size="sm"
                                    variant="ghost"
                                    disabled={voidNote.isPending}
                                    onClick={() => voidNote.mutate(n.id)}
                                  >
                                    Void
                                  </Button>
                                </div>
                              )
                            ) : (
                              <span className="text-[11px] text-muted-foreground/50">
                                {n.applied_invoice_id ? "Applied" : "—"}
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}

      {/* ── Refunds ───────────────────────────────────────────────── */}
      {tab === "refunds" && (
        <>
          {canAmend && (
            <Card className="premium-card">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <RotateCcw className="h-4 w-4 text-primary" /> Record a refund
                </CardTitle>
              </CardHeader>
              <CardContent>
                <form onSubmit={submitRefund} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  <div className="space-y-1.5">
                    <Label className="text-[11px]">Student</Label>
                    {studentSelect(refundForm.student_id, (v) =>
                      setRefundForm({ ...refundForm, student_id: v }),
                    )}
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-[11px]">Amount</Label>
                    <Input
                      type="number"
                      step="0.01"
                      min="0.01"
                      value={refundForm.amount}
                      onChange={(e) => setRefundForm({ ...refundForm, amount: e.target.value })}
                      placeholder="50000"
                      required
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-[11px]">Method</Label>
                    <select
                      className="flex h-9 w-full rounded-xl border border-border/80 bg-background/50 px-3 text-[13px] shadow-sm"
                      value={refundForm.method}
                      onChange={(e) => setRefundForm({ ...refundForm, method: e.target.value })}
                    >
                      {REFUND_METHODS.map((m) => (
                        <option key={m} value={m}>
                          {m.replace("_", " ")}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-[11px]">Reference (optional)</Label>
                    <Input
                      value={refundForm.reference}
                      onChange={(e) => setRefundForm({ ...refundForm, reference: e.target.value })}
                    />
                  </div>
                  <div className="space-y-1.5 lg:col-span-2">
                    <Label className="text-[11px]">Reason</Label>
                    <Input
                      value={refundForm.reason}
                      onChange={(e) => setRefundForm({ ...refundForm, reason: e.target.value })}
                      placeholder="Withdrawn mid-term"
                    />
                  </div>
                  <label className="flex items-end gap-2 pb-2 text-[12px]">
                    <input
                      type="checkbox"
                      checked={refundForm.mark_paid}
                      onChange={(e) =>
                        setRefundForm({ ...refundForm, mark_paid: e.target.checked })
                      }
                    />
                    Already paid — skip approval
                  </label>
                  <div className="flex items-end lg:col-span-3">
                    <Button type="submit" disabled={createRefund.isPending} className="gap-1.5">
                      {createRefund.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                      Record refund
                    </Button>
                  </div>
                </form>
                <p className="mt-3 text-[11.5px] text-muted-foreground">
                  A refund can never exceed what the student has actually paid and kept.
                </p>
              </CardContent>
            </Card>
          )}

          <Card className="premium-card">
            <CardHeader>
              <CardTitle>Refunds</CardTitle>
            </CardHeader>
            <CardContent>
              {loadingRefunds ? (
                <Skeleton className="h-32 w-full" />
              ) : refunds.length === 0 ? (
                <p className="py-8 text-center text-[13px] text-muted-foreground/70">
                  No refunds recorded.
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-[13px]">
                    <thead>
                      <tr className="border-b border-border/40 text-left text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground/60">
                        <th className="pb-2.5">Student</th>
                        <th className="pb-2.5 text-right">Amount</th>
                        <th className="pb-2.5">Method</th>
                        <th className="pb-2.5">Reason</th>
                        <th className="pb-2.5">Date</th>
                        <th className="pb-2.5">Status</th>
                        {canAmend && <th className="pb-2.5 text-right">Actions</th>}
                      </tr>
                    </thead>
                    <tbody>
                      {refunds.map((r) => (
                        <tr
                          key={r.id}
                          className="border-b border-border/30 last:border-0 transition-colors hover:bg-accent/40"
                        >
                          <td className="py-3">
                            <p className="font-medium">{r.student_name ?? studentName(r.student_id)}</p>
                            <p className="font-mono text-[11px] text-muted-foreground">
                              {r.admission_no ?? ""}
                            </p>
                          </td>
                          <td className="py-3 text-right font-medium tabular-nums">
                            {formatMoney(r.amount, r.currency)}
                          </td>
                          <td className="py-3 capitalize text-muted-foreground">
                            {r.method.replace("_", " ")}
                          </td>
                          <td className="py-3 text-muted-foreground">{r.reason ?? "—"}</td>
                          <td className="py-3 text-muted-foreground">{r.refund_date ?? "—"}</td>
                          <td className="py-3">
                            <span
                              className={cn(
                                "inline-flex rounded-full px-2 py-0.5 text-[11px] font-semibold capitalize",
                                statusChip(r.status),
                              )}
                            >
                              {r.status}
                            </span>
                          </td>
                          {canAmend && (
                            <td className="py-3 text-right">
                              <div className="flex items-center justify-end gap-1.5">
                                {r.status === "pending" && (
                                  <>
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      disabled={approveRefund.isPending}
                                      onClick={() => approveRefund.mutate(r.id)}
                                    >
                                      Approve
                                    </Button>
                                    <Button
                                      size="sm"
                                      variant="ghost"
                                      disabled={rejectRefund.isPending}
                                      onClick={() =>
                                        rejectRefund.mutate({
                                          refundId: r.id,
                                          reason: "Rejected by accountant",
                                        })
                                      }
                                    >
                                      Reject
                                    </Button>
                                  </>
                                )}
                                {r.status === "approved" && (
                                  <Button
                                    size="sm"
                                    disabled={payRefund.isPending}
                                    onClick={() => payRefund.mutate({ refundId: r.id })}
                                  >
                                    Mark paid
                                  </Button>
                                )}
                                {(r.status === "paid" || r.status === "rejected") && (
                                  <span className="text-[11px] text-muted-foreground/50">—</span>
                                )}
                              </div>
                            </td>
                          )}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
