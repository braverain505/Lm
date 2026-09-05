"use client";

import { Plus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader } from "@/components/ui/loader";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { usePsychomotor, useSavePsychomotor, useCanEnterResults } from "@/hooks/use-api";

// Configurable achievement vocabulary — schools can pick per row (or add a
// custom level through the text handling in the UI by choosing "Custom…").
export const PSYCHOMOTOR_LEVELS = [
  "Excellent",
  "Very Good",
  "Good",
  "Fair",
  "Poor",
];

const DEFAULT_AREAS = [
  "Handwriting",
  "Physical Education",
  "Sports & Games",
  "Drawing & Painting",
  "ICT Skills",
  "Verbal Reasoning",
  "Social Habits",
];

function LevelSelect({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  const isCustom = !PSYCHOMOTOR_LEVELS.includes(value);
  const [custom, setCustom] = useState(isCustom ? value : "");

  return (
    <div className="flex gap-1.5">
      <Select value={isCustom ? "__custom" : value} onValueChange={(v) => onChange(v === "__custom" ? custom || "Custom" : v)}>
        <SelectTrigger className="w-32">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {PSYCHOMOTOR_LEVELS.map((l) => (
            <SelectItem key={l} value={l}>
              {l}
            </SelectItem>
          ))}
          <SelectItem value="__custom">Custom…</SelectItem>
        </SelectContent>
      </Select>
      {isCustom && (
        <Input
          className="h-9 w-28"
          placeholder="Custom level"
          value={custom}
          onChange={(e) => {
            setCustom(e.target.value);
            onChange(e.target.value || "Custom");
          }}
        />
      )}
    </div>
  );
}

export function PsychomotorEditor({
  studentId,
  termId,
  allowed,
}: {
  studentId: string;
  termId: string;
  /** Override from the report card payload (results.enter OR homeroom teacher). */
  allowed?: boolean;
}) {
  const canEnter = useCanEnterResults();
  const { data: rows = [], isLoading } = usePsychomotor(studentId, termId);
  const save = useSavePsychomotor(studentId, termId);
  const [draft, setDraft] = useState<{ learning_area: string; achievement_level: string }[]>([]);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    setDraft(rows);
    setDirty(false);
  }, [rows]);

  const update = (i: number, patch: Partial<{ learning_area: string; achievement_level: string }>) => {
    setDraft((prev) => prev.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
    setDirty(true);
  };

  if (!(allowed ?? canEnter)) return null;

  return (
    <Card className="print:hidden">
      <div className="border-b px-4 py-3">
        <div className="flex items-center justify-between gap-2">
          <div>
            <h4 className="text-sm font-semibold">Psychomotor &amp; affective</h4>
            <p className="text-xs text-muted-foreground">
              Skills, practical abilities &amp; physical development — areas and achievement
              levels are fully configurable.
            </p>
          </div>
          {dirty && <span className="text-xs font-medium text-warning">unsaved</span>}
        </div>
      </div>
      <div className="space-y-2 px-4 py-3">
        {isLoading ? (
          <div className="flex justify-center py-4">
            <Loader />
          </div>
        ) : draft.length === 0 ? (
          <p className="py-3 text-center text-xs text-muted-foreground">
            No psychomotor rows yet — add the learning areas below.
          </p>
        ) : (
          draft.map((row, i) => (
            <div key={i} className="flex items-center gap-2">
              <Input
                className="h-9 flex-1"
                placeholder="Learning area"
                value={row.learning_area}
                onChange={(e) => update(i, { learning_area: e.target.value })}
              />
              <LevelSelect
                value={row.achievement_level}
                onChange={(v) => update(i, { achievement_level: v })}
              />
              <Button
                variant="ghost"
                size="icon"
                className="text-muted-foreground hover:text-destructive"
                onClick={() => {
                  setDraft((prev) => prev.filter((_, idx) => idx !== i));
                  setDirty(true);
                }}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          ))
        )}

        <div className="flex items-center justify-between gap-2 pt-1">
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setDraft((prev) => [
                ...prev,
                { learning_area: DEFAULT_AREAS[prev.length % DEFAULT_AREAS.length], achievement_level: "Good" },
              ]);
              setDirty(true);
            }}
          >
            <Plus className="h-3.5 w-3.5" /> Add area
          </Button>
          <Button
            size="sm"
            disabled={!dirty || save.isPending}
            onClick={() =>
              save.mutate(
                draft.filter((r) => r.learning_area.trim() !== ""),
                { onSuccess: () => setDirty(false) },
              )
            }
          >
            {save.isPending ? "Saving…" : "Save psychomotor"}
          </Button>
        </div>
      </div>
    </Card>
  );
}