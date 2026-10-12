"use client";

import { motion, useReducedMotion } from "framer-motion";
import {
  Award,
  BarChart3,
  Bot,
  CalendarCheck,
  ClipboardCheck,
  Download,
  FileText,
  LayoutDashboard,
  Pause,
  Play,
  Search,
  Sparkles,
  Users,
  Wallet,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { cn } from "@/lib/utils";

import { EASE } from "./landing-shared";

const ROTATE_MS = 5500;

const FRAME_NAV: { icon: LucideIcon; label: string }[] = [
  { icon: LayoutDashboard, label: "Overview" },
  { icon: ClipboardCheck, label: "Results" },
  { icon: FileText, label: "Report cards" },
  { icon: CalendarCheck, label: "Attendance" },
  { icon: Wallet, label: "Fees" },
  { icon: Users, label: "Staff" },
];

const CHIP: Record<string, string> = {
  success: "border-success/40 bg-success/15 text-success",
  primary: "border-primary/40 bg-primary/15 text-primary",
  warning: "border-warning/40 bg-warning/20 text-warning",
  muted: "border-border/80 bg-muted/60 text-muted-foreground",
};

/* ─────────────────────────────── Screens ─────────────────────────────── */

function ScreenHeading({
  title,
  subtitle,
  chip,
}: {
  title: string;
  subtitle: string;
  chip: string;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2">
      <div className="min-w-0">
        <p className="truncate text-[13px] font-bold tracking-tight text-foreground">{title}</p>
        <p className="truncate text-[10.5px] text-muted-foreground">{subtitle}</p>
      </div>
      <span className="shrink-0 rounded-full border border-border/70 bg-muted/50 px-2.5 py-1 text-[9.5px] font-semibold text-muted-foreground">
        {chip}
      </span>
    </div>
  );
}

function Kpi({
  label,
  value,
  note,
  tone = "text-foreground",
}: {
  label: string;
  value: string;
  note: string;
  tone?: string;
}) {
  return (
    <div className="rounded-xl border border-border/70 bg-background/60 p-2.5">
      <p className="truncate text-[9.5px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className={cn("mt-0.5 text-[18px] font-bold tracking-tight", tone)}>{value}</p>
      <p className="truncate text-[9.5px] text-muted-foreground/85">{note}</p>
    </div>
  );
}

function OverviewScreen() {
  const bars = [42, 58, 47, 66, 74, 61, 83, 71, 88, 79, 92, 84];
  const activity = [
    { text: "Primary 5A results published", when: "2 min ago", tone: "success" },
    { text: "JSS 2B verified by the exam office", when: "18 min ago", tone: "primary" },
    { text: "₦120,000 fee payment · Amaka O.", when: "1 hr ago", tone: "muted" },
  ];

  return (
    <div className="space-y-3">
      <ScreenHeading title="Good morning, Principal" subtitle="Brightfield Academy · First Term" chip="2025 / 2026" />

      <div className="grid grid-cols-3 gap-2.5">
        <Kpi label="Students" value="1,248" note="+36 this term" />
        <Kpi label="Fees collected" value="84%" note="₦18.4m of ₦21.9m" tone="text-primary" />
        <Kpi label="Results published" value="12" note="of 14 classes" tone="text-success" />
      </div>

      <div className="grid gap-2.5 sm:grid-cols-5">
        <div className="rounded-xl border border-border/70 bg-background/60 p-3 sm:col-span-3">
          <div className="flex items-center justify-between">
            <p className="text-[11px] font-semibold text-foreground">Fee collection</p>
            <BarChart3 className="h-3.5 w-3.5 text-muted-foreground" />
          </div>
          <div className="mt-2.5 flex h-[70px] items-end gap-1.5">
            {bars.map((height, index) => (
              <div
                key={index}
                style={{ height: `${height}%` }}
                className="flex-1 rounded-t-sm bg-gradient-to-t from-primary/25 to-primary/75"
              />
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-border/70 bg-background/60 p-3 sm:col-span-2">
          <p className="text-[11px] font-semibold text-foreground">Activity</p>
          <div className="mt-2.5 space-y-2">
            {activity.map((row) => (
              <div key={row.text} className="flex items-start gap-2">
                <span
                  className={cn(
                    "mt-[3px] h-1.5 w-1.5 shrink-0 rounded-full",
                    row.tone === "success" ? "bg-success" : row.tone === "primary" ? "bg-primary" : "bg-muted-foreground/60",
                  )}
                />
                <div className="min-w-0">
                  <p className="truncate text-[10.5px] text-foreground">{row.text}</p>
                  <p className="text-[9px] text-muted-foreground/80">{row.when}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function ScoresScreen() {
  const rows = [
    { name: "Amaka Okafor", no: "BFA/2024/018", ca1: "18", ca2: "17", exam: "58", total: 93, grade: "A" },
    { name: "Ibrahim Yusuf", no: "BFA/2024/021", ca1: "15", ca2: "16", exam: "51", total: 82, grade: "A" },
    { name: "Grace Adeyemi", no: "BFA/2024/007", ca1: "13", ca2: "12", exam: "44", total: 69, grade: "B" },
    { name: "Tobi Balogun", no: "BFA/2024/033", ca1: "11", ca2: "10", exam: "38", total: 59, grade: "C" },
    { name: "Nneka Eze", no: "BFA/2024/012", ca1: "16", ca2: "15", exam: "55", total: 86, grade: "A" },
  ];

  return (
    <div className="space-y-3">
      <ScreenHeading title="Mathematics · JSS 2B" subtitle="First Term · score entry" chip="Open" />

      <div className="flex items-center justify-between gap-2 rounded-lg border border-border/70 bg-muted/30 px-2.5 py-1.5">
        <span className="text-[10px] text-muted-foreground">6 of 32 students shown</span>
        <span className="inline-flex items-center gap-1 rounded-md bg-primary px-2 py-1 text-[9.5px] font-semibold text-primary-foreground">
          <Download className="h-2.5 w-2.5" />
          Download spreadsheet
        </span>
      </div>

      <div className="overflow-hidden rounded-xl border border-border/70">
        <table className="w-full text-[10.5px]">
          <thead className="bg-muted/60">
            <tr className="text-muted-foreground">
              <th className="px-2.5 py-1.5 text-left font-medium">Student</th>
              <th className="px-2 py-1.5 text-center font-medium">CA 1</th>
              <th className="px-2 py-1.5 text-center font-medium">CA 2</th>
              <th className="px-2 py-1.5 text-center font-medium">Exam</th>
              <th className="px-2 py-1.5 text-center font-medium">Total</th>
              <th className="px-2 py-1.5 text-center font-medium">Grade</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.no} className="border-t border-border/60">
                <td className="px-2.5 py-1.5">
                  <p className="truncate font-medium text-foreground">{row.name}</p>
                  <p className="font-mono text-[9px] text-muted-foreground">{row.no}</p>
                </td>
                <td className="px-2 py-1.5 text-center text-muted-foreground">{row.ca1}</td>
                <td className="px-2 py-1.5 text-center text-muted-foreground">{row.ca2}</td>
                <td className="px-2 py-1.5 text-center text-muted-foreground">{row.exam}</td>
                <td className="px-2 py-1.5 text-center font-semibold text-foreground">{row.total}</td>
                <td className="px-2 py-1.5 text-center">
                  <span className={cn("rounded-full border px-1.5 py-0.5 text-[9px] font-bold", CHIP.primary)}>
                    {row.grade}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function FeesScreen() {
  const invoices = [
    { student: "Amaka Okafor", amount: "₦185,000", status: "Paid", tone: "success" },
    { student: "Ibrahim Yusuf", amount: "₦92,500", status: "Part-paid", tone: "warning" },
    { student: "Tobi Balogun", amount: "₦185,000", status: "Overdue", tone: "muted" },
    { student: "Grace Adeyemi", amount: "₦185,000", status: "Paid", tone: "success" },
  ];

  return (
    <div className="space-y-3">
      <ScreenHeading title="Fees & billing" subtitle="First Term · JSS 2B" chip="84% collected" />

      <div className="grid grid-cols-3 gap-2.5">
        <Kpi label="Invoiced" value="₦21.9m" note="Term total" />
        <Kpi label="Collected" value="₦18.4m" note="84% of invoiced" tone="text-success" />
        <Kpi label="Outstanding" value="₦3.5m" note="41 students" tone="text-warning" />
      </div>

      <div className="rounded-xl border border-border/70 bg-background/60 p-3">
        <div className="flex items-center justify-between">
          <p className="text-[11px] font-semibold text-foreground">Term collection</p>
          <Wallet className="h-3.5 w-3.5 text-muted-foreground" />
        </div>
        <div className="mt-2.5 h-2 w-full overflow-hidden rounded-full bg-muted">
          <div className="h-full w-[84%] rounded-full bg-gradient-to-r from-primary to-primary/60" />
        </div>
        <div className="mt-3 space-y-1.5">
          {invoices.map((invoice) => (
            <div key={invoice.student} className="flex items-center justify-between gap-2 border-t border-border/50 pt-1.5 first:border-0 first:pt-0">
              <span className="truncate text-[10.5px] text-foreground">{invoice.student}</span>
              <span className="flex shrink-0 items-center gap-2">
                <span className="text-[10.5px] font-medium text-muted-foreground">{invoice.amount}</span>
                <span className={cn("rounded-full border px-1.5 py-0.5 text-[9px] font-semibold", CHIP[invoice.tone])}>
                  {invoice.status}
                </span>
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function ReportCardScreen() {
  const subjects = [
    { name: "Mathematics", total: 93, grade: "A", remark: "Excellent" },
    { name: "Basic Science", total: 86, grade: "A", remark: "Excellent" },
    { name: "English Language", total: 74, grade: "B", remark: "Very good" },
    { name: "Social Studies", total: 68, grade: "B", remark: "Very good" },
    { name: "Civic Education", total: 61, grade: "C", remark: "Good" },
  ];

  return (
    <div className="space-y-3">
      <ScreenHeading title="Report card" subtitle="Amaka Okafor · JSS 2B" chip="Published" />

      <div className="rounded-xl border border-border/70 bg-card p-3.5 shadow-card">
        <div className="flex items-start justify-between gap-3 border-b border-border/60 pb-2.5">
          <div>
            <p className="text-[12px] font-bold tracking-tight text-foreground">Brightfield Academy</p>
            <p className="text-[9.5px] text-muted-foreground">First Term Report · 2025 / 2026</p>
          </div>
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-primary/12">
            <Award className="h-3.5 w-3.5 text-primary" />
          </span>
        </div>

        <table className="mt-2.5 w-full text-[10.5px]">
          <thead>
            <tr className="text-muted-foreground">
              <th className="py-1 text-left font-medium">Subject</th>
              <th className="py-1 text-right font-medium">Total</th>
              <th className="py-1 text-right font-medium">Grade</th>
              <th className="hidden py-1 text-right font-medium sm:table-cell">Remark</th>
            </tr>
          </thead>
          <tbody>
            {subjects.map((subject) => (
              <tr key={subject.name} className="border-t border-border/50">
                <td className="py-1 font-medium text-foreground">{subject.name}</td>
                <td className="py-1 text-right tabular-nums text-muted-foreground">{subject.total}</td>
                <td className="py-1 text-right font-semibold text-primary">{subject.grade}</td>
                <td className="hidden py-1 text-right text-muted-foreground sm:table-cell">{subject.remark}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-border/60 pt-2.5">
          <span className="text-[10px] text-muted-foreground">
            Total <span className="font-semibold text-foreground">382</span> · Average{" "}
            <span className="font-semibold text-foreground">76.4</span> · Position{" "}
            <span className="font-semibold text-foreground">3rd</span> of 32
          </span>
          <span className="rounded-md border border-primary/30 bg-primary/10 px-2 py-1 font-mono text-[9.5px] font-semibold uppercase tracking-wider text-primary">
            BFA-7K42Q
          </span>
        </div>
      </div>

      <p className="text-[9.5px] text-muted-foreground/85">
        A parent opens this with the result code — no account needed.
      </p>
    </div>
  );
}

function AiScreen() {
  return (
    <div className="space-y-3">
      <ScreenHeading title="Clearis AI" subtitle="Grounded in this school's records" chip="Beta" />

      <div className="space-y-2.5">
        <div className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-md bg-primary px-3.5 py-2 text-[11px] text-primary-foreground">
          Which classes have not submitted results yet?
        </div>
        <div className="w-fit max-w-[92%] rounded-2xl rounded-bl-md border border-border/70 bg-background/70 px-3.5 py-2.5">
          <span className="flex items-center gap-1.5 text-[9.5px] font-semibold uppercase tracking-wide text-muted-foreground">
            <Bot className="h-3 w-3" /> Clearis AI
          </span>
          <p className="mt-1 text-[11px] leading-relaxed text-foreground">
            Two classes are outstanding for First Term: JSS 1A has Mathematics
            pending, and SSS 2C has Physics. Both are still open for entry.
          </p>
        </div>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {["Fees not paid this term", "Best performing subject", "Draft a lesson plan"].map((prompt) => (
          <span
            key={prompt}
            className="rounded-full border border-border/70 bg-muted/50 px-2.5 py-1 text-[9.5px] text-muted-foreground"
          >
            {prompt}
          </span>
        ))}
      </div>
    </div>
  );
}

/* ──────────────────────────────── Slider ──────────────────────────────── */

const SLIDES: {
  id: string;
  icon: LucideIcon;
  label: string;
  caption: string;
  /** Which sidebar row lights up while this screen is showing. */
  nav: string | null;
  screen: React.ReactNode;
}[] = [
  {
    id: "overview",
    icon: LayoutDashboard,
    label: "Overview",
    caption: "One dashboard for the term — enrolment, collections and results.",
    nav: "Overview",
    screen: <OverviewScreen />,
  },
  {
    id: "scores",
    icon: ClipboardCheck,
    label: "Score entry",
    caption: "Teachers enter marks for their own classes and export the sheet in one click.",
    nav: "Results",
    screen: <ScoresScreen />,
  },
  {
    id: "fees",
    icon: Wallet,
    label: "Fees",
    caption: "Fee structures, invoices, payments and every student's running balance.",
    nav: "Fees",
    screen: <FeesScreen />,
  },
  {
    id: "report-card",
    icon: FileText,
    label: "Report cards",
    caption: "Cards built from the approved snapshot, in your school's own design.",
    nav: "Report cards",
    screen: <ReportCardScreen />,
  },
  {
    id: "ai",
    icon: Bot,
    label: "Clearis AI",
    caption: "Ask your own records a question and get an answer built from real rows.",
    nav: null,
    screen: <AiScreen />,
  },
];

export function LandingProductSlider() {
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);
  const reduceMotion = useReducedMotion();
  const total = SLIDES.length;

  const go = useCallback(
    (next: number) => setIndex(((next % total) + total) % total),
    [total],
  );

  // Advance on its own — this is the whole point of the slider, so nothing
  // incidental stops it. A timeout rather than an interval, keyed on the index,
  // means the full delay is granted after every change including a manual one,
  // so picking a screen never gets yanked away a moment later.
  //
  // Reduced motion does not switch the rotation off (the content would then
  // never change); it removes the movement, leaving a plain cross-fade. The
  // explicit pause button is the control WCAG 2.2.2 asks for.
  useEffect(() => {
    if (paused) return;
    const timer = setTimeout(() => setIndex((current) => (current + 1) % total), ROTATE_MS);
    return () => clearTimeout(timer);
  }, [paused, total, index]);

  const active = SLIDES[index];

  return (
    <div className="relative">
      {/* Browser frame */}
      <div className="overflow-hidden rounded-2xl border border-border/70 bg-card shadow-[0_40px_120px_-40px_rgba(124,58,237,0.45)]">
        <div className="flex items-center gap-3 border-b border-border/60 bg-muted/40 px-4 py-2.5">
          <div className="flex gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-destructive/40" />
            <span className="h-2.5 w-2.5 rounded-full bg-warning/50" />
            <span className="h-2.5 w-2.5 rounded-full bg-success/50" />
          </div>
          <div className="mx-auto hidden max-w-[300px] flex-1 items-center justify-center gap-1.5 rounded-md border border-border/60 bg-background/70 px-3 py-1 text-[10.5px] text-muted-foreground sm:flex">
            <Search className="h-3 w-3" />
            clearis.site/{active.id}
          </div>
        </div>

        <div className="flex">
          {/* Sidebar */}
          <aside className="hidden w-[150px] shrink-0 border-r border-border/60 bg-muted/20 p-3 sm:block">
            <div className="space-y-0.5">
              {FRAME_NAV.map(({ icon: Icon, label }) => {
                const isActive = label === active.nav;
                return (
                  <div
                    key={label}
                    className={cn(
                      "flex items-center gap-2 rounded-lg px-2.5 py-2 text-[11.5px] transition-colors",
                      isActive
                        ? "bg-primary/12 font-semibold text-primary"
                        : "text-muted-foreground",
                    )}
                  >
                    <Icon className="h-3.5 w-3.5" />
                    {label}
                  </div>
                );
              })}
            </div>
            <div className="mt-4 rounded-lg border border-primary/25 bg-primary/[0.07] p-2.5">
              <div className="flex items-center gap-1.5 text-[10.5px] font-semibold text-primary">
                <Sparkles className="h-3 w-3" />
                Clearis AI
              </div>
              <p className="mt-1 text-[10px] leading-snug text-muted-foreground">
                Ask your school&apos;s records anything.
              </p>
            </div>
          </aside>

          {/* Screens are stacked into a single grid cell so the frame keeps one
              height while layers cross-fade, instead of resizing per slide. */}
          <div className="grid min-w-0 flex-1 p-4 sm:p-5">
            {SLIDES.map((slide, slideIndex) => {
              const isActive = slideIndex === index;
              return (
                <motion.div
                  key={slide.id}
                  aria-hidden={!isActive}
                  className="col-start-1 row-start-1"
                  animate={{
                    opacity: isActive ? 1 : 0,
                    x: reduceMotion ? 0 : isActive ? 0 : slideIndex < index ? -28 : 28,
                    filter: reduceMotion ? "none" : isActive ? "blur(0px)" : "blur(6px)",
                  }}
                  transition={{ duration: 0.5, ease: EASE }}
                  style={{ pointerEvents: isActive ? "auto" : "none" }}
                >
                  {slide.screen}
                </motion.div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Controls */}
      <div className="mt-5 flex flex-col items-center gap-3">
        <div className="flex flex-wrap items-center justify-center gap-1.5">
          {SLIDES.map((slide, slideIndex) => (
            <button
              key={slide.id}
              type="button"
              onClick={() => go(slideIndex)}
              aria-label={`Show ${slide.label}`}
              aria-current={slideIndex === index}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[11.5px] font-medium transition-colors",
                slideIndex === index
                  ? "border-primary/40 bg-primary/12 text-primary"
                  : "border-border/70 bg-card/60 text-muted-foreground hover:text-foreground",
              )}
            >
              <slide.icon className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">{slide.label}</span>
            </button>
          ))}

          <button
            type="button"
            onClick={() => setPaused((value) => !value)}
            aria-label={paused ? "Resume the rotating screens" : "Pause the rotating screens"}
            className="inline-flex h-[30px] w-[30px] items-center justify-center rounded-full border border-border/70 bg-card/60 text-muted-foreground transition-colors hover:text-foreground"
          >
            {paused ? <Play className="h-3.5 w-3.5" /> : <Pause className="h-3.5 w-3.5" />}
          </button>
        </div>

        <p className="text-center text-[12.5px] text-muted-foreground" aria-live="polite">
          {active.caption}
        </p>

        {/* The track stays in the layout at all times so pausing never shifts
            the caption; only the fill fades out. */}
        <div
          className={cn(
            "h-[3px] w-40 overflow-hidden rounded-full bg-muted transition-opacity duration-200",
            (paused || reduceMotion) && "opacity-0",
          )}
          aria-hidden
        >
          <motion.div
            key={index}
            className="h-full rounded-full bg-primary"
            initial={{ width: "0%" }}
            animate={{ width: "100%" }}
            transition={{ duration: ROTATE_MS / 1000, ease: "linear" }}
          />
        </div>
      </div>
    </div>
  );
}
