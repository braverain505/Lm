"use client";

import { Save } from "lucide-react";
import { useState } from "react";

import { EmptyState, Panel, PanelSkeleton, fmtNum, titleCase } from "@/components/platform-utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useSaSettings, useSaUpdateSettings } from "@/hooks/use-superadmin";

export default function SuperAdminSettingsPage() {
  const { data, isLoading } = useSaSettings();
  const update = useSaUpdateSettings();
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [saved, setSaved] = useState(false);

  const settings = (data ?? {}) as Record<string, unknown>;
  const keys = Object.keys(settings);

  const valueOf = (k: string): string => {
    if (k in draft) return draft[k];
    const v = settings[k];
    return typeof v === "boolean" ? (v ? "true" : "false") : String(v ?? "");
  };

  const isNumeric = (k: string) => typeof settings[k] === "number" || typeof settings[k] === "boolean";

  function save(e: React.FormEvent) {
    e.preventDefault();
    const updates: Record<string, unknown> = {};
    for (const k of keys) {
      const raw = draft[k];
      if (raw === undefined) continue;
      if (typeof settings[k] === "number") updates[k] = Number(raw);
      else if (typeof settings[k] === "boolean") updates[k] = raw === "true";
      else updates[k] = raw;
    }
    if (Object.keys(updates).length === 0) return;
    update.mutate(updates, { onSuccess: () => setSaved(true) });
  }

  return (
    <div className="space-y-6">
      <Panel
        title="Platform settings"
        subtitle="Global configuration — applies to every tenant"
        action={
          saved && <span className="text-xs font-medium text-success">Saved ✓</span>
        }
      >
        {isLoading ? (
          <PanelSkeleton rows={6} />
        ) : keys.length === 0 ? (
          <EmptyState message="No platform settings yet." />
        ) : (
          <form onSubmit={save} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              {keys.map((k) => (
                <div key={k} className="space-y-1">
                  <Label className="text-xs">{titleCase(k)}</Label>
                  <Input
                    className="h-9"
                    type={isNumeric(k) ? "text" : "text"}
                    value={valueOf(k)}
                    onChange={(e) => {
                      setDraft((d) => ({ ...d, [k]: e.target.value }));
                      setSaved(false);
                    }}
                  />
                  <p className="text-[11px] text-muted-foreground">
                    {typeof settings[k] === "number" ? "numeric" : typeof settings[k] === "boolean" ? "true / false" : "text"}
                  </p>
                </div>
              ))}
            </div>
            <Button type="submit" disabled={update.isPending || Object.keys(draft).length === 0}>
              <Save className="h-4 w-4" /> {update.isPending ? "Saving…" : "Save changes"}
            </Button>
          </form>
        )}
      </Panel>

      <Panel title="Usage reference" subtitle="Derived platform metrics you can reference">
        {isLoading ? (
          <PanelSkeleton rows={3} />
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {keys.filter((k) => k.startsWith("platform.") || k.startsWith("ai.")).map((k) => (
              <div key={k} className="rounded-xl border bg-muted/30 p-3 text-sm">
                <p className="truncate text-xs text-muted-foreground">{titleCase(k)}</p>
                <p className="mt-0.5 font-semibold">
                  {typeof settings[k] === "number" ? fmtNum(settings[k] as number) : String(settings[k])}
                </p>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}