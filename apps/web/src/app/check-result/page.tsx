"use client";

// The parent-facing result viewer. Reached only by checking in on /login with a
// result code — a per-student code names the child outright, so no admission
// number is asked for; the short-lived portal token that check returns is held
// in sessionStorage, and this page is the only reader of it.
//
// It is a *public* page: no auth, no tenant header, and it talks exclusively to
// /api/public/* — which is exactly why the API never returns anything that is
// not published for the student behind the token.
import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowLeft,
  BookOpen,
  CalendarDays,
  Download,
  GraduationCap,
  Loader2,
  Printer,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  UserRound,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import type { PinTermBrief, ReportCard, ReportLayout } from "@clearis/shared";
import { api } from "@clearis/shared";

import { FlintwireCredit } from "@/components/flintwire-credit";
import { ReportCardDocument } from "@/components/report-card-document";
import { Button } from "@/components/ui/button";
import { ThemeSwitch } from "@/components/theme-switch";
import { downloadPdf } from "@/lib/pdf";
import { clearPortalSession, readPortalSession, type PortalSession } from "@/lib/portal-session";

import "@/app/report-card.css";
import "@/app/report-card-templates.css";

const ease = [0.25, 0.46, 0.45, 0.94] as const;

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
}

function pct(n: number | null | undefined): string {
  return n == null ? "—" : `${Math.round(n)}%`;
}

export default function CheckResultPage() {
  const router = useRouter();
  const stageRef = useRef<HTMLDivElement>(null);

  const [session, setSession] = useState<PortalSession | null>(null);
  const [ready, setReady] = useState(false);
  const [terms, setTerms] = useState<PinTermBrief[]>([]);
  const [termId, setTermId] = useState<string | null>(null);
  const [card, setCard] = useState<ReportCard | null>(null);
  const [cardLoading, setCardLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);
  // The school's card design, read on the client with the session so the server
  // render and the first client render agree.
  const [design, setDesign] = useState<ReportLayout | null>(null);

  // 1. Establish the session. Without a token there is nothing to show, and the
  //    check-in form (on /login) is the only way to get one.
  useEffect(() => {
    const stored = readPortalSession();
    if (!stored) {
      router.replace("/login");
      return;
    }
    setSession(stored);
    setDesign(stored.report_template ?? null);
    setReady(true);
  }, [router]);

  // 2. The list of published terms drives the term picker. A failure here is not
  //    fatal — the card still loads for the latest term below.
  useEffect(() => {
    if (!session) return;
    let cancelled = false;
    api
      .publicTerms(session.token)
      .then((rows) => {
        if (!cancelled) setTerms(rows);
      })
      .catch(() => {
        if (!cancelled) setTerms([]);
      });
    return () => {
      cancelled = true;
    };
  }, [session]);

  // 3. Load the card for the selected term (latest when none is chosen).
  useEffect(() => {
    if (!session) return;
    let cancelled = false;
    setCardLoading(true);
    setError(null);
    api
      .publicReportCard(session.token, termId ?? undefined)
      .then((data) => {
        if (!cancelled) setCard(data);
      })
      .catch((e) => {
        if (cancelled) return;
        setCard(null);
        setError(
          e instanceof Error && e.message
            ? e.message
            : "No published result is available for this student yet.",
        );
      })
      .finally(() => {
        if (!cancelled) setCardLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [session, termId]);

  const handleDownload = useCallback(async () => {
    const el = stageRef.current;
    if (!el || !card) return;
    setDownloading(true);
    try {
      await downloadPdf(el, `report-card-${card.student.admission_no}.pdf`);
    } finally {
      setDownloading(false);
    }
  }, [card]);

  const checkAnother = () => {
    clearPortalSession();
    router.push("/login");
  };

  if (!ready || !session) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="flex items-center gap-3 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Opening your result…
        </div>
      </div>
    );
  }

  const stats = [
    {
      label: "Overall average",
      value: pct(card?.summary.average),
      sub: card?.summary.grade_letter ? `Grade ${card.summary.grade_letter}` : "Grade —",
      icon: TrendingUp,
    },
    {
      label: "Position in class",
      value: card?.summary.class_rank != null ? `${card.summary.class_rank}` : "—",
      sub: `of ${card?.summary.class_size ?? "—"} students`,
      icon: GraduationCap,
    },
    {
      label: "Attendance",
      value: pct(card?.attendance_pct),
      sub: card?.term?.name ?? "This term",
      icon: CalendarDays,
    },
    {
      label: "Subjects",
      value: card ? `${card.subjects.length}` : "—",
      sub: card ? `${card.session.name}` : "session",
      icon: BookOpen,
    },
  ];

  return (
    <div className="min-h-screen bg-background">
      {/* Chrome — never printed. */}
      <header className="sticky top-0 z-20 border-b border-border/50 bg-background/80 backdrop-blur-xl print:hidden">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <button
            type="button"
            onClick={checkAnother}
            className="flex items-center gap-2 text-[13px] font-semibold text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" />
            <span className="hidden sm:inline">Check another result</span>
            <span className="sm:hidden">Back</span>
          </button>
          <div className="flex items-center gap-2">
            <ThemeSwitch />
            <Button
              variant="outline"
              size="sm"
              onClick={() => window.print()}
              disabled={!card}
            >
              <Printer className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Print</span>
            </Button>
            <Button size="sm" onClick={handleDownload} disabled={!card || downloading}>
              {downloading ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Download className="h-3.5 w-3.5" />
              )}
              <span className="hidden sm:inline">
                {downloading ? "Preparing…" : "Download PDF"}
              </span>
              <span className="sm:hidden">PDF</span>
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 pb-16 pt-6 sm:px-6">
        {/* Identity banner */}
        <motion.section
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease }}
          className="relative overflow-hidden rounded-3xl border border-border/60 bg-card p-6 shadow-[0_20px_60px_-35px_rgba(15,23,42,0.5)] sm:p-7"
        >
          <div className="pointer-events-none absolute inset-0">
            <div className="absolute -right-16 -top-24 h-64 w-64 rounded-full bg-primary/[0.07] blur-3xl" />
          </div>

          <div className="relative flex flex-wrap items-center gap-5">
            <div className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-2xl border border-border/60 bg-white">
              {card?.school.logo_url ? (
                /* eslint-disable-next-line @next/next/no-img-element */
                <img
                  src={card.school.logo_url}
                  alt={session.school.name}
                  className="h-full w-full object-contain p-1"
                />
              ) : (
                <span className="text-[17px] font-bold text-primary">
                  {initials(session.school.name)}
                </span>
              )}
            </div>

            <div className="min-w-0 flex-1">
              <p className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground/70">
                <ShieldCheck className="h-3.5 w-3.5 text-primary" />
                Verified result
              </p>
              <h1 className="mt-1 truncate text-[20px] font-bold tracking-tight sm:text-[23px]">
                {session.school.name}
              </h1>
              <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12.5px] text-muted-foreground">
                <span className="inline-flex items-center gap-1.5">
                  <UserRound className="h-3.5 w-3.5" />
                  <strong className="font-semibold text-foreground/90">
                    {session.student.full_name}
                  </strong>
                </span>
                <span className="inline-flex items-center gap-1.5">
                  Admission No.
                  <strong className="font-semibold text-foreground/90">
                    {session.student.admission_no}
                  </strong>
                </span>
                {card && (
                  <span className="inline-flex items-center gap-1.5">
                    <Sparkles className="h-3.5 w-3.5" />
                    {card.class_arm.full_name}
                  </span>
                )}
              </p>
            </div>
          </div>

          {/* Stat tiles */}
          <div className="relative mt-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
            {stats.map((stat) => {
              const Icon = stat.icon;
              return (
                <div
                  key={stat.label}
                  className="rounded-2xl border border-border/50 bg-muted/25 p-4"
                >
                  <div className="flex items-center justify-between">
                    <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground/70">
                      {stat.label}
                    </p>
                    <Icon className="h-3.5 w-3.5 text-primary/70" />
                  </div>
                  <p className="mt-2 text-[22px] font-bold tabular-nums leading-none">
                    {cardLoading ? "—" : stat.value}
                  </p>
                  <p className="mt-1 text-[11px] text-muted-foreground/70">{stat.sub}</p>
                </div>
              );
            })}
          </div>
        </motion.section>

        {/* Term picker — only worth showing when there is a choice to make. */}
        {terms.length > 1 && (
          <div className="mt-6 flex flex-wrap items-center gap-2 print:hidden">
            <span className="mr-1 text-[12px] font-medium text-muted-foreground">
              Term
            </span>
            {terms.map((t) => {
              const active = (termId ?? terms[0]?.id) === t.id;
              return (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setTermId(t.id)}
                  className={`rounded-full border px-3.5 py-1.5 text-[12px] font-semibold transition-all duration-150 ${
                    active
                      ? "border-primary/30 bg-primary/10 text-primary"
                      : "border-border/60 text-muted-foreground hover:border-border hover:text-foreground"
                  }`}
                >
                  {t.name}
                  <span className="ml-1.5 font-normal text-muted-foreground/60">
                    {t.session_name}
                  </span>
                </button>
              );
            })}
          </div>
        )}

        {/* The document */}
        <div className="mt-6">
          <AnimatePresence mode="wait">
            {cardLoading ? (
              <motion.div
                key="loading"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex h-72 items-center justify-center rounded-3xl border border-border/60 bg-card"
              >
                <div className="flex items-center gap-3 text-[13px] text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Loading report card…
                </div>
              </motion.div>
            ) : error || !card ? (
              <motion.div
                key="error"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="rounded-3xl border border-border/60 bg-card px-6 py-14 text-center"
              >
                <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-muted/60">
                  <BookOpen className="h-5 w-5 text-muted-foreground" />
                </div>
                <h2 className="text-[15px] font-semibold">
                  No published result yet
                </h2>
                <p className="mx-auto mt-2 max-w-md text-[13px] leading-relaxed text-muted-foreground">
                  {error ??
                    "Your school has not published a report card for this student yet. Please check back later."}
                </p>
                <Button variant="outline" className="mt-5" onClick={checkAnother}>
                  <ArrowLeft className="h-4 w-4" />
                  Back to check-in
                </Button>
              </motion.div>
            ) : (
              <motion.div
                key={card.term.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.35, ease }}
                className="rc-print-page"
              >
                <div ref={stageRef} className="report-card-stage">
                  <ReportCardDocument card={card} layout={design} />
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <p className="mt-6 flex items-center justify-center gap-2 text-center text-[11.5px] text-muted-foreground/70 print:hidden">
          <ShieldCheck className="h-3.5 w-3.5 text-primary/70" />
          Published by {session.school.name} · served securely through Clearis
        </p>

        <div className="mt-6 print:hidden">
          <FlintwireCredit />
        </div>
      </main>
    </div>
  );
}
