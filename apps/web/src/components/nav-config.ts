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
  /** Permission code required to see this item (null = always visible). */
  perm: string | null;
  /** Only visible to Lumo platform admins (User.is_superadmin). */
  platformAdmin?: boolean;
  /** Role codes allowed to see this item. If omitted, all roles with the required perm can see it. */
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
    label: "Academic",
    items: [
      { href: "/students", label: "Students", icon: Users, perm: "students.view", roles: ["super_admin", "admin", "principal", "vp_academics", "accountant"] },
      { href: "/teachers", label: "Teachers", icon: GraduationCap, perm: "staff.view", roles: ["super_admin", "admin", "principal", "vp_academics", "accountant"] },
      { href: "/classes", label: "Classes", icon: BookOpen, perm: "academics.view", roles: ["super_admin", "admin", "principal", "vp_academics"] },
      { href: "/classes?view=subjects", label: "Subjects", icon: BookOpen, perm: "academics.manage", roles: ["super_admin", "admin", "principal", "vp_academics"] },
      { href: "/results", label: "Results", icon: ClipboardCheck, perm: "results.view", roles: ["admin", "principal", "vp_academics", "accountant", "teacher", "homeroom_teacher"] },
      { href: "/results/score", label: "Enter Scores", icon: NotebookPen, perm: "results.enter", roles: ["teacher", "homeroom_teacher"] },
      { href: "/readiness", label: "Readiness", icon: BarChart3, perm: "results.view", roles: ["admin", "principal", "vp_academics", "accountant"] },
      { href: "/approvals", label: "Process Results", icon: ListChecks, perm: "results.verify", roles: ["admin", "principal", "vp_academics"] },
      { href: "/reports", label: "Generate Report Cards", icon: FileText, perm: "results.view", roles: ["admin", "principal", "vp_academics", "accountant"] },
      { href: "/attendance", label: "Attendance", icon: CalendarCheck, perm: "attendance.view" },
    ],
  },
  {
    label: "Result Generation",
    items: [
      { href: "/attendance", label: "Attendance", icon: CalendarCheck, perm: "attendance.view", roles: ["super_admin", "admin", "principal", "vp_academics"] },
      { href: "/question-banks", label: "CBT", icon: MonitorPlay, perm: "results.comment", roles: ["super_admin", "admin", "principal", "vp_academics"] },
      { href: "/reports?view=term", label: "Term Report", icon: FileText, perm: "results.view", roles: ["super_admin", "admin", "principal", "vp_academics"] },
      { href: "/reports?view=session", label: "Session Report", icon: FileText, perm: "results.view", roles: ["super_admin", "admin", "principal", "vp_academics"] },
      { href: "/reports?view=student", label: "Student Report", icon: FileText, perm: "results.view", roles: ["super_admin", "admin", "principal", "vp_academics"] },
      { href: "/reports?view=early-years", label: "Early Years Report", icon: FileText, perm: "results.view", roles: ["super_admin", "admin", "principal", "vp_academics"] },
      { href: "/readiness", label: "Subject Performance", icon: BarChart3, perm: "results.view", roles: ["super_admin", "admin", "principal", "vp_academics"] },
      { href: "/reports?view=broadsheet", label: "Broadsheet", icon: PieChart, perm: "results.view", roles: ["super_admin", "admin", "principal", "vp_academics"] },
      { href: "/reports?view=cumulative", label: "Cumulative Broadsheet", icon: PieChart, perm: "results.view", roles: ["super_admin", "admin", "principal", "vp_academics"] },
      { href: "/results/comments", label: "Teacher Comments", icon: MessageSquareText, perm: "results.comment", roles: ["super_admin", "admin", "principal", "vp_academics"] },
      { href: "/approvals", label: "Publish Results", icon: ListChecks, perm: "results.verify", roles: ["super_admin", "admin", "principal", "vp_academics"] },
      { href: "/settings", label: "Result Settings", icon: SlidersHorizontal, perm: "school.manage", roles: ["super_admin", "admin", "principal", "vp_academics"] },
      { href: "/teachers", label: "Users", icon: UsersRound, perm: "staff.view", roles: ["super_admin", "admin", "principal", "vp_academics"] },
    ],
  },
  {
    label: "Administration",
    items: [
      { href: "/teachers", label: "Staff", icon: GraduationCap, perm: "staff.view", roles: ["super_admin", "admin", "principal", "vp_academics", "accountant"] },
      { href: "/students", label: "Admissions", icon: UserPlus, perm: "students.view", roles: ["super_admin", "admin", "principal", "vp_academics", "accountant"] },
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
    label: "AI",
    items: [
      { href: "/copilot", label: "Lumo AI", icon: Bot, perm: "ai.copilot" },
      { href: "/lesson-plans", label: "AI Lesson Plans", icon: NotebookPen, perm: "results.comment" },
      { href: "/question-banks", label: "AI Questions", icon: HelpCircle, perm: "results.comment" },
      { href: "/dashboard", label: "AI Insights", icon: Sparkles, perm: "ai.copilot" },
    ],
  },
  {
    label: "Lumo",
     items: [{ href: "/admin", label: "All Schools", icon: Shield, perm: null, platformAdmin: true }],
  },
  {
    label: "Reports",
    items: [
      { href: "/reports", label: "Academic Reports", icon: PieChart, perm: "results.view", roles: ["admin", "principal", "vp_academics", "accountant"] },
      { href: "/attendance", label: "Attendance Reports", icon: CalendarCheck, perm: "attendance.view", roles: ["admin", "principal", "vp_academics", "accountant"] },
    ],
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
  "/copilot": { title: "Lumo AI", breadcrumb: "AI" },
  "/settings": { title: "Settings", breadcrumb: "Settings" },
};

export function pageMeta(pathname: string): PageMeta {
  const prefix = Object.keys(PAGE_META)
    .filter((k) => pathname.startsWith(k))
    .sort((a, b) => b.length - a.length)[0];
  const meta: PageMeta | undefined = prefix ? PAGE_META[prefix] : undefined;
  return meta ?? { title: "Lumo", breadcrumb: "" };
}