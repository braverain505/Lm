"use client";

import { CalendarDays, GraduationCap, HelpCircle, Menu } from "lucide-react";
import Link from "next/link";

import { pageMeta } from "@/components/nav-config";
import { Notifications, ProfileMenu } from "@/components/notifications";
import { SearchPalette } from "@/components/search-palette";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useSessionTerm } from "@/providers/session-context";
import { useAuth } from "@/providers/auth-provider";
import { cn } from "@/lib/utils";

interface AppHeaderProps {
  pathname: string;
  onOpenMobileNav: () => void;
}

export function AppHeader({ pathname, onOpenMobileNav }: AppHeaderProps) {
  const { activeSchool } = useAuth();
  const { sessions, terms, session, term, loadingTerms, setSession, setTerm } = useSessionTerm();
  const meta = pageMeta(pathname);

  return (
    <header className="sticky top-0 z-20 flex h-16 shrink-0 items-center gap-3 border-b bg-background/85 px-4 backdrop-blur-xl lg:px-6 print:hidden">
      <button
        onClick={onOpenMobileNav}
        className="focus-ring -ml-1 flex h-9 w-9 items-center justify-center rounded-lg text-muted-foreground hover:bg-accent lg:hidden"
        aria-label="Open navigation"
      >
        <Menu className="h-5 w-5" />
      </button>

      {/* Page title + breadcrumb */}
      <div className="min-w-0">
        <div className="flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground">
          <span className="capitalize">{activeSchool?.role?.name ?? "Workspace"}</span>
          {meta.breadcrumb && (
            <>
              <span className="text-border">/</span>
              <span>{meta.breadcrumb}</span>
            </>
          )}
        </div>
        <h1 className="truncate text-[15px] font-semibold leading-tight tracking-tight">{meta.title}</h1>
      </div>

      <div className="ml-auto flex items-center gap-2">
        {/* Session selector */}
        {sessions.length > 0 && (
          <Select value={session?.id ?? ""} onValueChange={(v) => {
            const s = sessions.find((x) => x.id === v);
            if (s) setSession(s);
          }}>
            <SelectTrigger icon={<CalendarDays className="h-3.5 w-3.5 text-muted-foreground" />} className="hidden h-9 w-auto md:inline-flex">
              <SelectValue placeholder="Session" />
            </SelectTrigger>
            <SelectContent>
              {sessions.map((s) => (
                <SelectItem key={s.id} value={s.id}>
                  {s.name}
                  {s.is_current ? " · Current" : ""}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}

        {/* Term selector */}
        {session && !loadingTerms && terms.length > 0 && (
          <Select value={term?.id ?? ""} onValueChange={(v) => {
            const t = terms.find((x) => x.id === v);
            if (t) setTerm(t);
          }}>
            <SelectTrigger icon={<GraduationCap className="h-3.5 w-3.5 text-muted-foreground" />} className="hidden h-9 w-auto sm:inline-flex">
              <SelectValue placeholder="Term" />
            </SelectTrigger>
            <SelectContent>
              {terms.map((t) => (
                <SelectItem key={t.id} value={t.id}>
                  {t.name}
                  {t.is_current ? " · Current" : ""}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}

        {/* Search */}
        <div className={cn("hidden sm:block")}>
          <SearchPalette />
        </div>

        {/* Help */}
        <Link
          href="/copilot"
          className="focus-ring flex h-9 w-9 items-center justify-center rounded-lg border border-input bg-background text-muted-foreground shadow-card transition-colors hover:bg-accent/60 hover:text-foreground"
          title="Lumo AI help"
          aria-label="Help"
        >
          <HelpCircle className="h-4 w-4" />
        </Link>

        {/* Notifications */}
        <Notifications />

        <span className="hidden h-6 w-px bg-border sm:block" />

        {/* Profile */}
        <ProfileMenu />
      </div>
    </header>
  );
}