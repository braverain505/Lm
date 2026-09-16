"use client";

import { motion, AnimatePresence } from "framer-motion";
import { Download, Loader2, Mail, Printer, Share2, X } from "lucide-react";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useEmailReceipt, useReceipt } from "@/hooks/use-api";
import { downloadPdf } from "@/lib/pdf";

const CURRENCY_SYMBOLS: Record<string, string> = { NGN: "₦", USD: "$", GBP: "£", EUR: "€" };

function naira(amount: number | null | undefined, currency = "NGN") {
  const sym = CURRENCY_SYMBOLS[currency] ?? "";
  return `${sym}${(amount ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

/** wa.me wants digits only, with a country code. */
function whatsappNumber(phone: string | null | undefined) {
  const digits = (phone ?? "").replace(/[^\d]/g, "");
  if (!digits) return "";
  // A local Nigerian number (0XXXXXXXXXX) needs the 234 country code.
  if (digits.startsWith("0") && digits.length === 11) return `234${digits.slice(1)}`;
  return digits;
}

export function ReceiptDialog({
  paymentId,
  onClose,
}: {
  paymentId: string | null;
  onClose: () => void;
}) {
  const { data: receipt, isLoading } = useReceipt(paymentId);
  const emailReceipt = useEmailReceipt();
  const contentRef = useRef<HTMLDivElement>(null);
  const [printed, setPrinted] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [notice, setNotice] = useState<{ tone: "ok" | "warn" | "error"; text: string } | null>(null);

  if (!paymentId) return null;

  const currency = receipt?.school.currency ?? "NGN";
  const student = receipt?.student;
  const guardianPhone = student?.guardian_phone ?? null;
  const guardianEmail = student?.guardian_email ?? null;

  async function handleDownload() {
    if (!contentRef.current || !receipt) return;
    setDownloading(true);
    setNotice(null);
    try {
      await downloadPdf(contentRef.current, `receipt-${receipt.receipt_number ?? "payment"}.pdf`);
    } catch {
      setNotice({ tone: "error", text: "Could not generate the PDF. Try the Print button instead." });
    } finally {
      setDownloading(false);
    }
  }

  function handleWhatsApp() {
    if (!receipt) return;
    const lines = [
      `*${receipt.school.name ?? "School"}* — Payment Receipt`,
      `Receipt no.: ${receipt.receipt_number ?? "—"}`,
      `Student: ${student?.full_name ?? ""}`,
      `Amount paid: ${naira(receipt.paid_total, currency)}`,
      receipt.balance_due > 0
        ? `Balance due: ${naira(receipt.balance_due, currency)}`
        : "Status: fully paid",
      "",
      "Thank you for your payment.",
    ];
    const number = whatsappNumber(guardianPhone);
    const url = `https://wa.me/${number}?text=${encodeURIComponent(lines.join("\n"))}`;
    window.open(url, "_blank", "noopener,noreferrer");
  }

  function handleEmail() {
    if (!receipt) return;
    setNotice(null);
    emailReceipt.mutate(
      { paymentId: paymentId!, to: null },
      {
        onSuccess: (result) => {
          if (result.delivered) {
            setNotice({ tone: "ok", text: `Receipt emailed to ${result.recipient}.` });
          } else if (result.dev_skipped) {
            setNotice({
              tone: "warn",
              text: `Email is not configured on this deployment, so nothing was sent to ${result.recipient}.`,
            });
          } else {
            setNotice({ tone: "ok", text: `Sent to ${result.recipient}.` });
          }
        },
        onError: (error) =>
          setNotice({
            tone: "error",
            text: error instanceof Error ? error.message : "Could not send the email.",
          }),
      },
    );
  }

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
          <div className="flex flex-wrap items-center justify-between gap-3 border-b px-5 py-3 print:hidden">
            <div>
              <h3 className="text-base font-semibold">Payment receipt</h3>
              <p className="text-xs text-muted-foreground">
                Download, share or email this official receipt.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button size="sm" variant="outline" onClick={handleDownload} disabled={downloading || !receipt}>
                {downloading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
                PDF
              </Button>
              <Button size="sm" variant="outline" onClick={handleWhatsApp} disabled={!receipt}>
                <Share2 className="h-4 w-4" /> WhatsApp
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={handleEmail}
                disabled={!receipt || emailReceipt.isPending}
                title={guardianEmail ? `Send to ${guardianEmail}` : "No guardian email on file — you will be asked for one"}
              >
                {emailReceipt.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Mail className="h-4 w-4" />}
                Email
              </Button>
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
                aria-label="Close"
              >
                <X className="h-5 w-5" />
              </motion.button>
            </div>
          </div>

          {notice && (
            <div
              className={`px-5 py-2 text-[12px] print:hidden ${
                notice.tone === "ok"
                  ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300"
                  : notice.tone === "warn"
                    ? "bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300"
                    : "bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-300"
              }`}
            >
              {notice.text}
            </div>
          )}

          <div className="overflow-y-auto px-6 py-6 print:overflow-visible">
            {isLoading || !receipt ? (
              <div className="space-y-3">
                <Skeleton className="h-6 w-1/2" />
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-40 w-full" />
              </div>
            ) : (
              <div ref={contentRef} className="space-y-6 bg-background p-1">
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
                      {naira(receipt.amount_paid, currency)}
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
                    {student?.guardian_name && (
                      <p className="mt-1 text-xs text-muted-foreground">
                        Guardian: {student.guardian_name}
                      </p>
                    )}
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
                            {naira(p.amount, currency)}
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
                        {naira(receipt.paid_total, currency)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Invoice total</span>
                      <span className="tabular-nums">{naira(receipt.invoice_total, currency)}</span>
                    </div>
                    <div className="flex justify-between border-t pt-1.5">
                      <span className="font-medium">Balance due</span>
                      <span className={`font-bold tabular-nums ${receipt.balance_due > 0 ? "text-destructive" : "text-success"}`}>
                        {naira(receipt.balance_due, currency)}
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
