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
      "inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10px] font-semibold leading-4 transition-colors",
      variant === "default" && "bg-primary/10 text-primary",
      variant === "success" && "bg-success/10 text-success",
      variant === "warning" && "bg-warning/10 text-warning",
      variant === "info" && "bg-info/10 text-info",
      variant === "muted" && "bg-muted text-muted-foreground",
      variant === "destructive" && "bg-destructive/10 text-destructive",
      variant === "outline" && "border border-border/50 bg-transparent text-muted-foreground",
      className,
    )}
    {...props}
  />
));
Badge.displayName = "Badge";

export { Badge };
