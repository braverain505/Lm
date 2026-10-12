"use client";

import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowRight,
  Award,
  Banknote,
  Bot,
  BookCopy,
  BookOpen,
  Building2,
  CalendarCheck,
  Calculator,
  Check,
  CheckCircle2,
  ChevronDown,
  ClipboardCheck,
  ClipboardList,
  DatabaseBackup,
  Download,
  FileSpreadsheet,
  FileText,
  GraduationCap,
  History,
  LayoutTemplate,
  Lock,
  MessageSquare,
  MonitorPlay,
  NotebookPen,
  Package,
  Receipt,
  ShieldCheck,
  Sparkles,
  Users,
  Wallet,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { APP_DOWNLOAD_NAME, APP_DOWNLOAD_URL } from "@/lib/app-download";
import { cn } from "@/lib/utils";

import { AuroraBackdrop, EASE, Reveal, SectionHeading, SectionLabel } from "./landing-shared";

/** One shared "get the app" affordance so every placement stays identical. */
function AppDownloadButton({ className, label = "Download the app" }: { className?: string; label?: string }) {
  return (
    <Button
      asChild
      variant="outline"
      className={cn("border-primary/40 bg-primary/[0.07] text-primary hover:bg-primary/12 hover:text-primary", className)}
    >
      <a href={APP_DOWNLOAD_URL} download={APP_DOWNLOAD_NAME}>
        <Download className="mr-1.5 h-4 w-4" />
        {label}
      </a>
    </Button>
  );
}

/* ───────────────────────────── Trust strip ───────────────────────────── */

const TRUST = [
  { icon: ShieldCheck, label: "Tenant-isolated" },
  { icon: Lock, label: "Role-based access" },
  { icon: History, label: "Append-only audit journal" },
  { icon: GraduationCap, label: "WAEC-aligned grading" },
  { icon: DatabaseBackup, label: "Automated backups" },
];

function TrustStrip() {
  return (
    <section className="border-y border-border/70 bg-muted/25">
      <div className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6">
        <div className="flex flex-wrap items-center justify-center gap-x-7 gap-y-3">
          {TRUST.map(({ icon: Icon, label }) => (
            <span
              key={label}
              className="inline-flex items-center gap-2 text-[12.5px] font-medium text-muted-foreground"
            >
              <Icon className="h-4 w-4 text-primary/80" />
              {label}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ─────────────────────────────── Problem ─────────────────────────────── */

const PAINS: { icon: LucideIcon; title: string; body: string }[] = [
  {
    icon: FileSpreadsheet,
    title: "Marks in spreadsheets",
    body: "Term averages by hand, one broken formula from a card nobody can defend.",
  },
  {
    icon: BookOpen,
    title: "Fees in a ledger book",
    body: "Balances only one person can read, and only when they are in the office.",
  },
  {
    icon: ClipboardList,
    title: "Attendance on paper",
    body: "No monthly summary, no answer for a parent asking about last term.",
  },
  {
    icon: MessageSquare,
    title: "Results over WhatsApp",
    body: "Screenshots flying about, nobody sure which version is final.",
  },
];

function ProblemSection() {
  return (
    <section className="relative py-20 sm:py-24">
      <div className="mx-auto w-full max-w-6xl px-4 sm:px-6">
        <Reveal>
          <SectionLabel>The problem</SectionLabel>
          <SectionHeading
            className="mt-5"
            title="Six tools and a group chat is not a system."
            description="Every school assembles its own software out of whatever is closest. It works — until the term gets busy and the numbers stop agreeing."
          />
        </Reveal>

        <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {PAINS.map(({ icon: Icon, title, body }, index) => (
            <Reveal key={title} delay={index * 0.06}>
              <div className="h-full rounded-2xl border border-border/70 bg-card p-5 shadow-card">
                <span className="flex h-9 w-9 items-center justify-center rounded-xl border border-destructive/25 bg-destructive/10">
                  <Icon className="h-4 w-4 text-destructive" />
                </span>
                <p className="mt-4 text-[14px] font-semibold text-foreground">{title}</p>
                <p className="mt-1.5 text-[12.5px] leading-relaxed text-muted-foreground">
                  {body}
                </p>
              </div>
            </Reveal>
          ))}
        </div>

        <Reveal delay={0.1}>
          <div className="mt-8 flex flex-col items-start gap-4 rounded-2xl border border-primary/25 bg-primary/[0.06] p-5 sm:flex-row sm:items-center sm:p-6">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-sm shadow-primary/30">
              <CheckCircle2 className="h-5 w-5" />
            </span>
            <p className="text-[15px] text-foreground">
              Clearis replaces it with <span className="font-semibold">one system of record</span> —
              one login, one permission model, one audit trail.
            </p>
          </div>
        </Reveal>
      </div>
    </section>
  );
}

/* ────────────────────────── One platform, all seats ───────────────────────── */

const SEATS: { icon: LucideIcon; title: string; items: string[] }[] = [
  {
    icon: Building2,
    title: "The school office",
    items: [
      "School-wide term dashboard",
      "Admissions and student records",
      "Classes, subjects and timetables",
      "Fee structures and balances",
      "Report card designer and branding",
    ],
  },
  {
    icon: GraduationCap,
    title: "Teachers",
    items: [
      "Score entry for their own classes",
      "Attendance for their register",
      "Psychomotor and affective notes",
      "AI lesson plans and question banks",
      "Their own timetable",
    ],
  },
  {
    icon: Wallet,
    title: "Bursary and accounts",
    items: [
      "Fees, invoices and payments",
      "Expenses, cashbook and debtors",
      "Discounts and refunds",
      "Salary structures and pay runs",
      "Financial reports",
    ],
  },
  {
    icon: Users,
    title: "Parents and students",
    items: [
      "A result code, no account needed",
      "Opens the published result only",
      "The school's own card design",
      "Works from any phone",
      "No staff data exposed",
    ],
  },
];

function PlatformSection() {
  return (
    <section id="platform" className="scroll-mt-20 border-y border-border/70 bg-muted/20 py-20 sm:py-24">
      <div className="mx-auto w-full max-w-6xl px-4 sm:px-6">
        <Reveal>
          <SectionLabel>One platform</SectionLabel>
          <SectionHeading
            className="mt-5"
            title="One platform, every seat covered."
            description="A front door for each person who touches the school day — and each one sees only what their role allows, decided on the server."
          />
        </Reveal>

        <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {SEATS.map(({ icon: Icon, title, items }, index) => (
            <Reveal key={title} delay={index * 0.06}>
              <div className="h-full rounded-2xl border border-border/70 bg-card p-5 shadow-card transition-shadow duration-200 hover:shadow-card-hover">
                <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/12">
                  <Icon className="h-4 w-4 text-primary" />
                </span>
                <p className="mt-4 text-[15px] font-bold tracking-tight text-foreground">{title}</p>
                <ul className="mt-3.5 space-y-2">
                  {items.map((item) => (
                    <li key={item} className="flex gap-2 text-[12.5px] leading-relaxed text-muted-foreground">
                      <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-success" />
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ──────────────────────────────── Features ──────────────────────────────── */

const DESKS: {
  icon: LucideIcon;
  desk: string;
  beta?: boolean;
  features: { icon: LucideIcon; name: string }[];
}[] = [
  {
    icon: ClipboardCheck,
    desk: "Academics",
    features: [
      { icon: ClipboardCheck, name: "Results and grading" },
      { icon: FileText, name: "Report cards" },
      { icon: LayoutTemplate, name: "Card designer" },
      { icon: CalendarCheck, name: "Attendance" },
      { icon: BookOpen, name: "Classes, subjects, timetable" },
    ],
  },
  {
    icon: Users,
    desk: "Administration",
    features: [
      { icon: Users, name: "Students and admissions" },
      { icon: GraduationCap, name: "Teachers and staff" },
      { icon: Package, name: "Inventory" },
      { icon: BookCopy, name: "Library" },
    ],
  },
  {
    icon: Wallet,
    desk: "Finance",
    features: [
      { icon: Wallet, name: "Fees and billing" },
      { icon: Banknote, name: "Payroll" },
      { icon: Calculator, name: "Accounting desk" },
      { icon: Receipt, name: "Receipts" },
    ],
  },
  {
    icon: Bot,
    desk: "AI tools",
    beta: true,
    features: [
      { icon: Bot, name: "Clearis AI copilot" },
      { icon: NotebookPen, name: "AI lesson plans" },
      { icon: MonitorPlay, name: "AI question banks" },
    ],
  },
];

function FeaturesSection() {
  return (
    <section id="features" className="scroll-mt-20 py-20 sm:py-24">
      <div className="mx-auto w-full max-w-6xl px-4 sm:px-6">
        <Reveal>
          <SectionLabel>Features</SectionLabel>
          <SectionHeading
            className="mt-5"
            title="Four desks, everything a term needs."
            description="The same structure you see the moment you sign in. The office, the classroom, the bursary and the AI desk."
          />
        </Reveal>

        <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {DESKS.map(({ icon: DeskIcon, desk, beta, features }, index) => (
            <Reveal key={desk} delay={index * 0.06}>
              <div className="h-full rounded-2xl border border-border/70 bg-card p-5 shadow-card">
                <div className="flex items-center gap-2">
                  <DeskIcon className="h-4 w-4 text-primary" />
                  <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-foreground">
                    {desk}
                  </p>
                  {beta && (
                    <span className="rounded-full border border-warning/40 bg-warning/15 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide text-warning">
                      Beta
                    </span>
                  )}
                </div>

                <div className="mt-4 space-y-2.5">
                  {features.map(({ icon: Icon, name }) => (
                    <div key={name} className="flex items-center gap-2.5">
                      <Icon className="h-3.5 w-3.5 shrink-0 text-muted-foreground/70" />
                      <p className="text-[12.5px] font-medium text-foreground">{name}</p>
                    </div>
                  ))}
                </div>
              </div>
            </Reveal>
          ))}
        </div>

        <Reveal delay={0.1}>
          <div className="mt-8 flex flex-col items-start justify-between gap-4 rounded-2xl border border-border/70 bg-muted/30 p-5 sm:flex-row sm:items-center">
            <p className="text-[13.5px] text-muted-foreground">
              Every screen is scoped to your school and re-checked against your role on each request.
            </p>
            <div className="flex shrink-0 flex-wrap gap-2">
              <Button asChild className="h-10 px-5 text-[13.5px]">
                <Link href="/register">
                  Create your workspace
                  <ArrowRight className="ml-1.5 h-4 w-4" />
                </Link>
              </Button>
              <AppDownloadButton className="h-10 px-5 text-[13.5px]" />
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}

/* ──────────────────────────── Results spotlight ──────────────────────────── */

const GUARANTEES = [
  "Marks are validated at entry, so a typo cannot be published.",
  "Grades compute against your school's own scale — WAEC-aligned by default.",
  "Every stage lands in an append-only audit journal.",
  "A published card is a snapshot; later edits cannot rewrite it.",
];

const PIPELINE = [
  { title: "Enter scores", body: "Teachers enter marks for their own subjects only." },
  { title: "Read readiness", body: "The exam office sees which classes are complete." },
  { title: "Process", body: "Verify, approve or reject, with a reason on record." },
  { title: "Publish", body: "Cards generated from the approved snapshot." },
  { title: "Parents check", body: "A result code opens the published card." },
];

function ResultsSection() {
  return (
    <section id="results" className="scroll-mt-20 border-y border-border/70 bg-muted/20 py-20 sm:py-24">
      <div className="mx-auto w-full max-w-6xl px-4 sm:px-6">
        <div className="grid gap-12 lg:grid-cols-2 lg:gap-16">
          <Reveal>
            <SectionLabel>Results, end to end</SectionLabel>
            <SectionHeading
              className="mt-5"
              title="A report card a parent can trust."
              description="Results are the document a school is judged by. Clearis runs the whole pipeline and keeps a record of how each one was reached."
            />

            <ul className="mt-8 space-y-3">
              {GUARANTEES.map((line) => (
                <li key={line} className="flex gap-3 text-[13px] leading-relaxed text-muted-foreground">
                  <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-success/15">
                    <Check className="h-3 w-3 text-success" />
                  </span>
                  {line}
                </li>
              ))}
            </ul>

            <div className="mt-8 flex flex-wrap gap-3">
              <Button asChild className="h-11 px-5 text-[13.5px]">
                <Link href="/register">
                  Start with your school
                  <ArrowRight className="ml-1.5 h-4 w-4" />
                </Link>
              </Button>
              <Button asChild variant="outline" className="h-11 px-5 text-[13.5px]">
                <Link href="/check-result">
                  <Award className="mr-1.5 h-4 w-4" />
                  Check a result
                </Link>
              </Button>
            </div>
          </Reveal>

          <Reveal delay={0.1}>
            <ol className="relative space-y-4">
              {PIPELINE.map((step, index) => (
                <li key={step.title} className="relative flex gap-4">
                  <div className="flex flex-col items-center">
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-primary/30 bg-card text-[12px] font-bold text-primary shadow-xs">
                      {index + 1}
                    </span>
                    {index < PIPELINE.length - 1 && (
                      <span className="mt-1.5 h-full w-px flex-1 bg-gradient-to-b from-primary/35 to-border/60" />
                    )}
                  </div>
                  <div className="pb-2">
                    <p className="text-[14px] font-semibold tracking-tight text-foreground">
                      {step.title}
                    </p>
                    <p className="mt-0.5 text-[12.5px] leading-relaxed text-muted-foreground">
                      {step.body}
                    </p>
                  </div>
                </li>
              ))}
            </ol>
          </Reveal>
        </div>
      </div>
    </section>
  );
}

/* ────────────────────────────────── AI ────────────────────────────────── */

const AI_CARDS: { icon: LucideIcon; title: string; body: string }[] = [
  {
    icon: Bot,
    title: "School copilot",
    body: "Ask about enrolments, results, attendance or fees — answered from your rows.",
  },
  {
    icon: NotebookPen,
    title: "Lesson plans",
    body: "Draft a topic plan, then edit it.",
  },
  {
    icon: MonitorPlay,
    title: "Question banks",
    body: "Generate questions for a subject and class.",
  },
];

const AI_NOTES = ["Grounded in your records", "Metered per request", "Permission-gated", "Beta"];

function AiSection() {
  return (
    <section id="ai" className="scroll-mt-20 py-20 sm:py-24">
      <div className="mx-auto w-full max-w-6xl px-4 sm:px-6">
        <Reveal>
          <div className="relative overflow-hidden rounded-3xl border border-primary/25 bg-gradient-to-br from-primary via-primary to-chart-5 p-7 shadow-xl shadow-primary/20 sm:p-11">
            <div
              aria-hidden
              className="pointer-events-none absolute inset-0 opacity-[0.14]"
              style={{
                backgroundImage:
                  "linear-gradient(to right, white 1px, transparent 1px), linear-gradient(to bottom, white 1px, transparent 1px)",
                backgroundSize: "44px 44px",
                maskImage: "radial-gradient(ellipse at 20% 0%, black, transparent 70%)",
                WebkitMaskImage: "radial-gradient(ellipse at 20% 0%, black, transparent 70%)",
              }}
            />

            <div className="relative grid gap-10 lg:grid-cols-2 lg:gap-14">
              <div>
                <span className="inline-flex items-center gap-1.5 rounded-full border border-white/25 bg-white/15 px-3 py-1 text-[10.5px] font-semibold uppercase tracking-[0.14em] text-white backdrop-blur">
                  <Sparkles className="h-3 w-3" />
                  AI tools
                </span>
                <h2 className="mt-5 text-[26px] font-bold leading-[1.15] tracking-tight text-white sm:text-[32px] lg:text-[38px]">
                  Clearis AI, grounded in your school&apos;s own records.
                </h2>
                <p className="mt-4 max-w-lg text-[14.5px] leading-relaxed text-white/85">
                  Ask in plain English, get an answer built from your data — never a
                  black box on it.
                </p>

                <div className="mt-6 flex flex-wrap gap-2">
                  {AI_NOTES.map((note) => (
                    <span
                      key={note}
                      className="rounded-full border border-white/25 bg-white/10 px-2.5 py-1 text-[11px] font-medium text-white/90 backdrop-blur"
                    >
                      {note}
                    </span>
                  ))}
                </div>

                <div className="mt-7 space-y-2.5">
                  <div className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-md bg-white/95 px-4 py-2.5 text-[12.5px] text-slate-900 shadow-sm">
                    Who has not paid this term?
                  </div>
                  <div className="w-fit max-w-[92%] rounded-2xl rounded-bl-md border border-white/20 bg-white/10 px-4 py-2.5 text-[12.5px] leading-relaxed text-white backdrop-blur">
                    <span className="flex items-center gap-1.5 text-[10.5px] font-semibold uppercase tracking-wide text-white/70">
                      <Bot className="h-3 w-3" /> Clearis AI
                    </span>
                    <p className="mt-1">
                      Two classes are outstanding for First Term. I can open the
                      debtor list with balances for the bursary.
                    </p>
                  </div>
                </div>
              </div>

              <div className="grid gap-3 self-start">
                {AI_CARDS.map(({ icon: Icon, title, body }) => (
                  <div
                    key={title}
                    className="rounded-2xl border border-white/20 bg-white/10 p-4 backdrop-blur"
                  >
                    <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/20">
                      <Icon className="h-4 w-4 text-white" />
                    </span>
                    <p className="mt-3 text-[14px] font-semibold text-white">{title}</p>
                    <p className="mt-1 text-[12.5px] leading-relaxed text-white/80">{body}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}

/* ────────────────────────────── How it works ────────────────────────────── */

const STEPS = [
  { title: "Create your workspace", body: "Register the school; you become its first administrator." },
  { title: "Add your school", body: "Classes, subjects, staff roles, students and fee structures." },
  { title: "Run the term", body: "Scores, attendance, invoices and results — the audit trail writes itself." },
];

function HowItWorksSection() {
  return (
    <section id="how" className="scroll-mt-20 border-y border-border/70 bg-muted/20 py-20 sm:py-24">
      <div className="mx-auto w-full max-w-6xl px-4 sm:px-6">
        <Reveal>
          <SectionLabel>Get started</SectionLabel>
          <SectionHeading
            className="mt-5"
            title="Three steps to a calmer term."
            description="No migration needed on day one. Bring in one class and grow from there."
          />
        </Reveal>

        <div className="mt-12 grid gap-4 md:grid-cols-3">
          {STEPS.map((step, index) => (
            <Reveal key={step.title} delay={index * 0.07}>
              <div className="h-full rounded-2xl border border-border/70 bg-card p-5 shadow-card">
                <span className="text-[40px] font-bold leading-none text-primary/15">
                  0{index + 1}
                </span>
                <p className="mt-2 text-[15px] font-bold tracking-tight text-foreground">
                  {step.title}
                </p>
                <p className="mt-1.5 text-[12.5px] leading-relaxed text-muted-foreground">
                  {step.body}
                </p>
              </div>
            </Reveal>
          ))}
        </div>

        <Reveal delay={0.1}>
          <div className="mt-8 flex flex-col items-center gap-4 rounded-2xl border border-border/70 bg-card p-6 sm:flex-row sm:justify-between">
            <div className="flex items-center gap-3">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/12">
                <Download className="h-4 w-4 text-primary" />
              </span>
              <div>
                <p className="text-[14px] font-semibold text-foreground">
                  Take Clearis with you
                </p>
                <p className="text-[12.5px] text-muted-foreground">
                  The same workspace from a phone — marks, fees and results.
                </p>
              </div>
            </div>
            <AppDownloadButton className="h-11 w-full shrink-0 px-5 text-[13.5px] sm:w-auto" label="Download the app" />
          </div>
        </Reveal>
      </div>
    </section>
  );
}

/* ────────────────────────────────── FAQ ────────────────────────────────── */

const FAQS = [
  {
    q: "Who is Clearis built for?",
    a: "Primary and secondary schools that run on a term structure — sessions, classes and arms, subjects, staff roles, guardians and report cards.",
  },
  {
    q: "How long does setup take?",
    a: "Creating the workspace takes minutes. Then add your classes and staff, load students, and grow from one class.",
  },
  {
    q: "Can parents see results without an account?",
    a: "Yes. Each published result gets a code an admin issues. The parent enters it and sees that student's card in the school's own design — no staff data exposed.",
  },
  {
    q: "Is our data separate from other schools?",
    a: "Every request carries the school it acts on, and the server confirms the caller is a member before anything is read or written. A non-member gets the same not-found as a school that does not exist.",
  },
  {
    q: "How is access controlled?",
    a: "Roles and permissions checked server-side on every request, never in the browser. Teachers see their classes, the exam office processes results, the accountant sees the books.",
  },
  {
    q: "What about the AI features?",
    a: "They are beta while improving. Answers come from your school's records, every generation is metered, and each AI feature sits behind its own permission.",
  },
];

function FaqItem({ q, a }: { q: string; a: string }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="border-b border-border/70">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-4 py-4 text-left"
      >
        <span className="text-[14px] font-semibold text-foreground">{q}</span>
        <ChevronDown
          className={cn(
            "h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200",
            open && "rotate-180",
          )}
        />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: EASE }}
            className="overflow-hidden"
          >
            <p className="pb-4 pr-6 text-[13px] leading-relaxed text-muted-foreground">{a}</p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function FaqSection() {
  return (
    <section id="faq" className="scroll-mt-20 py-20 sm:py-24">
      <div className="mx-auto w-full max-w-3xl px-4 sm:px-6">
        <Reveal>
          <SectionHeading
            align="center"
            title="Questions schools ask before switching."
            description="Setup, access, and where the data lives."
          />
        </Reveal>
        <Reveal delay={0.08}>
          <div className="mt-10 border-t border-border/70">
            {FAQS.map((faq) => (
              <FaqItem key={faq.q} q={faq.q} a={faq.a} />
            ))}
          </div>
        </Reveal>
      </div>
    </section>
  );
}

/* ──────────────────────────────── Final CTA ──────────────────────────────── */

function FinalCta() {
  return (
    <section className="relative isolate overflow-hidden border-t border-border/70 py-20 sm:py-24">
      <AuroraBackdrop className="opacity-80" />
      <div className="relative mx-auto w-full max-w-3xl px-4 text-center sm:px-6">
        <Reveal>
          <h2 className="text-[30px] font-bold leading-[1.1] tracking-tight text-foreground sm:text-[40px]">
            Bring your school onto one clear platform.
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-[15px] leading-relaxed text-muted-foreground">
            Start with the workspace, add your first class, and let the term run
            itself.
          </p>
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
            <Button asChild variant="outline" className="h-12 w-full px-6 text-[14.5px] sm:w-auto">
              <Link href="/login">Sign in</Link>
            </Button>
            <AppDownloadButton className="h-12 w-full px-6 text-[14.5px] sm:w-auto" />
          </div>
          <p className="mt-5 text-[12.5px] text-muted-foreground/85">
            Parent or student?{" "}
            <Link href="/check-result" className="font-semibold text-primary hover:text-primary/90">
              Check a published result
            </Link>
          </p>
        </Reveal>
      </div>
    </section>
  );
}

export function LandingBody() {
  return (
    <>
      <TrustStrip />
      <ProblemSection />
      <PlatformSection />
      <FeaturesSection />
      <ResultsSection />
      <AiSection />
      <HowItWorksSection />
      <FaqSection />
      <FinalCta />
    </>
  );
}
