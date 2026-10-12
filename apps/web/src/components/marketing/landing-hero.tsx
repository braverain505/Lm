"use client";

import {
  ArrowRight,
  Award,
  BadgeCheck,
  BarChart3,
  CalendarCheck,
  CheckCircle2,
  ClipboardCheck,
  FileText,
  LayoutDashboard,
  Search,
  Sparkles,
  Users,
  Wallet,
} from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";

import { AuroraBackdrop, EASE, Reveal } from "./landing-shared";
import { motion } from "framer-motion";

/** A quiet, non-numeric promise row — nothing here that a school can be billed for later. */
const PROMISES = [
  "Create your workspace in minutes",
  "Nothing to install",
  "Roles and permissions from day one",
];

const MOCK_NAV = [
  { icon: LayoutDashboard, label: "Overview", active: true },
  { icon: ClipboardCheck, label: "Results" },
  { icon: FileText, label: "Report cards" },
  { icon: CalendarCheck, label: "Attendance" },
  { icon: Wallet, label: "Fees" },
  { icon: Users, label: "Staff" },
];

const MOCK_KPIS = [
  { label: "Students enrolled", value: "1,248", note: "+36 this term", tone: "text-success" },
  { label: "Fees collected", value: "84%", note: "₦18.4m of ₦21.9m", tone: "text-primary" },
  { label: "Results published", value: "12", note: "of 14 classes", tone: "text-foreground" },
];

const MOCK_BARS = [42, 58, 47, 66, 74, 61, 83, 71, 88, 79, 92, 84];

const MOCK_ROWS = [
  { klass: "Primary 5A", stage: "Published", tone: "success", when: "2 min ago" },
  { klass: "JSS 2B", stage: "Verified", tone: "primary", when: "18 min ago" },
  { klass: "SSS 1A", stage: "Draft", tone: "muted", when: "1 hr ago" },
];

const STAGE_TONE: Record<string, string> = {
  success: "border-success/40 bg-success/15 text-success",
  primary: "border-primary/40 bg-primary/15 text-primary",
  muted: "border-border/80 bg-muted/60 text-muted-foreground",
};

export function LandingHero() {
  return (
    <section className="relative isolate overflow-hidden pb-16 pt-14 sm:pb-24 sm:pt-20">
      <AuroraBackdrop />

      <div className="relative mx-auto w-full max-w-6xl px-4 sm:px-6">
        <div className="mx-auto max-w-3xl text-center">
          <Reveal>
            <span className="inline-flex items-center gap-2 rounded-full border border-border/70 bg-card/70 px-3.5 py-1.5 text-[11.5px] font-semibold text-muted-foreground backdrop-blur">
              <Sparkles className="h-3.5 w-3.5 text-primary" />
              One platform for the whole school
            </span>
          </Reveal>

          <Reveal delay={0.05}>
            <h1 className="mt-6 text-[34px] font-bold leading-[1.08] tracking-tight text-foreground sm:text-[48px] lg:text-[58px]">
              Run your school from{" "}
              <span className="bg-gradient-to-br from-primary via-primary to-accent bg-clip-text text-transparent">
                one clear platform
              </span>
              .
            </h1>
          </Reveal>

          <Reveal delay={0.1}>
            <p className="mx-auto mt-5 max-w-2xl text-[15px] leading-relaxed text-muted-foreground sm:text-[17px]">
              Admissions, results, report cards, fees, attendance, timetables,
              staff, stock and your school&apos;s own AI copilot — in one system
              of record, instead of six spreadsheets and a WhatsApp group.
            </p>
          </Reveal>

          <Reveal delay={0.15}>
            <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <Button
                asChild
                className="h-12 w-full px-6 text-[14.5px] font-semibold shadow-md shadow-primary/25 sm:w-auto"
              >
                <Link href="/register">
                  Get started free
                  <ArrowRight className="ml-1.5 h-4 w-4" />
                </Link>
              </Button>
              <Button
                asChild
                variant="outline"
                className="h-12 w-full border-border/80 px-6 text-[14.5px] sm:w-auto"
              >
                <Link href="/login">Sign in to your school</Link>
              </Button>
            </div>
          </Reveal>

          <Reveal delay={0.2}>
            <div className="mt-7 flex flex-wrap items-center justify-center gap-x-5 gap-y-2">
              {PROMISES.map((promise) => (
                <span
                  key={promise}
                  className="inline-flex items-center gap-1.5 text-[12.5px] text-muted-foreground/90"
                >
                  <BadgeCheck className="h-3.5 w-3.5 text-success" />
                  {promise}
                </span>
              ))}
            </div>
          </Reveal>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 28 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease: EASE, delay: 0.2 }}
          className="relative mx-auto mt-14 max-w-5xl sm:mt-16"
        >
          <WorkspaceMock />

          {/* Floating proof chips — decorative, so they never crowd a small screen. */}
          <div className="pointer-events-none absolute -left-6 top-24 hidden xl:block">
            <div className="flex items-center gap-2.5 rounded-xl border border-border/70 bg-card/95 px-3.5 py-2.5 shadow-pop backdrop-blur">
              <CheckCircle2 className="h-4 w-4 text-success" />
              <div className="text-left">
                <p className="text-[11.5px] font-semibold leading-tight text-foreground">
                  Report card published
                </p>
                <p className="text-[10.5px] leading-tight text-muted-foreground">
                  Snapshot locked for audit
                </p>
              </div>
            </div>
          </div>

          <div className="pointer-events-none absolute -right-5 bottom-20 hidden xl:block">
            <div className="flex items-center gap-2.5 rounded-xl border border-border/70 bg-card/95 px-3.5 py-2.5 shadow-pop backdrop-blur">
              <Award className="h-4 w-4 text-primary" />
              <div className="text-left">
                <p className="text-[11.5px] font-semibold leading-tight text-foreground">
                  Result code issued
                </p>
                <p className="text-[10.5px] leading-tight text-muted-foreground">
                  Parent can check it now
                </p>
              </div>
            </div>
          </div>
        </motion.div>

        <p className="mt-6 text-center text-[11.5px] text-muted-foreground/80">
          Preview of the Clearis workspace
        </p>
      </div>
    </section>
  );
}

/**
 * The product shot.
 *
 * Built from markup rather than a screenshot so it re-themes with the site,
 * stays crisp on every display and never drifts out of date when the real
 * dashboard changes.
 */
function WorkspaceMock() {
  return (
    <div className="overflow-hidden rounded-2xl border border-border/70 bg-card shadow-[0_40px_120px_-40px_rgba(15,23,42,0.45)]">
      {/* Browser chrome */}
      <div className="flex items-center gap-3 border-b border-border/60 bg-muted/40 px-4 py-2.5">
        <div className="flex gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-destructive/40" />
          <span className="h-2.5 w-2.5 rounded-full bg-warning/50" />
          <span className="h-2.5 w-2.5 rounded-full bg-success/50" />
        </div>
        <div className="mx-auto hidden max-w-[280px] flex-1 items-center justify-center gap-1.5 rounded-md border border-border/60 bg-background/70 px-3 py-1 text-[10.5px] text-muted-foreground sm:flex">
          <Search className="h-3 w-3" />
          clearis.site/dashboard
        </div>
      </div>

      <div className="flex">
        {/* Sidebar */}
        <aside className="hidden w-[150px] shrink-0 border-r border-border/60 bg-muted/20 p-3 sm:block">
          <div className="space-y-0.5">
            {MOCK_NAV.map(({ icon: Icon, label, active }) => (
              <div
                key={label}
                className={
                  active
                    ? "flex items-center gap-2 rounded-lg bg-primary/12 px-2.5 py-2 text-[11.5px] font-semibold text-primary"
                    : "flex items-center gap-2 rounded-lg px-2.5 py-2 text-[11.5px] text-muted-foreground"
                }
              >
                <Icon className="h-3.5 w-3.5" />
                {label}
              </div>
            ))}
          </div>
          <div className="mt-4 rounded-lg border border-primary/25 bg-primary/8 p-2.5">
            <div className="flex items-center gap-1.5 text-[10.5px] font-semibold text-primary">
              <Sparkles className="h-3 w-3" />
              Clearis AI
            </div>
            <p className="mt-1 text-[10px] leading-snug text-muted-foreground">
              Ask your school&apos;s records anything.
            </p>
          </div>
        </aside>

        {/* Content */}
        <div className="min-w-0 flex-1 p-4 sm:p-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="text-[13.5px] font-bold tracking-tight text-foreground">
                Good morning, Principal
              </p>
              <p className="text-[11px] text-muted-foreground">
                Brightfield Academy · First Term
              </p>
            </div>
            <span className="rounded-full border border-border/70 bg-muted/50 px-2.5 py-1 text-[10px] font-semibold text-muted-foreground">
              2025 / 2026 session
            </span>
          </div>

          <div className="mt-4 grid gap-2.5 sm:grid-cols-3">
            {MOCK_KPIS.map((kpi) => (
              <div
                key={kpi.label}
                className="rounded-xl border border-border/70 bg-background/60 p-3"
              >
                <p className="text-[10.5px] font-medium uppercase tracking-wide text-muted-foreground">
                  {kpi.label}
                </p>
                <p className={`mt-1 text-[20px] font-bold tracking-tight ${kpi.tone}`}>
                  {kpi.value}
                </p>
                <p className="text-[10.5px] text-muted-foreground/85">{kpi.note}</p>
              </div>
            ))}
          </div>

          <div className="mt-3 grid gap-2.5 lg:grid-cols-5">
            <div className="rounded-xl border border-border/70 bg-background/60 p-3.5 lg:col-span-3">
              <div className="flex items-center justify-between">
                <p className="text-[11.5px] font-semibold text-foreground">
                  Fee collection
                </p>
                <BarChart3 className="h-3.5 w-3.5 text-muted-foreground" />
              </div>
              <div className="mt-3 flex h-[86px] items-end gap-1.5">
                {MOCK_BARS.map((height, index) => (
                  <div
                    key={index}
                    style={{ height: `${height}%` }}
                    className="flex-1 rounded-t-sm bg-gradient-to-t from-primary/25 to-primary/70"
                  />
                ))}
              </div>
              <div className="mt-2 flex justify-between text-[9.5px] text-muted-foreground/80">
                <span>Sep</span>
                <span>Oct</span>
                <span>Nov</span>
                <span>Dec</span>
              </div>
            </div>

            <div className="rounded-xl border border-border/70 bg-background/60 p-3.5 lg:col-span-2">
              <p className="text-[11.5px] font-semibold text-foreground">
                Result processing
              </p>
              <div className="mt-3 space-y-2">
                {MOCK_ROWS.map((row) => (
                  <div key={row.klass} className="flex items-center justify-between gap-2">
                    <div className="min-w-0">
                      <p className="truncate text-[11.5px] font-medium text-foreground">
                        {row.klass}
                      </p>
                      <p className="text-[9.5px] text-muted-foreground">{row.when}</p>
                    </div>
                    <span
                      className={`shrink-0 rounded-full border px-2 py-0.5 text-[9.5px] font-semibold ${STAGE_TONE[row.tone]}`}
                    >
                      {row.stage}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
