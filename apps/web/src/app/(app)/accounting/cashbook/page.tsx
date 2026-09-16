"use client";

import { Banknote, Check, Loader2, Plus } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useCashAccounts,
  useCashbook,
  useCreateCashAccount,
  useReconcileCashbookEntry,
} from "@/hooks/use-api";
import { useAuth } from "@/providers/auth-provider";
import { cn, formatMoney, todayIso } from "@/lib/utils";

export default function CashbookPage() {
  const { activeSchool } = useAuth();
  const permissions = activeSchool?.permissions ?? [];
  const canReconcile = permissions.includes("accounting.reconcile");

  const [accountId, setAccountId] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [onlyUnreconciled, setOnlyUnreconciled] = useState(false);

  const { data: accounts = [] } = useCashAccounts();
  const { data: book, isLoading } = useCashbook({
    cashAccountId: accountId || undefined,
    dateFrom: dateFrom || undefined,
    dateTo: dateTo || undefined,
    onlyUnreconciled,
  });
  const reconcile = useReconcileCashbookEntry();
  const createAccount = useCreateCashAccount();

  const currency = accounts[0]?.currency ?? "NGN";
  const [showAccountForm, setShowAccountForm] = useState(false);
  const [accountForm, setAccountForm] = useState({
    name: "",
    kind: "bank",
    bank_name: "",
    account_number: "",
    opening_balance: "0",
    is_default: false,
  });

  function submitAccount(event: React.FormEvent) {
    event.preventDefault();
    createAccount.mutate(
      {
        name: accountForm.name,
        kind: accountForm.kind as "bank" | "cash" | "petty_cash",
        bank_name: accountForm.bank_name || null,
        account_number: accountForm.account_number || null,
        opening_balance: Number(accountForm.opening_balance) || 0,
        is_default: accountForm.is_default,
      },
      {
        onSuccess: () => {
          setAccountForm({
            name: "",
            kind: "bank",
            bank_name: "",
            account_number: "",
            opening_balance: "0",
            is_default: false,
          });
          setShowAccountForm(false);
        },
      },
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-[22px] font-bold tracking-tight text-foreground">Cashbook</h1>
          <p className="mt-1 text-[13px] text-muted-foreground">
            Every movement in and out of the school&apos;s accounts, matched line by line to the
            bank statement.
          </p>
        </div>
        {canReconcile && (
          <Button variant="outline" onClick={() => setShowAccountForm((v) => !v)} className="gap-1.5">
            <Plus className="h-4 w-4" /> Add account
          </Button>
        )}
      </div>

      {/* Cash accounts */}
      <Card className="premium-card">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Banknote className="h-4 w-4 text-primary" /> Cash &amp; bank accounts
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {accounts.length === 0 ? (
            <p className="text-[13px] text-muted-foreground">
              No accounts yet. The first fee payment creates a default cash account, or add a bank
              account above.
            </p>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {accounts.map((account) => (
                <div
                  key={account.id}
                  className="rounded-xl border border-border/50 bg-muted/20 p-4"
                >
                  <div className="flex items-center justify-between gap-2">
                    <p className="truncate text-[13px] font-semibold">{account.name}</p>
                    {account.is_default && (
                      <span className="shrink-0 rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-semibold text-primary">
                        Default
                      </span>
                    )}
                  </div>
                  <p className="mt-0.5 text-[11px] capitalize text-muted-foreground">
                    {account.kind.replace("_", " ")}
                    {account.bank_name ? ` · ${account.bank_name}` : ""}
                    {account.account_number ? ` · ${account.account_number}` : ""}
                  </p>
                  <p className="mt-2 text-lg font-bold tabular-nums">
                    {formatMoney(account.balance, account.currency)}
                  </p>
                  <p className="text-[11px] text-muted-foreground">
                    Opening {formatMoney(account.opening_balance, account.currency)}
                  </p>
                </div>
              ))}
            </div>
          )}

          {showAccountForm && canReconcile && (
            <form
              onSubmit={submitAccount}
              className="grid gap-3 rounded-xl border border-border/40 bg-muted/20 p-4 sm:grid-cols-2 lg:grid-cols-4"
            >
              <div className="space-y-1.5">
                <Label className="text-[11px]">Name</Label>
                <Input
                  value={accountForm.name}
                  onChange={(e) => setAccountForm({ ...accountForm, name: e.target.value })}
                  placeholder="Zenith Bank — Main"
                  required
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-[11px]">Kind</Label>
                <select
                  className="flex h-9 w-full rounded-xl border border-border/80 bg-background/50 px-3 text-[13px] shadow-sm"
                  value={accountForm.kind}
                  onChange={(e) => setAccountForm({ ...accountForm, kind: e.target.value })}
                >
                  {["bank", "cash", "petty_cash"].map((k) => (
                    <option key={k} value={k}>
                      {k.replace("_", " ")}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-[11px]">Bank (optional)</Label>
                <Input
                  value={accountForm.bank_name}
                  onChange={(e) => setAccountForm({ ...accountForm, bank_name: e.target.value })}
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-[11px]">Account no. (optional)</Label>
                <Input
                  value={accountForm.account_number}
                  onChange={(e) =>
                    setAccountForm({ ...accountForm, account_number: e.target.value })
                  }
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-[11px]">Opening balance</Label>
                <Input
                  type="number"
                  step="0.01"
                  value={accountForm.opening_balance}
                  onChange={(e) =>
                    setAccountForm({ ...accountForm, opening_balance: e.target.value })
                  }
                />
              </div>
              <label className="flex items-end gap-2 pb-2 text-[12px]">
                <input
                  type="checkbox"
                  checked={accountForm.is_default}
                  onChange={(e) =>
                    setAccountForm({ ...accountForm, is_default: e.target.checked })
                  }
                />
                Make this the default account
              </label>
              <div className="flex items-end">
                <Button type="submit" disabled={createAccount.isPending}>
                  {createAccount.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                  Add account
                </Button>
              </div>
            </form>
          )}
        </CardContent>
      </Card>

      {/* The book itself */}
      <Card className="premium-card">
        <CardHeader className="flex-wrap items-end justify-between gap-4 space-y-0">
          <CardTitle>Movements</CardTitle>
          <div className="flex flex-wrap items-end gap-3">
            <div className="space-y-1.5">
              <Label className="text-[11px] text-muted-foreground/70">Account</Label>
              <select
                className="flex h-9 min-w-[180px] rounded-xl border border-border/80 bg-background/50 px-3 text-[13px] shadow-sm"
                value={accountId}
                onChange={(e) => setAccountId(e.target.value)}
              >
                <option value="">All accounts</option>
                {accounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-[11px] text-muted-foreground/70">From</Label>
              <Input
                type="date"
                value={dateFrom}
                max={todayIso()}
                onChange={(e) => setDateFrom(e.target.value)}
                className="w-[150px]"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-[11px] text-muted-foreground/70">To</Label>
              <Input
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="w-[150px]"
              />
            </div>
            <label className="flex h-9 items-center gap-2 text-[12px]">
              <input
                type="checkbox"
                checked={onlyUnreconciled}
                onChange={(e) => setOnlyUnreconciled(e.target.checked)}
              />
              Unreconciled only
            </label>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {book && (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
              {[
                { label: "Opening", value: book.opening, tone: "text-foreground" },
                { label: "Money in", value: book.total_in, tone: "text-success" },
                { label: "Money out", value: book.total_out, tone: "text-destructive" },
                { label: "Closing", value: book.closing, tone: "text-foreground" },
              ].map((item) => (
                <div key={item.label} className="rounded-xl border border-border/50 bg-muted/20 p-3.5">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/60">
                    {item.label}
                  </p>
                  <p className={cn("mt-1 text-lg font-bold tabular-nums", item.tone)}>
                    {formatMoney(item.value, currency)}
                  </p>
                </div>
              ))}
              <div className="rounded-xl border border-border/50 bg-muted/20 p-3.5">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/60">
                  Unreconciled
                </p>
                <p className="mt-1 text-lg font-bold tabular-nums text-primary">
                  {book.unreconciled_count}
                  <span className="ml-1 text-[11px] font-medium text-muted-foreground">
                    of {book.lines.length}
                  </span>
                </p>
              </div>
            </div>
          )}

          {isLoading ? (
            <Skeleton className="h-48 w-full" />
          ) : !book || book.lines.length === 0 ? (
            <p className="py-10 text-center text-[13px] text-muted-foreground/70">
              Nothing has moved in this window yet.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-[13px]">
                <thead>
                  <tr className="border-b border-border/40 text-left text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground/60">
                    <th className="pb-2.5">Date</th>
                    <th className="pb-2.5">Description</th>
                    <th className="pb-2.5">Reference</th>
                    <th className="pb-2.5">Account</th>
                    <th className="pb-2.5 text-right">In</th>
                    <th className="pb-2.5 text-right">Out</th>
                    <th className="pb-2.5 text-center">Bank reconciled</th>
                  </tr>
                </thead>
                <tbody>
                  {book.lines.map((line, index) => {
                    const key = `${line.source_type}-${line.source_id ?? index}`;
                    const reconcilable = line.source_type !== "opening" && !!line.source_id;
                    return (
                      <tr
                        key={key}
                        className="border-b border-border/30 last:border-0 transition-colors hover:bg-accent/40"
                      >
                        <td className="py-3 text-muted-foreground">{line.entry_date ?? "—"}</td>
                        <td className="py-3">
                          <p className="font-medium">{line.description}</p>
                          <p className="text-[11px] capitalize text-muted-foreground">
                            {line.source_type}
                          </p>
                        </td>
                        <td className="py-3 font-mono text-[11px] text-muted-foreground">
                          {line.reference ?? "—"}
                        </td>
                        <td className="py-3 text-muted-foreground">
                          {line.cash_account_name ?? "—"}
                        </td>
                        <td className="py-3 text-right tabular-nums text-success">
                          {line.direction === "in" ? formatMoney(line.amount, currency) : "—"}
                        </td>
                        <td className="py-3 text-right tabular-nums text-destructive">
                          {line.direction === "out" ? formatMoney(line.amount, currency) : "—"}
                        </td>
                        <td className="py-3 text-center">
                          {reconcilable && canReconcile ? (
                            <button
                              onClick={() =>
                                reconcile.mutate({
                                  source_type: line.source_type as
                                    | "payment"
                                    | "expense"
                                    | "refund",
                                  source_id: line.source_id!,
                                  reconciled: !line.reconciled,
                                  bank_reference: line.bank_reference,
                                })
                              }
                              disabled={reconcile.isPending}
                              title={
                                line.bank_reference
                                  ? `Bank ref: ${line.bank_reference}`
                                  : line.reconciled
                                    ? "Mark as not reconciled"
                                    : "Mark as reconciled"
                              }
                              className={cn(
                                "mx-auto flex h-6 w-6 items-center justify-center rounded-md border transition-colors",
                                line.reconciled
                                  ? "border-success/40 bg-success/10 text-success"
                                  : "border-border text-muted-foreground/40 hover:border-primary/40 hover:text-primary",
                              )}
                            >
                              {line.reconciled ? <Check className="h-3.5 w-3.5" /> : null}
                            </button>
                          ) : (
                            <span className="text-[11px] text-muted-foreground/40">
                              {line.source_type === "opening" ? "—" : ""}
                            </span>
                          )}
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
    </div>
  );
}
