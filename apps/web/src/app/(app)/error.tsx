"use client";

import { AlertTriangle, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";

export default function AppError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="flex min-h-[60vh] items-center justify-center p-6">
      <div className="w-full max-w-md rounded-xl border bg-card p-8 text-center shadow-sm">
        <AlertTriangle className="mx-auto h-8 w-8 text-destructive" />
        <h1 className="mt-4 text-lg font-semibold">This page could not load</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Something went wrong while loading this workspace. Try again to refresh the page data.
        </p>
        <Button className="mt-6" onClick={() => reset()}>
          <RefreshCw className="h-4 w-4" /> Try again
        </Button>
      </div>
    </div>
  );
}