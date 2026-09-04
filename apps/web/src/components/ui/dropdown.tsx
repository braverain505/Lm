"use client";

import * as React from "react";
import { motion, AnimatePresence } from "framer-motion";

import { cn } from "@/lib/utils";

interface DropdownProps {
  trigger: React.ReactNode;
  children: React.ReactNode | ((close: () => void) => React.ReactNode);
  align?: "start" | "end";
  className?: string;
  contentClassName?: string;
  onOpenChange?: (open: boolean) => void;
}

export function Dropdown({ trigger, children, align = "end", className, contentClassName, onOpenChange }: DropdownProps) {
  const [open, setOpenRaw] = React.useState(false);
  const rootRef = React.useRef<HTMLDivElement>(null);

  const setOpen = React.useCallback((v: boolean | ((prev: boolean) => boolean)) => {
    setOpenRaw((prev) => {
      const next = typeof v === "function" ? v(prev) : v;
      onOpenChange?.(next);
      return next;
    });
  }, [onOpenChange]);

  React.useEffect(() => {
    if (!open) return;
    function onClick(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, setOpen]);

  return (
    <div ref={rootRef} className={cn("relative", className)}>
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="rounded-xl outline-none transition-all duration-150"
      >
        {trigger}
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            role="menu"
            className={cn(
              "absolute z-50 mt-2 min-w-56 overflow-hidden rounded-xl border border-border/60 bg-card p-1.5 shadow-pop",
              align === "end" ? "right-0" : "left-0",
              contentClassName,
            )}
            initial={{ opacity: 0, scale: 0.96, y: -4 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: -4 }}
            transition={{ duration: 0.15, ease: [0.25, 0.46, 0.45, 0.94] }}
          >
            {typeof children === "function" ? children(() => setOpen(false)) : children}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

interface MenuItemProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  icon?: React.ReactNode;
  variant?: "default" | "danger";
}

export function MenuItem({ className, icon, variant = "default", children, ...props }: MenuItemProps) {
  return (
    <button
      role="menuitem"
      className={cn(
        "flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-[13px] font-medium transition-all duration-150 hover:translate-x-[2px] active:scale-[0.98]",
        variant === "danger"
          ? "text-destructive hover:bg-destructive/8"
          : "text-foreground hover:bg-accent",
        className,
      )}
      {...props}
    >
      {icon && <span className="shrink-0 text-muted-foreground [.text-destructive_&]:text-destructive">{icon}</span>}
      <span className="flex-1 truncate">{children}</span>
    </button>
  );
}

export function MenuLabel({ className, children }: { className?: string; children: React.ReactNode }) {
  return (
    <p className={cn("px-3 pb-1.5 pt-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/60", className)}>
      {children}
    </p>
  );
}

export function MenuSeparator({ className }: { className?: string }) {
  return <div className={cn("my-1 h-px bg-border/60", className)} />;
}
