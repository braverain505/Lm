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
        className="flex h-8 items-center gap-2 rounded-xl border border-border/60 bg-background/50 px-3 text-[12.5px] text-muted-foreground/60 shadow-sm transition-all duration-150 hover:border-border hover:bg-accent hover:text-foreground sm:w-56"
      >
        <Search className="h-3.5 w-3.5 shrink-0" />
        <span className="hidden flex-1 text-left sm:block">Search…</span>
        <kbd className="hidden rounded-md border border-border/40 bg-muted/50 px-1.5 py-0.5 text-[9.5px] font-medium text-muted-foreground/50 sm:block">
          ⌘K
        </kbd>
      </button>

      {open && (
        <div className="absolute right-0 z-50 mt-2 w-72 overflow-hidden rounded-2xl border border-border/60 bg-card shadow-pop animate-scale-in sm:w-80">
          <div className="flex items-center gap-2 border-b border-border/40 px-3">
            <Search className="h-4 w-4 shrink-0 text-muted-foreground/50" />
            <input
              ref={inputRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search Clearis…"
              className="h-10 w-full bg-transparent text-[13px] outline-none placeholder:text-muted-foreground/50"
            />
          </div>
          <div className="scrollbar-thin max-h-72 overflow-y-auto p-1.5">
            {results.length === 0 ? (
              <p className="px-3 py-6 text-center text-[13px] text-muted-foreground/70">No pages match &ldquo;{query}&rdquo;.</p>
            ) : (
              results.map((item) => (
                <Link
                  key={`${item.href}-${item.label}`}
                  href={item.href}
                  onClick={() => setOpen(false)}
                  className={cn(
                    "flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] transition-colors duration-150 hover:bg-accent",
                    pathname === item.href && "bg-accent",
                  )}
                >
                  <item.icon className="h-4 w-4 shrink-0 text-muted-foreground/50" />
                  <span className="font-medium">{item.label}</span>
                  <span className="ml-auto text-[10.5px] text-muted-foreground/40">{item.href}</span>
                </Link>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
