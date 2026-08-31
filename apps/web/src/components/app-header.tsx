"use client";

import { CalendarDays, GraduationCap, HelpCircle, Lock, Menu } from "lucide-react";
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
  const { sessions, terms, session, term, loadingTerms, setSession, setTerm, isTermClosed } = useSessionTerm();
  const meta = pageMeta(pathname);

  return (
    <header className="sticky top-0 z-20 flex h-16 shrink-0 items-center gap-4 border-b border-border/60 bg-background/80 px-4 backdrop-blur-xl sm:px-6 print:hidden">
      <button
        onClick={onOpenMobileNav}
        className="-ml-1 flex h-9 w-9 items-center justify-center rounded-xl text-muted-foreground transition-colors hover:bg-accent hover:text-foreground lg:hidden"
        aria-label="Open navigation"
      >
        <Menu className="h-5 w-5" />
      </button>

      {/* Page title */}
      <div className="min-w-0">
        <div className="flex items-center gap-1.5 text-[10.5px] font-medium uppercase tracking-wider text-muted-foreground/70">
          <span>{activeSchool?.role?.name ?? "Workspace"}</span>
          {meta.breadcrumb && (
            <>
              <span className="text-border">·</span>
              <span>{meta.breadcrumb}</span>
            </>
          )}
        </div>
        <h1 className="mt-0.5 truncate text-[15px] font-semibold tracking-tight">{meta.title}</h1>
      </div>

      <div className="ml-auto flex items-center gap-1.5">
        {/* Closed term indicator */}
        {isTermClosed && (
          <span className="hidden items-center gap-1.5 rounded-full border border-warning/30 bg-warning/10 px-2.5 py-1 text-[11px] font-semibold text-warning sm:inline-flex">
            <Lock className="h-3 w-3" />
            Term closed — read only
          </span>
        )}

        {/* Session selector */}
        {sessions.length > 0 && (
          <Select value={session?.id ?? ""} onValueChange={(v) => {
            const s = sessions.find((x) => x.id === v);
            if (s) setSession(s);
          }}>
            <SelectTrigger icon={<CalendarDays className="h-3.5 w-3.5 text-muted-foreground/60" />} className="hidden h-8 w-auto text-[12.5px] md:inline-flex">
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
            <SelectTrigger icon={<GraduationCap className="h-3.5 w-3.5 text-muted-foreground/60" />} className="hidden h-8 w-auto text-[12.5px] sm:inline-flex">
              <SelectValue placeholder="Term" />
            </SelectTrigger>
            <SelectContent>
              {terms.map((t) => (
                <SelectItem key={t.id} value={t.id}>
                  {t.name}
                  {t.is_current ? " · Current" : ""}
                  {t.status === "closed" ? " · Closed" : ""}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}

        <span className="hidden h-5 w-px bg-border/60 sm:block" />

        {/* Search */}
        <div className="hidden sm:block">
          <SearchPalette />
        </div>

        {/* Help */}
        <Link
          href="/copilot"
          className="flex h-8 w-8 items-center justify-center rounded-xl border border-border/60 bg-background/50 text-muted-foreground/60 transition-all hover:border-border hover:bg-accent hover:text-foreground"
          title="Lumo AI help"
          aria-label="Help"
        >
          <HelpCircle className="h-4 w-4" />
        </Link>

        {/* Notifications */}
        <Notifications />

        <span className="hidden h-5 w-px bg-border/60 sm:block" />

        {/* Profile */}
        <ProfileMenu />
      </div>
    </header>
  );
}
