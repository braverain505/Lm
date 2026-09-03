"use client";

import { Lock, Menu, ChevronRight } from "lucide-react";

import { pageMeta } from "@/components/nav-config";
import { Notifications, ProfileMenu } from "@/components/notifications";
import { SearchPalette } from "@/components/search-palette";
import { AnnouncementBanner } from "@/components/announcement-banner";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useSessionTerm } from "@/providers/session-context";
import { useAuth } from "@/providers/auth-provider";

interface AppHeaderProps {
  pathname: string;
  onOpenMobileNav: () => void;
}

export function AppHeader({ pathname, onOpenMobileNav }: AppHeaderProps) {
  const { activeSchool } = useAuth();
  const { sessions, terms, session, term, loadingTerms, setSession, setTerm, isTermClosed } = useSessionTerm();
  const meta = pageMeta(pathname);

  return (
    <header className="sticky top-0 z-20 print:hidden">
      <AnnouncementBanner />
      <div className="flex h-14 shrink-0 items-center gap-4 border-b border-border/50 bg-background/95 px-5 backdrop-blur-xl sm:px-6 lg:px-8">
      {/* Mobile menu button */}
      <button
        onClick={onOpenMobileNav}
        className="-ml-1.5 flex h-9 w-9 items-center justify-center rounded-xl text-muted-foreground transition-all duration-200 hover:bg-muted hover:text-foreground lg:hidden"
        aria-label="Open navigation"
      >
        <Menu className="h-[18px] w-[18px]" />
      </button>

      {/* Premium Breadcrumb */}
      <div className="min-w-0">
        <nav className="flex items-center gap-2 text-[12px]">
          <span className="font-medium text-muted-foreground/70">Home</span>
          {meta.breadcrumb && (
            <>
              <ChevronRight className="h-3 w-3 text-muted-foreground/40" />
              <span className="font-medium text-muted-foreground/70">{meta.breadcrumb}</span>
            </>
          )}
          <ChevronRight className="h-3 w-3 text-muted-foreground/40" />
          <span className="font-semibold text-foreground">{meta.title}</span>
        </nav>
      </div>

      <div className="ml-auto flex items-center gap-2">
        {/* Closed term indicator */}
        {isTermClosed && (
          <span className="hidden items-center gap-1.5 rounded-lg border border-warning/20 bg-warning/5 px-2.5 py-1.5 text-[11px] font-semibold text-warning sm:inline-flex">
            <Lock className="h-3 w-3" />
            Term closed
          </span>
        )}

        {/* Session selector */}
        {sessions.length > 0 && (
          <Select value={session?.id ?? ""} onValueChange={(v) => {
            const s = sessions.find((x) => x.id === v);
            if (s) setSession(s);
          }}>
            <SelectTrigger icon={null} className="hidden h-8 w-auto border-border/30 bg-transparent text-[12px] font-medium hover:bg-muted transition-colors md:inline-flex">
              <SelectValue placeholder="Session" />
            </SelectTrigger>
            <SelectContent>
              {sessions.map((s) => (
                <SelectItem key={s.id} value={s.id}>
                  {s.name}{s.is_current ? " · Current" : ""}
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
            <SelectTrigger icon={null} className="hidden h-8 w-auto border-border/30 bg-transparent text-[12px] font-medium hover:bg-muted transition-colors sm:inline-flex">
              <SelectValue placeholder="Term" />
            </SelectTrigger>
            <SelectContent>
              {terms.map((t) => (
                <SelectItem key={t.id} value={t.id}>
                  {t.name}{t.is_current ? " · Current" : ""}{t.status === "closed" ? " · Closed" : ""}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}

        <span className="hidden h-4 w-px bg-border/30 sm:block" />

        {/* Search */}
        <div className="hidden sm:block">
          <SearchPalette />
        </div>

        {/* Notifications */}
        <Notifications />

        <span className="hidden h-4 w-px bg-border/30 sm:block" />

        {/* Profile */}
        <ProfileMenu />
      </div>
      </div>
    </header>
  );
}
