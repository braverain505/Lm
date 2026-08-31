import * as React from "react";

import { cn } from "@/lib/utils";

const AVATAR_TONES = [
  "bg-primary/12 text-primary",
  "bg-emerald-500/12 text-emerald-700 dark:text-emerald-300",
  "bg-amber-500/14 text-amber-700 dark:text-amber-300",
  "bg-sky-500/12 text-sky-700 dark:text-sky-300",
  "bg-rose-500/12 text-rose-700 dark:text-rose-300",
  "bg-violet-500/12 text-violet-700 dark:text-violet-300",
  "bg-teal-500/12 text-teal-700 dark:text-teal-300",
  "bg-fuchsia-500/12 text-fuchsia-700 dark:text-fuchsia-300",
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
          "relative inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full font-semibold",
          size === "sm" && "h-7 w-7 text-[10px]",
          size === "default" && "h-9 w-9 text-[11px]",
          size === "lg" && "h-11 w-11 text-[13px]",
          !src && deriveTone(name ?? "U"),
          className,
        )}
        {...props}
      >
        {src ? (
          <img src={src} alt={name ?? ""} className="h-full w-full object-cover" />
        ) : (
          text
        )}
      </div>
    );
  },
);
Avatar.displayName = "Avatar";

export { Avatar };
