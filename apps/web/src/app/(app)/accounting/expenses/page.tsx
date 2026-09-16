"use client";

import { CheckCircle2, Loader2, Plus, Receipt, Trash2, XCircle } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useApproveExpense,
  useCashAccounts,
  useCreateExpense,
  useCreateExpenseCategory,
  useDeleteExpense,
  useExpenseCategories,
  useExpenses,
  usePayExpense,
  useRejectExpense,
} from "@/hooks/use-api";
import { useAuth } from "@/providers/auth-provider";
import { useSessionTerm } from "@/providers/session-context";
import { cn, formatMoney, todayIso } from "@/lib/utils";

const PAYMENT_METHODS = ["cash", "bank_transfer", "card", "pos", "cheque", "other"];

const STATUS_FILTERS = ["", "draft", "approved", "paid", "rejected"] as const;

function statusChip(status: string) {
  const map: Record<string, string> = {
    draft: "bg-muted text-muted-foreground",
    approved: "bg-primary/10 text-primary",
    paid: "bg-success/10 text-success",
    rejected: "bg-destructive/10 text-destructive",
  };
  return map[status] ?? "bg-muted text-muted-foreground";
}

export default function ExpensesPage() {
  const { activeSchool } = useAuth();
  const { term } = useSessionTerm();
  const permissions = activeSchool?.permissions ?? [];
  const canManage = permissions.includes("accounting.expenses");

  const [status, setStatus] = useState<string>("");
  const { data: expenses, isLoading } = useExpenses(
    status ? { status, termId: term?.id } : { termId: term?.id },
  );
  const { data: categories = [] } = useExpenseCategories();
  const { data: accounts = [] } = useCashAccounts();

  const createExpense = useCreateExpense();
  const createCategory = useCreateExpenseCategory();
  const approveExpense = useApproveExpense();
  const rejectExpense = useRejectExpense();
  const payExpense = usePayExpense();
  const deleteExpense = useDeleteExpense();

  const [showForm, setShowForm] = useState(false);
  const [newCategory, setNewCategory] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    description: "",
    amount: "",
    expense_date: todayIso(),
    payment_method: "cash",
    category_id: "",
    cash_account_id: "",
    payee: "",
    reference: "",
    requires_approval: false,
    mark_paid: false,
  });

  const currency = accounts[0]?.currency ?? "NGN";

  function submit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    createExpense.mutate(
      {
        description: form.description,
        amount: Number(form.amount),
        expense_date: form.expense_date,
        payment_method: form.payment_method,
        category_id: form.category_id || null,
        cash_account_id: form.cash_account_id || null,
        payee: form.payee || null,
        reference: form.reference || null,
        term_id: term?.id ?? null,
        requires_approval: form.requires_approval,
        mark_paid: form.mark_paid,
      },
      {
        onSuccess: () => {
          setForm({ ...form, description: "", amount: "", payee: "", reference: "" });
          setShowForm(false);
        },
        onError: (err) =>
          setError(err instanceof Error ? err.message : "Could not record the expense."),
      },
    );
  }

  const rows = expenses?.items ?? [];
  const totalPaid = rows
    .filter((r) => r.status === "paid")
    .reduce((sum, r) => sum + r.amount, 0);
  const totalPending = rows
    .filter((r) => r.status === "draft" || r.status === "approved")
    .reduce((sum, r) => sum + r.amount, 0);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-[22px] font-bold tracking-tight text-foreground">Expenses</h1>
          <p className="mt-1 text-[13px] text-muted-foreground">
            What the school spends beyond fees — running costs and petty cash
            {term ? ` · ${term.name}` : ""}.
          </p>
        </div>
        {canManage && (
          <Button onClick={() => setShowForm((v) => !v)} className="gap-1.5">
            <Plus className="h-4 w-4" /> Record expense
          </Button>
        )}
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        {[
          { label: "Paid (in view)", value: totalPaid, tone: "text-foreground" },
          { label: "Awaiting payment", value: totalPending, tone: "text-primary" },
          { label: "Entries", value: rows.length, tone: "text-foreground", raw: true },
        ].map((item) => (
          <Card key={item.label} className="premium-card">
            <CardContent className="p-4">
              <p className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground/60">
                {item.label}
              </p>
              <p className={cn("mt-1 text-xl font-bold tabular-nums", item.tone)}>
                {item.raw ? item.value : formatMoney(item.value as number, currency)}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      {showForm && canManage && (
        <Card className="premium-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Receipt className="h-4 w-4 text-primary" /> New expense
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <div className="space-y-1.5 lg:col-span-2">
                <Label className="text-[11px]">What was it for?</Label>
                <Input
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  placeholder="Generator diesel — September"
                  required
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-[11px]">Amount</Label>
                <Input
                  type="number"
                  step="0.01"
                  min="0.01"
                  value={form.amount}
                  onChange={(e) => setForm({ ...form, amount: e.target.value })}
                  placeholder="25000"
                  required
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-[11px]">Date</Label>
                <Input
                  type="date"
                  value={form.expense_date}
                  onChange={(e) => setForm({ ...form, expense_date: e.target.value })}
                  required
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-[11px]">Paid with</Label>
                <select
                  className="flex h-9 w-full rounded-xl border border-border/80 bg-background/50 px-3 text-[13px] shadow-sm"
                  value={form.payment_method}
                  onChange={(e) => setForm({ ...form, payment_method: e.target.value })}
                >
                  {PAYMENT_METHODS.map((m) => (
                    <option key={m} value={m}>
                      {m.replace("_", " ")}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-[11px]">Category</Label>
                <select
                  className="flex h-9 w-full rounded-xl border border-border/80 bg-background/50 px-3 text-[13px] shadow-sm"
                  value={form.category_id}
                  onChange={(e) => setForm({ ...form, category_id: e.target.value })}
                >
                  <option value="">Uncategorised</option>
                  {categories.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-[11px]">Account</Label>
                <select
                  className="flex h-9 w-full rounded-xl border border-border/80 bg-background/50 px-3 text-[13px] shadow-sm"
                  value={form.cash_account_id}
                  onChange={(e) => setForm({ ...form, cash_account_id: e.target.value })}
                >
                  <option value="">Default account</option>
                  {accounts.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name} ({a.kind.replace("_", " ")})
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-[11px]">Payee (optional)</Label>
                <Input
                  value={form.payee}
                  onChange={(e) => setForm({ ...form, payee: e.target.value })}
                  placeholder="Total Energies"
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-[11px]">Reference (optional)</Label>
                <Input
                  value={form.reference}
                  onChange={(e) => setForm({ ...form, reference: e.target.value })}
                  placeholder="Cheque / transfer no."
                />
              </div>
              <div className="flex flex-col justify-end gap-2 text-[12px]">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={form.requires_approval}
                    onChange={(e) => setForm({ ...form, requires_approval: e.target.checked })}
                  />
                  Needs approval before payment
                </label>
                <label className={cn("flex items-center gap-2", form.requires_approval && "opacity-40")}>
                  <input
                    type="checkbox"
                    disabled={form.requires_approval}
                    checked={form.mark_paid && !form.requires_approval}
                    onChange={(e) => setForm({ ...form, mark_paid: e.target.checked })}
                  />
                  Already paid (petty cash)
                </label>
              </div>
              <div className="flex items-end gap-2 lg:col-span-3">
                <Button type="submit" disabled={createExpense.isPending}>
                  {createExpense.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                  Save expense
                </Button>
                <Button type="button" variant="ghost" onClick={() => setShowForm(false)}>
                  Cancel
                </Button>
              </div>
              {error && <p className="text-[11.5px] text-destructive lg:col-span-3">{error}</p>}
            </form>

            <div className="flex flex-wrap items-end gap-2 border-t border-border/40 pt-4">
              <div className="space-y-1.5">
                <Label className="text-[11px]">Add an expense category</Label>
                <Input
                  value={newCategory}
                  onChange={(e) => setNewCategory(e.target.value)}
                  placeholder="Fuel & power"
                  className="w-56"
                />
              </div>
              <Button
                type="button"
                variant="outline"
                disabled={!newCategory.trim() || createCategory.isPending}
                onClick={() =>
                  createCategory.mutate(
                    { name: newCategory.trim() },
                    { onSuccess: () => setNewCategory("") },
                  )
                }
              >
                Add category
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <Card className="premium-card">
        <CardHeader className="flex-row items-center justify-between gap-4 space-y-0">
          <CardTitle>Expense ledger</CardTitle>
          <div className="flex gap-1.5">
            {STATUS_FILTERS.map((s) => (
              <button
                key={s || "all"}
                onClick={() => setStatus(s)}
                className={cn(
                  "rounded-lg px-2.5 py-1 text-[11.5px] font-medium capitalize transition-colors",
                  status === s
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:bg-accent/50",
                )}
              >
                {s || "all"}
              </button>
            ))}
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <Skeleton className="h-40 w-full" />
          ) : rows.length === 0 ? (
            <p className="py-10 text-center text-[13px] text-muted-foreground/70">
              No expenses recorded{status ? ` with status “${status}”` : ""} yet.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-[13px]">
                <thead>
                  <tr className="border-b border-border/40 text-left text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground/60">
                    <th className="pb-2.5">Date</th>
                    <th className="pb-2.5">Voucher</th>
                    <th className="pb-2.5">Description</th>
                    <th className="pb-2.5">Category</th>
                    <th className="pb-2.5">Account</th>
                    <th className="pb-2.5 text-right">Amount</th>
                    <th className="pb-2.5">Status</th>
                    {canManage && <th className="pb-2.5 text-right">Actions</th>}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr
                      key={row.id}
                      className="border-b border-border/30 last:border-0 transition-colors hover:bg-accent/40"
                    >
                      <td className="py-3 text-muted-foreground">{row.expense_date}</td>
                      <td className="py-3 font-mono text-[11px] text-muted-foreground">
                        {row.voucher_number}
                      </td>
                      <td className="py-3">
                        <p className="font-medium">{row.description}</p>
                        {row.payee && (
                          <p className="text-[11px] text-muted-foreground">to {row.payee}</p>
                        )}
                      </td>
                      <td className="py-3 text-muted-foreground">{row.category_name ?? "—"}</td>
                      <td className="py-3 text-muted-foreground">{row.cash_account_name ?? "—"}</td>
                      <td className="py-3 text-right font-medium tabular-nums">
                        {formatMoney(row.amount, row.currency)}
                      </td>
                      <td className="py-3">
                        <span
                          className={cn(
                            "inline-flex rounded-full px-2 py-0.5 text-[11px] font-semibold capitalize",
                            statusChip(row.status),
                          )}
                        >
                          {row.status}
                        </span>
                      </td>
                      {canManage && (
                        <td className="py-3">
                          <div className="flex items-center justify-end gap-1.5">
                            {(row.status === "draft" || row.status === "rejected") && (
                              <Button
                                size="sm"
                                variant="outline"
                                className="gap-1"
                                disabled={approveExpense.isPending}
                                onClick={() => approveExpense.mutate(row.id)}
                              >
                                <CheckCircle2 className="h-3.5 w-3.5" /> Approve
                              </Button>
                            )}
                            {row.status !== "paid" && row.status !== "rejected" && (
                              <Button
                                size="sm"
                                className="gap-1"
                                disabled={payExpense.isPending}
                                onClick={() => payExpense.mutate(row.id)}
                              >
                                Pay
                              </Button>
                            )}
                            {row.status !== "paid" && (
                              <>
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  disabled={rejectExpense.isPending}
                                  onClick={() =>
                                    rejectExpense.mutate({
                                      expenseId: row.id,
                                      reason: "Rejected by accountant",
                                    })
                                  }
                                >
                                  <XCircle className="h-3.5 w-3.5" />
                                </Button>
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  disabled={deleteExpense.isPending}
                                  onClick={() => deleteExpense.mutate(row.id)}
                                >
                                  <Trash2 className="h-3.5 w-3.5" />
                                </Button>
                              </>
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
    </div>
  );
}
