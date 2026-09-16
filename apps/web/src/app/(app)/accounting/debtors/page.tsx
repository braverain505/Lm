"use client";

import { AlertTriangle, Mail, MessageCircle, Users } from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useArms, useDebtors, useSessions, useTerms } from "@/hooks/use-api";
import { useAuth } from "@/providers/auth-provider";
import { cn, formatMoney } from "@/lib/utils";

/** wa.me wants digits only, with a country code. */
function whatsappNumber(phone: string | null | undefined) {
  const digits = (phone ?? "").replace(/[^\d]/g, "");
  if (!digits) return "";
  if (digits.startsWith("0") && digits.length === 11) return `234${digits.slice(1)}`;
  return digits;
}

export default function DebtorsPage() {
  const { activeSchool } = useAuth();

  const [termId, setTermId] = useState("");
  const [armId, setArmId] = useState("");

  const { data: sessions = [] } = useSessions();
  const sessionId = sessions.find((s) => s.is_current)?.id ?? sessions[0]?.id ?? null;
  const { data: terms = [] } = useTerms(sessionId);
  const { data: arms = [] } = useArms(sessionId);

  const { data: debtors, isLoading } = useDebtors({
    termId: termId || undefined,
    armId: armId || undefined,
  });

  const buckets = debtors?.buckets ?? {};
  const rows = debtors?.rows ?? [];
  const currency = debtors?.currency ?? "NGN";

  const agingCards = useMemo(
    () => [
      { key: "current", label: "Not yet due", tone: "text-foreground" },
      { key: "1_30", label: "1–30 days", tone: "text-foreground" },
      { key: "31_60", label: "31–60 days", tone: "text-warning" },
      { key: "61_90", label: "61–90 days", tone: "text-destructive" },
      { key: "90_plus", label: "90+ days", tone: "text-destructive" },
    ],
    [],
  );

  function reminder(row: (typeof rows)[number]) {
    const number = whatsappNumber(row.guardian_phone);
    const lines = [
      `Dear ${row.guardian_name ?? "Parent/Guardian"},`,
      "",
      `Our records show an outstanding balance of ${formatMoney(row.balance, currency)} on ${
        row.full_name
      }'s (${row.admission_no}) school fees.`,
      row.oldest_due_date ? `The oldest unpaid invoice was due ${row.oldest_due_date}.` : "",
      "",
      "Kindly settle at your earliest convenience. Thank you.",
      `— ${activeSchool?.school_name ?? "The school"} accounts office`,
    ].filter(Boolean);
    window.open(
      `https://wa.me/${number}?text=${encodeURIComponent(lines.join("\n"))}`,
      "_blank",
      "noopener,noreferrer",
    );
  }

  function emailReminder(row: (typeof rows)[number]) {
    const subject = `Outstanding school fees for ${row.full_name}`;
    const body = [
      `Dear ${row.guardian_name ?? "Parent/Guardian"},`,
      "",
      `Our records show an outstanding balance of ${formatMoney(row.balance, currency)} on ${row.full_name}'s (${row.admission_no}) school fees.`,
      row.oldest_due_date ? `The oldest unpaid invoice was due ${row.oldest_due_date}.` : "",
      "",
      "Kindly settle at your earliest convenience. Thank you.",
      `— ${activeSchool?.school_name ?? "The school"} accounts office`,
    ]
      .filter(Boolean)
      .join("\n");
    window.location.href = `mailto:${row.guardian_email ?? ""}?subject=${encodeURIComponent(
      subject,
    )}&body=${encodeURIComponent(body)}`;
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-[22px] font-bold tracking-tight text-foreground">
            Debtors &amp; aging
          </h1>
          <p className="mt-1 text-[13px] text-muted-foreground">
            Who still owes fees, how overdue it is, and a reminder you can send in one tap.
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <div className="space-y-1.5">
            <Label className="text-[11px] text-muted-foreground/70">Term</Label>
            <select
              className="flex h-9 min-w-[160px] rounded-xl border border-border/80 bg-background/50 px-3 text-[13px] shadow-sm"
              value={termId}
              onChange={(e) => setTermId(e.target.value)}
            >
              <option value="">All terms</option>
              {terms.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5">
            <Label className="text-[11px] text-muted-foreground/70">Class</Label>
            <select
              className="flex h-9 min-w-[160px] rounded-xl border border-border/80 bg-background/50 px-3 text-[13px] shadow-sm"
              value={armId}
              onChange={(e) => setArmId(e.target.value)}
            >
              <option value="">All classes</option>
              {arms.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.full_name}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
        <Card className="premium-card lg:col-span-1">
          <CardContent className="p-4">
            <p className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground/60">
              Total owed
            </p>
            <p className="mt-1 text-xl font-bold tabular-nums text-destructive">
              {isLoading ? "…" : formatMoney(debtors?.total_outstanding ?? 0, currency)}
            </p>
            <p className="mt-0.5 text-[11px] text-muted-foreground">
              {debtors?.student_count ?? 0} student(s)
            </p>
          </CardContent>
        </Card>
        {agingCards.map((bucket) => (
          <Card key={bucket.key} className="premium-card">
            <CardContent className="p-4">
              <p className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground/60">
                {bucket.label}
              </p>
              <p className={cn("mt-1 text-xl font-bold tabular-nums", bucket.tone)}>
                {isLoading ? "…" : formatMoney(buckets[bucket.key] ?? 0, currency)}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card className="premium-card">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Users className="h-4 w-4 text-primary" /> Outstanding by student
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <Skeleton className="h-48 w-full" />
          ) : rows.length === 0 ? (
            <div className="flex flex-col items-center gap-2 py-12 text-center">
              <AlertTriangle className="h-5 w-5 text-success" />
              <p className="text-[13px] text-muted-foreground/70">
                No outstanding balances in this scope. Every invoice is settled.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-[13px]">
                <thead>
                  <tr className="border-b border-border/40 text-left text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground/60">
                    <th className="pb-2.5">Student</th>
                    <th className="pb-2.5">Class</th>
                    <th className="pb-2.5 text-right">Invoiced</th>
                    <th className="pb-2.5 text-right">Paid</th>
                    <th className="pb-2.5 text-right">Balance</th>
                    <th className="pb-2.5 text-right">Current</th>
                    <th className="pb-2.5 text-right">1–30</th>
                    <th className="pb-2.5 text-right">31–60</th>
                    <th className="pb-2.5 text-right">61–90</th>
                    <th className="pb-2.5 text-right">90+</th>
                    <th className="pb-2.5 text-right">Remind</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr
                      key={row.student_id}
                      className="border-b border-border/30 last:border-0 transition-colors hover:bg-accent/40"
                    >
                      <td className="py-3">
                        <p className="font-medium">{row.full_name}</p>
                        <p className="font-mono text-[11px] text-muted-foreground">
                          {row.admission_no}
                          {row.guardian_phone ? ` · ${row.guardian_phone}` : ""}
                        </p>
                      </td>
                      <td className="py-3 text-muted-foreground">{row.arm_name ?? "—"}</td>
                      <td className="py-3 text-right tabular-nums text-muted-foreground">
                        {formatMoney(row.invoiced, currency)}
                      </td>
                      <td className="py-3 text-right tabular-nums text-success">
                        {formatMoney(row.paid, currency)}
                      </td>
                      <td className="py-3 text-right font-semibold tabular-nums text-destructive">
                        {formatMoney(row.balance, currency)}
                      </td>
                      <td className="py-3 text-right tabular-nums text-muted-foreground">
                        {row.current ? formatMoney(row.current, currency) : "—"}
                      </td>
                      <td className="py-3 text-right tabular-nums text-muted-foreground">
                        {row.days_1_30 ? formatMoney(row.days_1_30, currency) : "—"}
                      </td>
                      <td className="py-3 text-right tabular-nums text-warning">
                        {row.days_31_60 ? formatMoney(row.days_31_60, currency) : "—"}
                      </td>
                      <td className="py-3 text-right tabular-nums text-destructive">
                        {row.days_61_90 ? formatMoney(row.days_61_90, currency) : "—"}
                      </td>
                      <td className="py-3 text-right font-semibold tabular-nums text-destructive">
                        {row.days_90_plus ? formatMoney(row.days_90_plus, currency) : "—"}
                      </td>
                      <td className="py-3">
                        <div className="flex items-center justify-end gap-1.5">
                          <Button
                            size="sm"
                            variant="outline"
                            className="gap-1"
                            title={
                              row.guardian_phone
                                ? `WhatsApp ${row.guardian_name ?? ""}`
                                : "No guardian phone on file — pick a contact in WhatsApp"
                            }
                            onClick={() => reminder(row)}
                          >
                            <MessageCircle className="h-3.5 w-3.5" /> WhatsApp
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            title={
                              row.guardian_email
                                ? `Email ${row.guardian_email}`
                                : "No guardian email on file"
                            }
                            onClick={() => emailReminder(row)}
                          >
                            <Mail className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      </td>
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
