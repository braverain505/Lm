import * as React from "react";

import { cn } from "@/lib/utils";

interface ProgressProps extends React.HTMLAttributes<HTMLDivElement> {
  value: number;
  indicatorClassName?: string;
  size?: "sm" | "default" | "lg";
  indeterminate?: boolean;
}

const Progress = React.forwardRef<HTMLDivElement, ProgressProps>(
  ({ className, value, indicatorClassName, size = "default", indeterminate, ...props }, ref) => {
    const clamped = Math.max(0, Math.min(100, value));
    return (
      <div
        ref={ref}
        role="progressbar"
        aria-valuenow={Math.round(clamped)}
        aria-valuemin={0}
        aria-valuemax={100}
        className={cn(
          "relative w-full overflow-hidden rounded-full bg-muted/60",
          size === "sm" && "h-1",
          size === "default" && "h-1.5",
          size === "lg" && "h-2",
          className,
        )}
        {...props}
      >
        <div
          className={cn(
            "h-full rounded-full bg-primary transition-[width] duration-500 ease-out",
            indeterminate && "animate-pulse",
            indicatorClassName,
          )}
          style={{ width: `${clamped}%` }}
        />
      </div>
    );
  },
);
Progress.displayName = "Progress";

export { Progress };
