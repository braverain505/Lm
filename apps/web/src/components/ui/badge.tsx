import * as React from "react";

import { cn } from "@/lib/utils";

type BadgeVariant = "default" | "success" | "warning" | "muted" | "destructive" | "info" | "outline";

const Badge = React.forwardRef<
  HTMLSpanElement,
  React.HTMLAttributes<HTMLSpanElement> & { variant?: BadgeVariant }
>(({ className, variant = "default", ...props }, ref) => (
  <span
    ref={ref}
    className={cn(
      "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium leading-4 transition-colors",
      variant === "default" && "border-transparent bg-primary/10 text-primary",
      variant === "success" && "border-transparent bg-success/10 text-success",
      variant === "warning" && "border-transparent bg-warning/10 text-warning",
      variant === "info" && "border-transparent bg-info/10 text-info",
      variant === "muted" && "border-transparent bg-muted text-muted-foreground",
      variant === "destructive" && "border-transparent bg-destructive/10 text-destructive",
      variant === "outline" && "border-border bg-background text-muted-foreground",
      className,
    )}
    {...props}
  />
));
Badge.displayName = "Badge";

export { Badge };