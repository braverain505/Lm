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
    () => flattenNav(visibleNav(activeSchool?.permissions ?? [], user?.is_superadmin ?? false)),
    [activeSchool?.permissions, user?.is_superadmin],
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

  // Close when navigating.
  useEffect(() => setOpen(false), [pathname]);

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="focus-ring flex h-9 items-center gap-2 rounded-lg border border-input bg-background px-3 text-sm text-muted-foreground shadow-card transition-colors hover:bg-accent/60 sm:w-56"
      >
        <Search className="h-4 w-4 shrink-0" />
        <span className="hidden flex-1 text-left text-[13px] sm:block">Search…</span>
        <kbd className="hidden rounded border bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground sm:block">
          ⌘K
        </kbd>
      </button>

      {open && (
        <div className="absolute right-0 z-50 mt-2 w-72 overflow-hidden rounded-xl border bg-card shadow-pop animate-scale-in sm:w-80">
          <div className="flex items-center gap-2 border-b px-3">
            <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
            <input
              ref={inputRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search Lumo…"
              className="h-10 w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground"
            />
          </div>
          <div className="scrollbar-thin max-h-72 overflow-y-auto p-1.5">
            {results.length === 0 ? (
              <p className="px-3 py-6 text-center text-sm text-muted-foreground">No pages match “{query}”.</p>
            ) : (
              results.map((item) => (
                <Link
                  key={`${item.href}-${item.label}`}
                  href={item.href}
                  onClick={() => setOpen(false)}
                  className={cn(
                    "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors hover:bg-accent",
                    pathname === item.href && "bg-accent",
                  )}
                >
                  <item.icon className="h-4 w-4 shrink-0 text-muted-foreground" />
                  <span className="font-medium">{item.label}</span>
                  <span className="ml-auto text-[11px] text-muted-foreground">{item.href}</span>
                </Link>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}