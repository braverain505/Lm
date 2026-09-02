"use client";

import { motion, AnimatePresence } from "framer-motion";
import { Printer, X } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useReceipt } from "@/hooks/use-api";

const CURRENCY_SYMBOLS: Record<string, string> = { NGN: "₦", USD: "$", GBP: "£", EUR: "€" };

function naira(amount: number | null | undefined, currency = "NGN") {
  const sym = CURRENCY_SYMBOLS[currency] ?? "";
  return `${sym}${(amount ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function ReceiptDialog({
  paymentId,
  onClose,
}: {
  paymentId: string | null;
  onClose: () => void;
}) {
  const { data: receipt, isLoading } = useReceipt(paymentId);
  const [printed, setPrinted] = useState(false);

  if (!paymentId) return null;

  return (
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-50 flex items-center justify-center p-4 print:bg-white"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.2 }}
      >
        <motion.div
          className="absolute inset-0 bg-black/50 backdrop-blur-sm"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
        />
        <motion.div
          className="receipt-print-area relative flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden rounded-xl border bg-background shadow-xl print:max-h-none print:overflow-visible print:shadow-none"
          initial={{ opacity: 0, scale: 0.95, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 20 }}
          transition={{ duration: 0.25, ease: [0.25, 0.46, 0.45, 0.94] }}
        >
          {/* Toolbar (hidden when printing) */}
          <div className="flex items-center justify-between gap-3 border-b px-5 py-3 print:hidden">
            <div>
              <h3 className="text-base font-semibold">Payment receipt</h3>
              <p className="text-xs text-muted-foreground">
                Printable official receipt for this payment.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  setPrinted(true);
                  window.print();
                }}
              >
                <Printer className="h-4 w-4" /> Print
              </Button>
              <motion.button
                onClick={onClose}
                className="text-muted-foreground hover:text-foreground"
                whileHover={{ scale: 1.1, rotate: 90 }}
                whileTap={{ scale: 0.9 }}
                transition={{ duration: 0.15 }}
              >
                <X className="h-5 w-5" />
              </motion.button>
            </div>
          </div>

        <div className="overflow-y-auto px-6 py-6 print:overflow-visible">
          {isLoading || !receipt ? (
            <div className="space-y-3">
              <Skeleton className="h-6 w-1/2" />
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-40 w-full" />
            </div>
          ) : (
            <div className="space-y-6">
              {/* School header */}
              <div className="flex items-center gap-4 border-b pb-5">
                {receipt.school.logo_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={receipt.school.logo_url}
                    alt={receipt.school.name ?? "School logo"}
                    className="h-14 w-14 rounded-full object-cover"
                  />
                ) : (
                  <div className="flex h-14 w-14 items-center justify-center rounded-full bg-primary/10 text-lg font-bold text-primary">
                    {(receipt.school.name ?? "S").charAt(0)}
                  </div>
                )}
                <div className="min-w-0">
                  <p className="text-lg font-bold leading-tight">{receipt.school.name}</p>
                  <p className="text-xs text-muted-foreground">{receipt.school.address}</p>
                  <p className="text-xs text-muted-foreground">
                    {receipt.school.phone} {receipt.school.email && `· ${receipt.school.email}`}
                  </p>
                </div>
              </div>

              {/* Receipt title */}
              <div className="flex items-end justify-between gap-4">
                <div>
                  <p className="text-sm font-semibold uppercase tracking-widest text-muted-foreground">
                    Official Receipt
                  </p>
                  <p className="text-xl font-bold">
                    {naira(receipt.amount_paid, receipt.school.currency)}
                  </p>
                </div>
                <div className="text-right text-xs text-muted-foreground">
                  <p>Receipt no.</p>
                  <p className="font-mono text-sm font-semibold text-foreground">
                    {receipt.receipt_number ?? "—"}
                  </p>
                  <p>{receipt.payment_date ?? ""}</p>
                </div>
              </div>

              {/* Student + invoice */}
              <div className="grid grid-cols-2 gap-4 rounded-lg border bg-muted/30 p-4 text-sm">
                <div>
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">Student</p>
                  <p className="font-semibold">{receipt.student.full_name}</p>
                  <p className="text-xs text-muted-foreground">{receipt.student.admission_no}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">Invoice</p>
                  <p className="font-mono text-xs font-semibold">{receipt.invoice_reference}</p>
                  <p className="text-xs text-muted-foreground">
                    {receipt.fee_structure_name ?? "Fee"} · {receipt.invoice_issue_date ?? ""}
                  </p>
                </div>
              </div>

              {/* Payments on this invoice */}
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Payments received
                </p>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                      <th className="pb-1.5 font-medium">Receipt no.</th>
                      <th className="pb-1.5 font-medium">Date</th>
                      <th className="pb-1.5 font-medium">Method</th>
                      <th className="pb-1.5 text-right font-medium">Amount</th>
                    </tr>
                  </thead>
                  <tbody>
                    {receipt.invoice_payments.map((p) => (
                      <tr key={p.receipt_number ?? p.payment_date} className="border-b last:border-0">
                        <td className="py-1.5 font-mono text-xs">{p.receipt_number ?? "—"}</td>
                        <td className="py-1.5">{p.payment_date ?? "—"}</td>
                        <td className="py-1.5 capitalize">{p.payment_method}</td>
                        <td className="py-1.5 text-right tabular-nums">
                          {naira(p.amount, receipt.school.currency)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Totals */}
              <div className="flex justify-end">
                <div className="w-64 space-y-1.5 rounded-lg border p-4 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Amount paid</span>
                    <span className="font-semibold tabular-nums">
                      {naira(receipt.paid_total, receipt.school.currency)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Invoice total</span>
                    <span className="tabular-nums">{naira(receipt.invoice_total, receipt.school.currency)}</span>
                  </div>
                  <div className="flex justify-between border-t pt-1.5">
                    <span className="font-medium">Balance due</span>
                    <span className={`font-bold tabular-nums ${receipt.balance_due > 0 ? "text-destructive" : "text-success"}`}>
                      {naira(receipt.balance_due, receipt.school.currency)}
                    </span>
                  </div>
                </div>
              </div>

              <p className="border-t pt-4 text-center text-xs text-muted-foreground">
                Thank you for your payment. This receipt was generated by Clearis.
              </p>
              {printed && (
                <p className="text-center text-[10px] text-muted-foreground print:block hidden">
                  Printed {new Date().toLocaleString()}
                </p>
              )}
            </div>
          )}
        </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}