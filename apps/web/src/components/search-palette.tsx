"use client";

import { motion, AnimatePresence } from "framer-motion";
import { Search, ArrowRight, Sparkles } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { flattenNav, visibleNav } from "@/components/nav-config";
import { useAuth } from "@/providers/auth-provider";
import { cn } from "@/lib/utils";

export function SearchPalette() {
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
        className="flex h-9 items-center gap-2 rounded-xl border border-white/40 bg-white/50 px-3 text-[12px] text-muted-foreground/50 transition-all duration-200 hover:border-white/60 hover:bg-white/80 hover:text-foreground hover:shadow-[0_2px_8px_rgba(0,0,0,0.04)] sm:w-52"
      >
        <Search className="h-3.5 w-3.5 shrink-0" strokeWidth={1.75} />
        <span className="hidden flex-1 text-left sm:block">Search pages…</span>
        <kbd className="hidden rounded-lg border border-white/40 bg-white/60 px-1.5 py-px text-[9px] font-semibold text-muted-foreground/40 sm:block">
          ⌘K
        </kbd>
      </button>

      <AnimatePresence>
        {open && (
          <>
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              className="fixed inset-0 z-40 bg-black/20 backdrop-blur-sm"
              onClick={() => setOpen(false)}
            />

            {/* Palette */}
            <motion.div
              initial={{ opacity: 0, scale: 0.96, y: -8 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96, y: -8 }}
              transition={{ duration: 0.2, ease: [0.25, 0.46, 0.45, 0.94] }}
              className="fixed left-1/2 top-[20%] z-50 w-[90vw] max-w-[420px] -translate-x-1/2 overflow-hidden rounded-2xl border border-white/40 bg-white/90 shadow-[0_16px_48px_rgba(0,0,0,0.12)] backdrop-blur-xl"
            >
              {/* Search input */}
              <div className="flex items-center gap-3 border-b border-border/20 px-4">
                <Search className="h-4 w-4 shrink-0 text-muted-foreground/30" strokeWidth={1.75} />
                <input
                  ref={inputRef}
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search pages, actions…"
                  className="h-12 w-full bg-transparent text-[14px] text-foreground outline-none placeholder:text-muted-foreground/30"
                />
                <kbd className="shrink-0 rounded-lg border border-border/30 bg-muted/30 px-1.5 py-0.5 text-[9px] font-semibold text-muted-foreground/40">
                  ESC
                </kbd>
              </div>

              {/* Results */}
              <div className="scrollbar-thin max-h-72 overflow-y-auto p-2">
                {results.length === 0 ? (
                  <div className="flex flex-col items-center gap-2 py-8 text-center">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-muted/30">
                      <Search className="h-4 w-4 text-muted-foreground/30" />
                    </div>
                    <p className="text-[12px] text-muted-foreground/50">No results for &ldquo;{query}&rdquo;</p>
                  </div>
                ) : (
                  <>
                    <p className="px-2 py-1.5 text-[9px] font-semibold uppercase tracking-wider text-muted-foreground/35">
                      {query ? "Results" : "Quick navigation"}
                    </p>
                    {results.map((item, idx) => (
                      <motion.div
                        key={`${item.href}-${item.label}`}
                        initial={{ opacity: 0, y: 4 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.15, delay: idx * 0.02 }}
                      >
                        <Link
                          href={item.href}
                          onClick={() => setOpen(false)}
                          className={cn(
                            "group flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] transition-all duration-150",
                            pathname === item.href
                              ? "bg-primary/5 text-primary"
                              : "text-foreground/70 hover:bg-muted/30 hover:text-foreground",
                          )}
                        >
                          <div className={cn(
                            "flex h-8 w-8 items-center justify-center rounded-lg transition-colors duration-150",
                            pathname === item.href ? "bg-primary/10 text-primary" : "bg-muted/30 text-muted-foreground/40 group-hover:bg-muted/50 group-hover:text-foreground/60",
                          )}>
                            <item.icon className="h-4 w-4" strokeWidth={1.75} />
                          </div>
                          <span className="flex-1 font-medium">{item.label}</span>
                          <ArrowRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground/20 transition-all duration-150 group-hover:translate-x-0.5 group-hover:text-primary/50" />
                        </Link>
                      </motion.div>
                    ))}
                  </>
                )}
              </div>

              {/* Footer */}
              <div className="flex items-center justify-between border-t border-border/20 px-4 py-2.5">
                <div className="flex items-center gap-1.5 text-[9px] text-muted-foreground/30">
                  <Sparkles className="h-2.5 w-2.5" />
                  <span>Powered by Clearis</span>
                </div>
                <div className="flex items-center gap-1">
                  <kbd className="rounded border border-border/20 bg-muted/20 px-1 py-px text-[8px] text-muted-foreground/30">↑↓</kbd>
                  <span className="text-[9px] text-muted-foreground/30">navigate</span>
                  <kbd className="ml-1 rounded border border-border/20 bg-muted/20 px-1 py-px text-[8px] text-muted-foreground/30">↵</kbd>
                  <span className="text-[9px] text-muted-foreground/30">select</span>
                </div>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
