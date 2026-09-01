"use client";

import { Search } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { flattenNav, visibleNav } from "@/components/nav-config";
import { useAuth } from "@/providers/auth-provider";
import { cn } from "@/lib/utils";

export function SearchPalette() {
  const router = useRouter();
  const pathname = usePathname();
  const { activeSchool, user } = useAuth();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const items = useMemo(
    () => flattenNav(visibleNav(activeSchool?.permissions ?? [], user?.is_superadmin ?? false, activeSchool?.role?.code ?? undefined)),
    [activeSchool?.permissions, user?.is_superadmin, activeSchool?.role?.code],
  );

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items.slice(0, 8);
    return items.filter((i) => i.label.toLowerCase().includes(q)).slice(0, 8);
  }, [query, items]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (open) {
      setQuery("");
      setTimeout(() => inputRef.current?.focus(), 10);
    }
  }, [open]);

  useEffect(() => setOpen(false), [pathname]);

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex h-8 items-center gap-2 rounded-lg border border-border/40 bg-transparent px-3 text-[12px] text-muted-foreground/50 transition-all duration-100 hover:border-border/60 hover:text-foreground sm:w-48"
      >
        <Search className="h-3.5 w-3.5 shrink-0" />
        <span className="hidden flex-1 text-left sm:block">Search…</span>
        <kbd className="hidden rounded border border-border/30 bg-muted/30 px-1 py-px text-[9px] font-medium text-muted-foreground/40 sm:block">
          ⌘K
        </kbd>
      </button>

      {open && (
        <div className="absolute right-0 z-50 mt-2 w-80 overflow-hidden rounded-xl border border-border/50 bg-card shadow-elevated animate-scale-in">
          <div className="flex items-center gap-2 border-b border-border/30 px-3">
            <Search className="h-4 w-4 shrink-0 text-muted-foreground/30" />
            <input
              ref={inputRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search pages…"
              className="h-10 w-full bg-transparent text-[13px] text-foreground outline-none placeholder:text-muted-foreground/30"
            />
          </div>
          <div className="scrollbar-thin max-h-72 overflow-y-auto p-1.5">
            {results.length === 0 ? (
              <p className="px-3 py-6 text-center text-[12px] text-muted-foreground/40">No results for &ldquo;{query}&rdquo;</p>
            ) : (
              results.map((item) => (
                <Link
                  key={`${item.href}-${item.label}`}
                  href={item.href}
                  onClick={() => setOpen(false)}
                  className={cn(
                    "flex items-center gap-3 rounded-lg px-3 py-2.5 text-[12px] transition-colors duration-100 hover:bg-muted/30",
                    pathname === item.href && "bg-muted/30",
                  )}
                >
                  <item.icon className="h-4 w-4 shrink-0 text-muted-foreground/30" />
                  <span className="font-medium text-foreground/80">{item.label}</span>
                  <span className="ml-auto text-[10px] text-muted-foreground/25">{item.href}</span>
                </Link>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
