"use client";

import { Lock, Menu } from "lucide-react";

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

interface AppHeaderProps {
  pathname: string;
  onOpenMobileNav: () => void;
}

export function AppHeader({ pathname, onOpenMobileNav }: AppHeaderProps) {
  const { activeSchool } = useAuth();
  const { sessions, terms, session, term, loadingTerms, setSession, setTerm, isTermClosed } = useSessionTerm();
  const meta = pageMeta(pathname);

  return (
    <header className="sticky top-0 z-20 flex h-14 shrink-0 items-center gap-3 border-b border-border/40 bg-background/80 px-4 backdrop-blur-xl sm:px-6 lg:px-8 print:hidden">
      {/* Mobile menu button */}
      <button
        onClick={onOpenMobileNav}
        className="-ml-1 flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground lg:hidden"
        aria-label="Open navigation"
      >
        <Menu className="h-4 w-4" />
      </button>

      {/* Breadcrumb */}
      <div className="min-w-0">
        <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
          <span className="font-medium">{activeSchool?.role?.name ?? "Workspace"}</span>
          {meta.breadcrumb && (
            <>
              <span className="text-border">·</span>
              <span>{meta.breadcrumb}</span>
            </>
          )}
        </div>
        <h1 className="mt-px truncate text-[14px] font-semibold tracking-tight">{meta.title}</h1>
      </div>

      <div className="ml-auto flex items-center gap-1.5">
        {/* Closed term */}
        {isTermClosed && (
          <span className="hidden items-center gap-1.5 rounded-md border border-warning/20 bg-warning/5 px-2 py-1 text-[11px] font-medium text-warning sm:inline-flex">
            <Lock className="h-3 w-3" />
            Term closed
          </span>
        )}

        {/* Session */}
        {sessions.length > 0 && (
          <Select value={session?.id ?? ""} onValueChange={(v) => {
            const s = sessions.find((x) => x.id === v);
            if (s) setSession(s);
          }}>
            <SelectTrigger icon={null} className="hidden h-8 w-auto border-border/40 bg-transparent text-[12px] font-medium md:inline-flex">
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

        {/* Term */}
        {session && !loadingTerms && terms.length > 0 && (
          <Select value={term?.id ?? ""} onValueChange={(v) => {
            const t = terms.find((x) => x.id === v);
            if (t) setTerm(t);
          }}>
            <SelectTrigger icon={null} className="hidden h-8 w-auto border-border/40 bg-transparent text-[12px] font-medium sm:inline-flex">
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

        <span className="hidden h-4 w-px bg-border/40 sm:block" />

        {/* Search */}
        <div className="hidden sm:block">
          <SearchPalette />
        </div>

        {/* Notifications */}
        <Notifications />

        <span className="hidden h-4 w-px bg-border/40 sm:block" />

        {/* Profile */}
        <ProfileMenu />
      </div>
    </header>
  );
}
