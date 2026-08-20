import type { LucideIcon } from "lucide-react";
import {
  Activity,
  AlertTriangle,
  Building2,
  CreditCard,
  FileSearch,
  Globe,
  LayoutDashboard,
  LifeBuoy,
  Megaphone,
  Settings,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  Users,
} from "lucide-react";

export interface PlatformNavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

export interface PlatformNavSection {
  label: string;
  items: PlatformNavItem[];
}

export const PLATFORM_NAV: PlatformNavSection[] = [
  {
    label: "Command center",
    items: [{ href: "/super-admin", label: "Overview", icon: LayoutDashboard }],
  },
  {
    label: "Tenants",
    items: [
      { href: "/super-admin/schools", label: "Schools", icon: Building2 },
      { href: "/super-admin/subscriptions", label: "Subscriptions", icon: CreditCard },
    ],
  },
  {
    label: "Analytics",
    items: [
      { href: "/super-admin/growth", label: "Growth", icon: TrendingUp },
      { href: "/super-admin/revenue", label: "Revenue", icon: CreditCard },
      { href: "/super-admin/ai", label: "AI Usage", icon: Sparkles },
      { href: "/super-admin/users", label: "Users", icon: Users },
      { href: "/super-admin/analytics", label: "Engagement & Geo", icon: Globe },
    ],
  },
  {
    label: "Operations",
    items: [
      { href: "/super-admin/support", label: "Support", icon: LifeBuoy },
      { href: "/super-admin/issues", label: "Issues", icon: AlertTriangle },
      { href: "/super-admin/system", label: "System", icon: Activity },
      { href: "/super-admin/audit", label: "Audit log", icon: FileSearch },
    ],
  },
  {
    label: "Platform",
    items: [
      { href: "/super-admin/settings", label: "Settings", icon: Settings },
      { href: "/super-admin/announcements", label: "Announcements", icon: Megaphone },
    ],
  },
];

export const PLATFORM_META: Record<string, { title: string; breadcrumb: string }> = {
  "/super-admin": { title: "Platform Overview", breadcrumb: "Command center" },
  "/super-admin/schools": { title: "Schools", breadcrumb: "Tenants" },
  "/super-admin/subscriptions": { title: "Subscriptions", breadcrumb: "Tenants" },
  "/super-admin/growth": { title: "Growth", breadcrumb: "Analytics" },
  "/super-admin/revenue": { title: "Revenue", breadcrumb: "Analytics" },
  "/super-admin/ai": { title: "AI Usage", breadcrumb: "Analytics" },
  "/super-admin/users": { title: "Users", breadcrumb: "Analytics" },
  "/super-admin/analytics": { title: "Engagement & Geography", breadcrumb: "Analytics" },
  "/super-admin/support": { title: "Support", breadcrumb: "Operations" },
  "/super-admin/issues": { title: "Issues", breadcrumb: "Operations" },
  "/super-admin/system": { title: "System", breadcrumb: "Operations" },
  "/super-admin/audit": { title: "Audit log", breadcrumb: "Operations" },
  "/super-admin/settings": { title: "Platform Settings", breadcrumb: "Platform" },
  "/super-admin/announcements": { title: "Announcements", breadcrumb: "Platform" },
};

export function platformMeta(pathname: string): { title: string; breadcrumb: string } {
  const prefix = Object.keys(PLATFORM_META)
    .filter((k) => pathname.startsWith(k))
    .sort((a, b) => b.length - a.length)[0];
  const meta = prefix ? PLATFORM_META[prefix] : undefined;
  return meta ?? { title: "Lumo Platform", breadcrumb: "Super admin" };
}

export { ShieldCheck };