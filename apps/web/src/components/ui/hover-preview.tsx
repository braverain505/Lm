"use client";

import { motion, AnimatePresence } from "framer-motion";
import { Mail, Phone, Calendar, ArrowUpRight } from "lucide-react";
import Link from "next/link";
import { useState, useRef, useCallback } from "react";

import { Avatar } from "@/components/ui/avatar";
import { cn } from "@/lib/utils";

interface PreviewData {
  name: string;
  email?: string;
  phone?: string;
  role?: string;
  department?: string;
  joined?: string;
  avatar?: string;
  href: string;
  stats?: Array<{ label: string; value: string | number }>;
}

export function HoverPreview({
  children,
  data,
  side = "right",
  className,
}: {
  children: React.ReactNode;
  data: PreviewData;
  side?: "left" | "right";
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  const show = useCallback(() => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => setOpen(true), 400);
  }, []);

  const hide = useCallback(() => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => setOpen(false), 200);
  }, []);

  return (
    <div
      className={cn("relative inline-block", className)}
      onMouseEnter={show}
      onMouseLeave={hide}
    >
      {children}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 4 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 4 }}
            transition={{ duration: 0.2, ease: [0.25, 0.46, 0.45, 0.94] }}
            className={cn(
              "absolute z-50 mt-2 w-64 overflow-hidden rounded-2xl border border-white/40 bg-white/95 shadow-[0_12px_36px_rgba(0,0,0,0.12)] backdrop-blur-xl",
              side === "right" ? "left-0" : "right-0",
            )}
            onMouseEnter={show}
            onMouseLeave={hide}
          >
            {/* Header gradient */}
            <div className="relative h-14 bg-gradient-to-r from-primary/10 via-violet-500/10 to-rose-500/10" />

            {/* Avatar */}
            <div className="relative -mt-6 px-4">
              <Avatar
                name={data.name}
                className="h-12 w-12 border-2 border-white shadow-md bg-gradient-to-br from-primary to-primary-hover text-sm font-semibold text-white"
              />
            </div>

            {/* Info */}
            <div className="px-4 pb-4 pt-2">
              <div className="flex items-start justify-between">
                <div className="min-w-0">
                  <p className="text-[13px] font-semibold text-foreground truncate">{data.name}</p>
                  {data.role && (
                    <p className="text-[11px] text-muted-foreground/50">{data.role}{data.department ? ` · ${data.department}` : ""}</p>
                  )}
                </div>
                <Link
                  href={data.href}
                  className="flex h-6 w-6 items-center justify-center rounded-lg bg-primary/10 text-primary transition-colors hover:bg-primary/15"
                >
                  <ArrowUpRight className="h-3 w-3" />
                </Link>
              </div>

              {/* Contact info */}
              <div className="mt-3 space-y-1.5">
                {data.email && (
                  <div className="flex items-center gap-2 text-[10px] text-muted-foreground/45">
                    <Mail className="h-3 w-3 shrink-0" />
                    <span className="truncate">{data.email}</span>
                  </div>
                )}
                {data.phone && (
                  <div className="flex items-center gap-2 text-[10px] text-muted-foreground/45">
                    <Phone className="h-3 w-3 shrink-0" />
                    <span>{data.phone}</span>
                  </div>
                )}
                {data.joined && (
                  <div className="flex items-center gap-2 text-[10px] text-muted-foreground/45">
                    <Calendar className="h-3 w-3 shrink-0" />
                    <span>Joined {data.joined}</span>
                  </div>
                )}
              </div>

              {/* Stats */}
              {data.stats && data.stats.length > 0 && (
                <div className="mt-3 grid grid-cols-3 gap-2 border-t border-border/20 pt-3">
                  {data.stats.map((stat) => (
                    <div key={stat.label} className="text-center">
                      <p className="text-[14px] font-bold text-foreground">{stat.value}</p>
                      <p className="text-[9px] uppercase tracking-wider text-muted-foreground/40">{stat.label}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
