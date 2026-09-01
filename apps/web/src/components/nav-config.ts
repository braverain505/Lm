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

export const NAV_SECTIONS: NavSection[] = [
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
    label: "AI Tools",
    items: [
      { href: "/lesson-plans", label: "Lesson Plans", icon: NotebookPen, perm: "results.comment" },
      { href: "/question-banks", label: "AI Questions", icon: MonitorPlay, perm: "results.comment" },
    ],
  },
  {
    label: "Communication",
    items: [
      { href: "/results/comments", label: "Teacher Comments", icon: MessageSquareText, perm: "results.comment", roles: ["principal", "vp_academics", "homeroom_teacher"] },
    ],
  },
  {
    label: "Administration",
    items: [
      { href: "/students", label: "Students", icon: Users, perm: "students.view", roles: ["super_admin", "admin", "principal", "vp_academics", "accountant"] },
      { href: "/teachers", label: "Teachers", icon: GraduationCap, perm: "staff.view", roles: ["super_admin", "admin", "principal", "vp_academics", "accountant"] },
      { href: "/reports", label: "Report Cards", icon: FileText, perm: "results.view", roles: ["admin", "principal", "vp_academics", "accountant"] },
      { href: "/approvals", label: "Process Results", icon: ListChecks, perm: "results.verify", roles: ["admin", "principal", "vp_academics"] },
      { href: "/copilot", label: "Clearis AI", icon: Bot, perm: "ai.copilot" },
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

/** Visible nav (permission-filtered) used by the sidebar and the search palette. */
export function visibleNav(permissions: string[], isSuperadmin = false, roleCode?: string): NavSection[] {
  return NAV_SECTIONS.map((section) => ({
    ...section,
    items: section.items.filter(
      (item) =>
        (!item.perm || permissions.includes(item.perm)) &&
        (!item.platformAdmin || isSuperadmin) &&
        (!item.roles || (roleCode ? item.roles.includes(roleCode) : false)),
    ),
  })).filter((section) => section.items.length > 0);
}

export function flattenNav(sections: NavSection[]): NavItem[] {
  return sections.flatMap((s) => s.items);
}

interface PageMeta {
  title: string;
  breadcrumb: string;
}

const PAGE_META: Record<string, PageMeta> = {
  "/dashboard": { title: "Dashboard", breadcrumb: "Overview" },
  "/students": { title: "Students", breadcrumb: "Academic" },
  "/teachers": { title: "Teachers & Staff", breadcrumb: "Academic" },
  "/classes": { title: "Classes", breadcrumb: "Academic" },
  "/results": { title: "Results", breadcrumb: "Academic" },
  "/readiness": { title: "Result Readiness", breadcrumb: "Academic" },
  "/approvals": { title: "Approvals", breadcrumb: "Academic" },
  "/reports": { title: "Report Cards", breadcrumb: "Academic" },
  "/attendance": { title: "Attendance", breadcrumb: "Academic" },
  "/timetable": { title: "Timetable", breadcrumb: "Academic" },
  "/billing": { title: "Fees & Billing", breadcrumb: "Finance" },
  "/payroll": { title: "Payroll", breadcrumb: "Finance" },
  "/inventory": { title: "Inventory", breadcrumb: "Administration" },
  "/library": { title: "Library", breadcrumb: "Administration" },
  "/lesson-plans": { title: "AI Lesson Plans", breadcrumb: "AI" },
  "/question-banks": { title: "AI Questions", breadcrumb: "AI" },
  "/copilot": { title: "Clearis AI", breadcrumb: "AI" },
  "/settings": { title: "Settings", breadcrumb: "Settings" },
};

export function pageMeta(pathname: string): PageMeta {
  const prefix = Object.keys(PAGE_META)
    .filter((k) => pathname.startsWith(k))
    .sort((a, b) => b.length - a.length)[0];
  const meta: PageMeta | undefined = prefix ? PAGE_META[prefix] : undefined;
  return meta ?? { title: "Clearis", breadcrumb: "" };
}
