"use client";

import { motion } from "framer-motion";
import { Download, Loader2, TrendingDown, TrendingUp } from "lucide-react";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useCashPosition,
  useCollectionReport,
  useIncomeExpenditure,
  useSessions,
  useTerms,
} from "@/hooks/use-api";
import { useAuth } from "@/providers/auth-provider";
import { downloadPdf } from "@/lib/pdf";
import { cn, formatMoney } from "@/lib/utils";

const ease = [0.25, 0.46, 0.45, 0.94] as const;

export default function ReportsPage() {
  const { activeSchool } = useAuth();
  const [termId, setTermId] = useState("");
  const reportRef = useRef<HTMLDivElement>(null);
  const [downloading, setDownloading] = useState(false);

  const { data: sessions = [] } = useSessions();
  const sessionId = sessions.find((s) => s.is_current)?.id ?? sessions[0]?.id ?? null;
  const { data: terms = [] } = useTerms(sessionId);

  const opts = { termId: termId || undefined, sessionId: sessionId ?? undefined };
  const { data: ie, isLoading: loadingIe } = useIncomeExpenditure(opts);
  const { data: collection, isLoading: loadingCollection } = useCollectionReport(opts);
  const { data: position, isLoading: loadingPosition } = useCashPosition();

  // Every report carries the tenant's own currency, so a non-NGN school reads
  // its own money and never someone else's symbol.
  const currency = ie?.currency ?? collection?.currency ?? position?.currency ?? "NGN";

  async function handleDownload() {
    if (!reportRef.current) return;
    setDownloading(true);
    try {
      await downloadPdf(
        reportRef.current,
        `financial-report-${ie?.period_label?.replace(/[^\w]+/g, "-") ?? "clearis"}.pdf`,
      );
    } finally {
      setDownloading(false);
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-[22px] font-bold tracking-tight text-foreground">
            Financial reports
          </h1>
          <p className="mt-1 text-[13px] text-muted-foreground">
            Income &amp; expenditure, fee collection and cash position for{" "}
            {activeSchool?.school_name}.
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <div className="space-y-1.5">
            <Label className="text-[11px] text-muted-foreground/70">Period</Label>
            <select
              className="flex h-9 min-w-[190px] rounded-xl border border-border/80 bg-background/50 px-3 text-[13px] shadow-sm"
              value={termId}
              onChange={(e) => setTermId(e.target.value)}
            >
              <option value="">Current term</option>
              {terms.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </div>
          <Button variant="outline" onClick={handleDownload} disabled={downloading || !ie}>
            {downloading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Download className="h-4 w-4" />
            )}
            Download PDF
          </Button>
        </div>
      </div>

      <div ref={reportRef} className="space-y-5 bg-background p-1">
        {/* Income & expenditure */}
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.28, ease }}>
          <Card className="premium-card">
            <CardHeader>
              <CardTitle>Income &amp; expenditure</CardTitle>
              {ie && (
                <p className="text-[12px] text-muted-foreground">Period: {ie.period_label}</p>
              )}
            </CardHeader>
            <CardContent>
              {loadingIe || !ie ? (
                <Skeleton className="h-56 w-full" />
              ) : (
                <div className="grid gap-6 lg:grid-cols-2">
                  <div className="space-y-3">
                    <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-success">
                      <TrendingUp className="h-3.5 w-3.5" /> Income
                    </div>
                    <div className="space-y-1.5 text-[13px]">
                      <div className="flex justify-between border-b border-border/30 py-1.5">
                        <span className="text-muted-foreground">Fees collected</span>
                        <span className="font-medium tabular-nums">
                          {formatMoney(ie.fee_collections, currency)}
                        </span>
                      </div>
                      <div className="flex justify-between border-b border-border/30 py-1.5">
                        <span className="text-muted-foreground">Other income</span>
                        <span className="font-medium tabular-nums">
                          {formatMoney(ie.other_income, currency)}
                        </span>
                      </div>
                      <div className="flex justify-between py-1.5 text-[14px] font-bold">
                        <span>Total income</span>
                        <span className="tabular-nums text-success">
                          {formatMoney(ie.total_income, currency)}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="space-y-3">
                    <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-destructive">
                      <TrendingDown className="h-3.5 w-3.5" /> Expenditure
                    </div>
                    <div className="space-y-1.5 text-[13px]">
                      {ie.expenses_by_category.length === 0 ? (
                        <p className="text-muted-foreground">No expenses paid in this period.</p>
                      ) : (
                        ie.expenses_by_category.map((row) => (
                          <div
                            key={row.category}
                            className="flex justify-between border-b border-border/30 py-1.5"
                          >
                            <span className="text-muted-foreground">{row.category}</span>
                            <span className="font-medium tabular-nums">
                              {formatMoney(row.amount, currency)}
                            </span>
                          </div>
                        ))
                      )}
                      <div className="flex justify-between py-1.5 text-[14px] font-bold">
                        <span>Total expenditure</span>
                        <span className="tabular-nums text-destructive">
                          {formatMoney(ie.total_expenditure, currency)}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div
                    className={cn(
                      "rounded-xl border p-4 lg:col-span-2",
                      ie.surplus >= 0 ? "border-success/30 bg-success/5" : "border-destructive/30 bg-destructive/5",
                    )}
                  >
                    <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/70">
                      {ie.surplus >= 0 ? "Surplus for the period" : "Deficit for the period"}
                    </p>
                    <p
                      className={cn(
                        "mt-1 text-2xl font-bold tabular-nums",
                        ie.surplus >= 0 ? "text-success" : "text-destructive",
                      )}
                    >
                      {formatMoney(Math.abs(ie.surplus), currency)}
                    </p>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>

        {/* Collection by class */}
        <Card className="premium-card">
          <CardHeader>
            <CardTitle>Fee collection by class</CardTitle>
          </CardHeader>
          <CardContent>
            {loadingCollection || !collection ? (
              <Skeleton className="h-40 w-full" />
            ) : collection.rows.length === 0 ? (
              <p className="py-8 text-center text-[13px] text-muted-foreground/70">
                No invoices raised in this period.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-[13px]">
                  <thead>
                    <tr className="border-b border-border/40 text-left text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground/60">
                      <th className="pb-2.5">Class</th>
                      <th className="pb-2.5 text-right">Students</th>
                      <th className="pb-2.5 text-right">Invoiced</th>
                      <th className="pb-2.5 text-right">Collected</th>
                      <th className="pb-2.5 text-right">Outstanding</th>
                      <th className="pb-2.5 text-right">Rate</th>
                    </tr>
                  </thead>
                  <tbody>
                    {collection.rows.map((row) => (
                      <tr
                        key={row.arm_id ?? row.arm_name ?? "unassigned"}
                        className="border-b border-border/30 last:border-0 transition-colors hover:bg-accent/40"
                      >
                        <td className="py-3 font-medium">{row.arm_name ?? "Unassigned"}</td>
                        <td className="py-3 text-right tabular-nums text-muted-foreground">
                          {row.students}
                        </td>
                        <td className="py-3 text-right tabular-nums">
                          {formatMoney(row.invoiced, currency)}
                        </td>
                        <td className="py-3 text-right tabular-nums text-success">
                          {formatMoney(row.collected, currency)}
                        </td>
                        <td className="py-3 text-right tabular-nums text-destructive">
                          {formatMoney(row.outstanding, currency)}
                        </td>
                        <td className="py-3 text-right font-semibold tabular-nums">
                          {row.collection_rate}%
                        </td>
                      </tr>
                    ))}
                    <tr className="border-t border-border/60 font-semibold">
                      <td className="py-3">Total</td>
                      <td className="py-3" />
                      <td className="py-3 text-right tabular-nums">
                        {formatMoney(collection.total_invoiced, currency)}
                      </td>
                      <td className="py-3 text-right tabular-nums text-success">
                        {formatMoney(collection.total_collected, currency)}
                      </td>
                      <td className="py-3 text-right tabular-nums text-destructive">
                        {formatMoney(collection.total_outstanding, currency)}
                      </td>
                      <td className="py-3 text-right tabular-nums">
                        {collection.collection_rate}%
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Cash position */}
        <Card className="premium-card">
          <CardHeader>
            <CardTitle>Cash &amp; bank position</CardTitle>
          </CardHeader>
          <CardContent>
            {loadingPosition || !position ? (
              <Skeleton className="h-32 w-full" />
            ) : position.rows.length === 0 ? (
              <p className="py-8 text-center text-[13px] text-muted-foreground/70">
                No cash or bank accounts yet.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-[13px]">
                  <thead>
                    <tr className="border-b border-border/40 text-left text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground/60">
                      <th className="pb-2.5">Account</th>
                      <th className="pb-2.5">Kind</th>
                      <th className="pb-2.5 text-right">Opening</th>
                      <th className="pb-2.5 text-right">In</th>
                      <th className="pb-2.5 text-right">Out</th>
                      <th className="pb-2.5 text-right">Balance</th>
                      <th className="pb-2.5 text-right">Unreconciled</th>
                    </tr>
                  </thead>
                  <tbody>
                    {position.rows.map((row) => (
                      <tr
                        key={row.cash_account_id}
                        className="border-b border-border/30 last:border-0 transition-colors hover:bg-accent/40"
                      >
                        <td className="py-3 font-medium">{row.name}</td>
                        <td className="py-3 capitalize text-muted-foreground">
                          {row.kind.replace("_", " ")}
                        </td>
                        <td className="py-3 text-right tabular-nums text-muted-foreground">
                          {formatMoney(row.opening_balance, currency)}
                        </td>
                        <td className="py-3 text-right tabular-nums text-success">
                          {formatMoney(row.total_in, currency)}
                        </td>
                        <td className="py-3 text-right tabular-nums text-destructive">
                          {formatMoney(row.total_out, currency)}
                        </td>
                        <td className="py-3 text-right font-semibold tabular-nums">
                          {formatMoney(row.balance, currency)}
                        </td>
                        <td className="py-3 text-right tabular-nums text-warning">
                          {row.unreconciled_amount
                            ? formatMoney(row.unreconciled_amount, currency)
                            : "—"}
                        </td>
                      </tr>
                    ))}
                    <tr className="border-t border-border/60 font-semibold">
                      <td className="py-3">Total</td>
                      <td className="py-3" />
                      <td className="py-3" />
                      <td className="py-3" />
                      <td className="py-3" />
                      <td className="py-3 text-right tabular-nums">
                        {formatMoney(position.total_balance, currency)}
                      </td>
                      <td className="py-3 text-right tabular-nums text-warning">
                        {formatMoney(position.total_unreconciled, currency)}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
