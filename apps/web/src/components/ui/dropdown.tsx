"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

interface DropdownProps {
  trigger: React.ReactNode;
  children: React.ReactNode | ((close: () => void) => React.ReactNode);
  align?: "start" | "end";
  className?: string;
  contentClassName?: string;
}

/** Lightweight popover menu with outside-click dismissal. */
export function Dropdown({ trigger, children, align = "end", className, contentClassName }: DropdownProps) {
  const [open, setOpen] = React.useState(false);
  const rootRef = React.useRef<HTMLDivElement>(null);

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
  }, [open]);

  return (
    <div ref={rootRef} className={cn("relative", className)}>
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="focus-ring rounded-lg outline-none"
      >
        {trigger}
      </button>
      {open && (
        <div
          role="menu"
          className={cn(
            "absolute z-50 mt-2 min-w-56 overflow-hidden rounded-xl border bg-card p-1.5 shadow-pop animate-scale-in",
            align === "end" ? "right-0" : "left-0",
            contentClassName,
          )}
        >
          {typeof children === "function" ? children(() => setOpen(false)) : children}
        </div>
      )}
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
        "flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-[13px] font-medium transition-colors",
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
    <p className={cn("px-3 pb-1.5 pt-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground", className)}>
      {children}
    </p>
  );
}

export function MenuSeparator({ className }: { className?: string }) {
  return <div className={cn("my-1.5 h-px bg-border", className)} />;
}