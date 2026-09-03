import * as React from "react";

import { cn } from "@/lib/utils";

const AVATAR_TONES = [
  "bg-primary/10 text-primary",
  "bg-success/10 text-success",
  "bg-warning/10 text-warning",
  "bg-info/10 text-info",
  "bg-destructive/10 text-destructive",
  "bg-violet-500/10 text-violet-600 dark:text-violet-300",
  "bg-teal-500/10 text-teal-600 dark:text-teal-300",
  "bg-fuchsia-500/10 text-fuchsia-600 dark:text-fuchsia-300",
];

interface AvatarProps extends React.HTMLAttributes<HTMLDivElement> {
  name?: string | null;
  initials?: string;
  size?: "sm" | "default" | "lg";
  src?: string | null;
}

function deriveTone(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = (hash * 31 + name.charCodeAt(i)) >>> 0;
  return AVATAR_TONES[hash % AVATAR_TONES.length];
}

export function initialsOf(name?: string | null): string {
  const clean = (name ?? "U").trim();
  if (!clean) return "U";
  const parts = clean.split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

const Avatar = React.forwardRef<HTMLDivElement, AvatarProps>(
  ({ className, name, initials, size = "default", src, ...props }, ref) => {
    const text = initials ?? initialsOf(name);
    return (
      <div
        ref={ref}
        className={cn(
          "relative inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full font-semibold leading-none",
          size === "sm" && "h-7 w-7 text-[10px]",
          size === "default" && "h-9 w-9 text-[11px]",
          size === "lg" && "h-11 w-11 text-[13px]",
          !src && deriveTone(name ?? "U"),
          className,
        )}
        style={{ backfaceVisibility: 'hidden', WebkitFontSmoothing: 'antialiased' }}
        {...props}
      >
        {src ? (
          <img src={src} alt={name ?? ""} className="h-full w-full object-cover" />
        ) : (
          <span className="flex h-full w-full items-center justify-center">{text}</span>
        )}
      </div>
    );
  },
);
Avatar.displayName = "Avatar";

export { Avatar };
