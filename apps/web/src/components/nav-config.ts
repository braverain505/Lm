import type { LucideIcon } from "lucide-react";
import {
  Activity,
  Banknote,
  BarChart3,
  BookCopy,
  BookOpen,
  Bot,
  Calculator,
  CalendarCheck,
  ClipboardCheck,
  FileText,
  GraduationCap,
  HelpCircle,
  LayoutDashboard,
  ListChecks,
  MessageSquareText,
  MonitorPlay,
  NotebookPen,
  Package,
  PieChart,
  Receipt,
  Settings,
  Shield,
  Sparkles,
  SlidersHorizontal,
  UserPlus,
  Users,
  UsersRound,
  Wallet,
} from "lucide-react";

/**
 * The accounting desk belongs to the school Accountant alone.
 *
 * The API enforces this per request (role code + permission); this list only
 * decides what is *shown*, so a bug here can never grant access — it just hides
 * or reveals a link. Kept in one place so the rule is described once.
 */
export const ACCOUNTING_ROLE = "accountant";

/**
 * Report cards are the Exam Office's document. Teachers can enter and view their
 * own scoresheets but never a report card, so the permission below — not
 * ``results.view``, which every teacher holds — is what reveals these links.
 * ``results.report_card`` is granted to the Exam Officer, Principal, VP
 * Academics and the school/ platform admins. The API enforces the same code.
 */
export const REPORT_CARD_PERM = "results.report_card";
export const REPORT_CARD_ROLES = [
  "super_admin",
  "director",
  "principal",
  "vp_academics",
  "exam_officer",
];

/**
 * Roles that work the results desk (they hold ``results.view`` and have a
 * reason to open it). The school owner's role code is ``super_admin`` — there
 * is no "admin" role template, so any list that omits it hides the page from
 * the owner entirely.
 */
const RESULTS_DESK_ROLES = [
  "super_admin",
  "director",
  "principal",
  "vp_academics",
  "head_teacher",
  "academic_coordinator",
  "exam_officer",
  "teacher",
  "homeroom_teacher",
];

/** The leadership half of the desk: school-wide review and reporting. */
const EXAM_OFFICE_ROLES = [
  "super_admin",
  "director",
  "principal",
  "vp_academics",
  "head_teacher",
  "academic_coordinator",
  "exam_officer",
];

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  perm: string | null;
  platformAdmin?: boolean;
  roles?: string[];
}

export interface NavSection {
  label: string;
  items: NavItem[];
}

/**
 * Rail items — shown as icons in the slim vertical rail.
 * Only the most important / frequently-used pages go here.
 */
export const RAIL_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, perm: null },
  { href: "/results", label: "Results", icon: ClipboardCheck, perm: "results.view", roles: RESULTS_DESK_ROLES },
  { href: "/results/score", label: "Enter Scores", icon: NotebookPen, perm: "results.enter", roles: ["teacher", "homeroom_teacher"] },
  { href: "/attendance", label: "Attendance", icon: CalendarCheck, perm: "attendance.view" },
  { href: "/timetable", label: "Timetable", icon: CalendarCheck, perm: "academics.view", roles: ["super_admin", "admin", "principal", "vp_academics"] },
  { href: "/classes", label: "Classes", icon: BookOpen, perm: "academics.view", roles: ["super_admin", "admin", "principal", "vp_academics"] },
  { href: "/lesson-plans", label: "AI Lesson Plans", icon: NotebookPen, perm: "results.comment" },
  { href: "/question-banks", label: "AI Questions", icon: MonitorPlay, perm: "results.comment" },
];

/**
 * Panel sections — shown in the expandable navigation panel.
 * Full grouped navigation with section labels.
 */
export const PANEL_SECTIONS: NavSection[] = [
  {
    label: "Overview",
    items: [{ href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, perm: null }],
  },
  {
    label: "Academics",
    items: [
      { href: "/results", label: "Results", icon: ClipboardCheck, perm: "results.view", roles: RESULTS_DESK_ROLES },
      { href: "/results/score", label: "Enter Scores", icon: NotebookPen, perm: "results.enter", roles: ["teacher", "homeroom_teacher"] },
      { href: "/attendance", label: "Attendance", icon: CalendarCheck, perm: "attendance.view" },
      { href: "/classes", label: "Classes", icon: BookOpen, perm: "academics.view", roles: ["super_admin", "admin", "principal", "vp_academics"] },
      { href: "/classes?view=subjects", label: "Subjects", icon: BookOpen, perm: "academics.manage", roles: ["super_admin", "admin", "principal", "vp_academics"] },
      { href: "/timetable", label: "Timetable", icon: CalendarCheck, perm: "academics.view", roles: ["super_admin", "admin", "principal", "vp_academics"] },
      { href: "/readiness", label: "Readiness", icon: BarChart3, perm: "results.view", roles: EXAM_OFFICE_ROLES },
    ],
  },
  {
    label: "Result Generation",
    items: [
      // The exam office runs the pipeline: ``exam_officer`` holds results.verify
      // (and publish), so it belongs here. The API decides each stage on its own
      // permission, so this link never grants more than the caller already has.
      { href: "/approvals", label: "Process Results", icon: ListChecks, perm: "results.verify", roles: EXAM_OFFICE_ROLES },
      { href: "/results/comments", label: "Teacher Comments", icon: MessageSquareText, perm: "results.comment", roles: [...EXAM_OFFICE_ROLES, "homeroom_teacher"] },
      // Psychomotor is written by score-entry roles and a student's homeroom
      // teacher — the same rule the API applies — so the permission alone
      // decides, with no role list to drift out of sync.
      { href: "/results/psychomotor", label: "Psychomotor", icon: Activity, perm: "results.enter" },
      { href: "/reports", label: "Report Cards", icon: FileText, perm: REPORT_CARD_PERM, roles: REPORT_CARD_ROLES },
    ],
  },
  {
    label: "AI Tools",
    items: [
      { href: "/copilot", label: "Clearis AI", icon: Bot, perm: "ai.copilot" },
      { href: "/lesson-plans", label: "AI Lesson Plans", icon: NotebookPen, perm: "results.comment" },
      { href: "/question-banks", label: "AI Questions", icon: MonitorPlay, perm: "results.comment" },
    ],
  },
  {
    label: "Administration",
    items: [
      // The Exam Office holds ``students.view`` — it needs the roster to issue
      // result codes and read a candidate's record — so it sees this link too.
      { href: "/students", label: "Students", icon: Users, perm: "students.view", roles: ["super_admin", "admin", "principal", "vp_academics", "accountant", "exam_officer"] },
      { href: "/teachers", label: "Teachers", icon: GraduationCap, perm: "staff.view", roles: ["super_admin", "admin", "principal", "vp_academics", "accountant"] },
      { href: "/inventory", label: "Inventory", icon: Package, perm: "inventory.view" },
      { href: "/library", label: "Library", icon: BookCopy, perm: "library.view" },
    ],
  },
  {
    label: "Finance",
    items: [
      { href: "/billing", label: "Fees & Billing", icon: Wallet, perm: "fees.view" },
      { href: "/payroll", label: "Payroll", icon: Wallet, perm: "payroll.view" },
    ],
  },
  {
    // Accountant-only: the ledger, cashbook, debtors and reporting desk.
    label: "Accounting",
    items: [
      { href: "/accounting", label: "Accountant's Desk", icon: Calculator, perm: "accounting.view", roles: [ACCOUNTING_ROLE] },
      { href: "/accounting/expenses", label: "Expenses", icon: Receipt, perm: "accounting.view", roles: [ACCOUNTING_ROLE] },
      { href: "/accounting/cashbook", label: "Cashbook", icon: Banknote, perm: "accounting.view", roles: [ACCOUNTING_ROLE] },
      { href: "/accounting/debtors", label: "Debtors", icon: Users, perm: "accounting.view", roles: [ACCOUNTING_ROLE] },
      { href: "/accounting/concessions", label: "Discounts & Refunds", icon: PieChart, perm: "accounting.view", roles: [ACCOUNTING_ROLE] },
      { href: "/accounting/reports", label: "Reports", icon: BarChart3, perm: "accounting.reports", roles: [ACCOUNTING_ROLE] },
    ],
  },
  {
    label: "Platform",
    items: [{ href: "/admin", label: "All Schools", icon: Shield, perm: null, platformAdmin: true }],
  },
  {
    label: "Settings",
    items: [
      {
        href: "/settings",
        label: "School Settings",
        icon: Settings,
        perm: "school.manage",
        roles: ["super_admin", "director", "admin", "principal"],
      },
    ],
  },
];

// ─── Helpers ────────────────────────────────────────────────────────────────

function matchesPerm(item: NavItem, permissions: string[], isSuperadmin: boolean, roleCode?: string): boolean {
  return (
    (!item.perm || permissions.includes(item.perm)) &&
    (!item.platformAdmin || isSuperadmin) &&
    (!item.roles || (roleCode ? item.roles.includes(roleCode) : false))
  );
}

/** Permission-filtered rail items. */
export function visibleRail(permissions: string[], isSuperadmin = false, roleCode?: string): NavItem[] {
  return RAIL_ITEMS.filter((item) => matchesPerm(item, permissions, isSuperadmin, roleCode));
}

/** Permission-filtered panel sections. */
export function visiblePanel(permissions: string[], isSuperadmin = false, roleCode?: string): NavSection[] {
  return PANEL_SECTIONS.map((section) => ({
    ...section,
    items: section.items.filter((item) => matchesPerm(item, permissions, isSuperadmin, roleCode)),
  })).filter((section) => section.items.length > 0);
}

/** Backward compat — same as visiblePanel. */
export function visibleNav(permissions: string[], isSuperadmin = false, roleCode?: string): NavSection[] {
  return visiblePanel(permissions, isSuperadmin, roleCode);
}

export function flattenNav(sections: NavSection[]): NavItem[] {
  return sections.flatMap((s) => s.items);
}

// ─── Page metadata ──────────────────────────────────────────────────────────

interface PageMeta {
  title: string;
  breadcrumb: string;
}

const PAGE_META: Record<string, PageMeta> = {
  "/dashboard": { title: "Dashboard", breadcrumb: "Overview" },
  "/students": { title: "Students", breadcrumb: "Administration" },
  "/teachers": { title: "Teachers & Staff", breadcrumb: "Administration" },
  "/classes": { title: "Classes", breadcrumb: "Academics" },
  "/results": { title: "Results", breadcrumb: "Academics" },
  "/results/psychomotor": { title: "Psychomotor & Affective", breadcrumb: "Academics" },
  "/readiness": { title: "Result Readiness", breadcrumb: "Academics" },
  "/approvals": { title: "Process Results", breadcrumb: "Result Generation" },
  "/reports": { title: "Report Cards", breadcrumb: "Result Generation" },
  "/attendance": { title: "Attendance", breadcrumb: "Academics" },
  "/timetable": { title: "Timetable", breadcrumb: "Academics" },
  "/billing": { title: "Fees & Billing", breadcrumb: "Finance" },
  "/payroll": { title: "Payroll", breadcrumb: "Finance" },
  "/accounting": { title: "Accountant's Desk", breadcrumb: "Accounting" },
  "/accounting/expenses": { title: "Expenses", breadcrumb: "Accounting" },
  "/accounting/cashbook": { title: "Cashbook", breadcrumb: "Accounting" },
  "/accounting/debtors": { title: "Debtors", breadcrumb: "Accounting" },
  "/accounting/concessions": { title: "Discounts & Refunds", breadcrumb: "Accounting" },
  "/accounting/reports": { title: "Financial Reports", breadcrumb: "Accounting" },
  "/inventory": { title: "Inventory", breadcrumb: "Administration" },
  "/library": { title: "Library", breadcrumb: "Administration" },
  "/lesson-plans": { title: "AI Lesson Plans", breadcrumb: "AI Tools" },
  "/question-banks": { title: "AI Questions", breadcrumb: "AI Tools" },
  "/copilot": { title: "Clearis AI", breadcrumb: "AI Tools" },
  "/settings": { title: "Settings", breadcrumb: "Settings" },
};

export function pageMeta(pathname: string): PageMeta {
  const prefix = Object.keys(PAGE_META)
    .filter((k) => pathname.startsWith(k))
    .sort((a, b) => b.length - a.length)[0];
  const meta: PageMeta | undefined = prefix ? PAGE_META[prefix] : undefined;
  return meta ?? { title: "Clearis", breadcrumb: "" };
}
