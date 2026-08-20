import { cn } from "@/lib/utils";

export function Loader({ className }: { className?: string }) {
  return (
    <div role="status" aria-label="Loading" className={cn("h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent", className)} />
  );
}