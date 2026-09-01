"use client";

import { Moon, Sun, Monitor } from "lucide-react";
import { useTheme } from "next-themes";
import { cn } from "@/lib/utils";

const themes = [
  { value: "light", icon: Sun, label: "Light" },
  { value: "dark", icon: Moon, label: "Dark" },
  { value: "system", icon: Monitor, label: "System" },
] as const;

export function ThemeSwitch({ className }: { className?: string }) {
  const { theme, setTheme } = useTheme();

  return (
    <div className={cn("inline-flex items-center gap-0.5 rounded-md border border-border/40 bg-transparent p-0.5", className)}>
      {themes.map(({ value, icon: Icon, label }) => (
        <button
          key={value}
          onClick={() => setTheme(value)}
          aria-label={label}
          title={label}
          className={cn(
            "flex h-6 w-6 items-center justify-center rounded text-[10px] transition-all duration-100",
            theme === value
              ? "bg-muted text-foreground shadow-xs"
              : "text-muted-foreground/40 hover:text-foreground",
          )}
        >
          <Icon className="h-3 w-3" />
        </button>
      ))}
    </div>
  );
}
