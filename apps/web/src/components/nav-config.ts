import type { LucideIcon } from "lucide-react";
import {
  BarChart3,
  BookCopy,
  BookOpen,
  Bot,
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
  Settings,
  Shield,
  Sparkles,
  SlidersHorizontal,
  UserPlus,
  Users,
  UsersRound,
  Wallet,
} from "lucide-react";

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
  { href: "/results", label: "Results", icon: ClipboardCheck, perm: "results.view", roles: ["admin", "principal", "vp_academics", "accountant", "teacher", "homeroom_teacher"] },
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
      { href: "/results", label: "Results", icon: ClipboardCheck, perm: "results.view", roles: ["admin", "principal", "vp_academics", "accountant", "teacher", "homeroom_teacher"] },
      { href: "/results/score", label: "Enter Scores", icon: NotebookPen, perm: "results.enter", roles: ["teacher", "homeroom_teacher"] },
      { href: "/attendance", label: "Attendance", icon: CalendarCheck, perm: "attendance.view" },
      { href: "/classes", label: "Classes", icon: BookOpen, perm: "academics.view", roles: ["super_admin", "admin", "principal", "vp_academics"] },
      { href: "/classes?view=subjects", label: "Subjects", icon: BookOpen, perm: "academics.manage", roles: ["super_admin", "admin", "principal", "vp_academics"] },
      { href: "/timetable", label: "Timetable", icon: CalendarCheck, perm: "academics.view", roles: ["super_admin", "admin", "principal", "vp_academics"] },
      { href: "/readiness", label: "Readiness", icon: BarChart3, perm: "results.view", roles: ["admin", "principal", "vp_academics", "accountant"] },
    ],
  },
  {
    label: "Result Generation",
    items: [
      { href: "/approvals", label: "Process Results", icon: ListChecks, perm: "results.verify", roles: ["admin", "principal", "vp_academics"] },
      { href: "/results/comments", label: "Teacher Comments", icon: MessageSquareText, perm: "results.comment", roles: ["principal", "vp_academics", "homeroom_teacher"] },
      { href: "/reports", label: "Report Cards", icon: FileText, perm: "results.view", roles: ["admin", "principal", "vp_academics", "accountant", "teacher", "homeroom_teacher"] },
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
      { href: "/students", label: "Students", icon: Users, perm: "students.view", roles: ["super_admin", "admin", "principal", "vp_academics", "accountant"] },
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
    label: "Platform",
    items: [{ href: "/admin", label: "All Schools", icon: Shield, perm: null, platformAdmin: true }],
  },
  {
    label: "Settings",
    items: [{ href: "/settings", label: "School Settings", icon: Settings, perm: "school.manage" }],
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
  "/readiness": { title: "Result Readiness", breadcrumb: "Academics" },
  "/approvals": { title: "Approvals", breadcrumb: "Result Generation" },
  "/reports": { title: "Report Cards", breadcrumb: "Result Generation" },
  "/attendance": { title: "Attendance", breadcrumb: "Academics" },
  "/timetable": { title: "Timetable", breadcrumb: "Academics" },
  "/billing": { title: "Fees & Billing", breadcrumb: "Finance" },
  "/payroll": { title: "Payroll", breadcrumb: "Finance" },
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
