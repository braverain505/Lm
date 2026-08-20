"use client";

import { Lock, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/providers/auth-provider";

/**
 * Premium gate for AI features. When the active school hasn't subscribed
 * (``ai_enabled`` false), show a friendly "premium feature — kindly subscribe"
 * panel in place of the AI surface. Keeps the page navigable, just locks AI.
 */
export function useAiEnabled(): boolean {
  const { activeSchool } = useAuth();
  return activeSchool?.ai_enabled ?? false;
}

export function PremiumLock({ compact = false }: { compact?: boolean }) {
  const { user } = useAuth();
  const isPlatformAdmin = user?.is_superadmin ?? false;

  if (compact) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm">
        <Lock className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
        <span className="text-amber-700 dark:text-amber-300">
          This is a premium feature. Kindly subscribe.
        </span>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center gap-3 rounded-2xl border border-amber-500/30 bg-gradient-to-b from-amber-500/10 to-transparent px-6 py-14 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-amber-500/15">
        <Sparkles className="h-7 w-7 text-amber-600 dark:text-amber-400" />
      </div>
      <Badge variant="warning">Premium</Badge>
      <h2 className="text-xl font-semibold">Lumo AI is a premium feature</h2>
      <p className="max-w-md text-sm text-muted-foreground">
        Your school hasn&apos;t activated the AI plan yet. Once your subscription
        is confirmed, your Lumo administrator will switch it on and every AI
        tool becomes available automatically.
      </p>
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Lock className="h-3.5 w-3.5" />
        {isPlatformAdmin
          ? "Tip: enable it for this school from the Lumo Admin dashboard."
          : "Kindly subscribe — reach out to your school owner."}
      </div>
      {isPlatformAdmin && (
        <Button asChild variant="outline" size="sm" className="mt-1">
          <a href="/admin">Open Lumo Admin</a>
        </Button>
      )}
    </div>
  );
}