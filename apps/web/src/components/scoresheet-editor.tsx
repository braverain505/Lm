"use client";

import { useEffect, useState } from "react";
import { Plus, SlidersHorizontal, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useReportCardTemplates,
  useScoresheet,
  useSectionDesigns,
  useUpdateScoresheet,
  useUpdateSectionDesigns,
} from "@/hooks/use-api";
import { useToast } from "@/components/toast";
import {
  SECTION_KEYS,
  SECTION_LABELS,
  type Scoresheet,
  type ScoresheetRowInput,
  type SectionKey,
  type SectionMode,
} from "@clearis/shared";

type DraftRow = { key?: string; name: string; max: string };
type Drafts = Record<SectionKey, DraftRow[]>;

const MAX_COMPONENTS = 12;

/** The saved structure as editable rows. */
function toDrafts(rows: Scoresheet["default"]): DraftRow[] {
  return rows.map((row) => ({
    key: row.key,
    name: row.name,
    max: String(row.max_score),
  }));
}

/** Editable rows back into the shape the API stores — one number per row. */
function toInput(rows: DraftRow[]): ScoresheetRowInput[] {
  const marks = marksOf(rows);
  return rows.map((row, index) => ({
    key: row.key,
    name: row.name.trim(),
    max_score: marks[index],
  }));
}

const emptyDrafts = (): Drafts => ({ nursery: [], primary: [], secondary: [] });

const marksOf = (rows: DraftRow[]) =>
  rows.map((row) => {
    const value = Number(row.max);
    return Number.isFinite(value) && value > 0 ? value : 0;
  });

/** Two structures that mark the same things the same way, whatever they are
 * keyed by — a section holding one of these is not a structure of its own. */
const sameStructure = (a: DraftRow[], b: DraftRow[]) =>
  a.length === b.length &&
  a.every((row, index) => {
    const other = b[index];
    return (
      other !== undefined &&
      row.name.trim().toLowerCase() === other.name.trim().toLowerCase() &&
      marksOf([row])[0] === marksOf([other])[0]
    );
  });

const isInvalid = (rows: DraftRow[]) => {
  const marks = marksOf(rows);
  const names = rows.map((row) => row.name.trim().toLowerCase()).filter(Boolean);
  return (
    rows.length === 0 ||
    rows.length > MAX_COMPONENTS ||
    new Set(names).size !== names.length ||
    rows.some((row, index) => !row.name.trim() || marks[index] <= 0)
  );
};

/**
 * Each component's share of the final 100, worked out from its mark limit in
 * proportion to the others. Mirrors the server's rounding: the residue from
 * rounding lands on the largest component so the shares total exactly 100.
 */
function deriveShares(marks: number[]): number[] {
  const total = marks.reduce((sum, mark) => sum + mark, 0);
  if (total <= 0) return marks.map(() => 0);
  const shares = marks.map((mark) => Math.round((mark / total) * 10000) / 100);
  const residue = Math.round((100 - shares.reduce((sum, share) => sum + share, 0)) * 100) / 100;
  if (residue) {
    let largest = 0;
    shares.forEach((share, index) => {
      if (share > shares[largest]) largest = index;
    });
    shares[largest] = Math.round((shares[largest] + residue) * 100) / 100;
  }
  return shares;
}

function RowsEditor({
  rows,
  label,
  onChange,
  onAdd,
  onRemove,
}: {
  rows: DraftRow[];
  label: string;
  onChange: (index: number, patch: Partial<DraftRow>) => void;
  onAdd: () => void;
  onRemove: (index: number) => void;
}) {
  const marks = marksOf(rows);
  const shares = deriveShares(marks);
  const marksTotal = Math.round(marks.reduce((sum, mark) => sum + mark, 0) * 100) / 100;
  const names = rows.map((row) => row.name.trim().toLowerCase()).filter(Boolean);
  const hasDuplicates = new Set(names).size !== names.length;

  return (
    <>
      <div className="hidden gap-3 px-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground sm:grid sm:grid-cols-[1fr_120px_110px_36px]">
        <span>Component</span>
        <span>Marked out of</span>
        <span>Counts</span>
        <span />
      </div>

      <div className="space-y-2">
        {rows.map((row, index) => (
          <div
            key={row.key ?? `new-${index}`}
            className="grid gap-3 rounded-xl border border-border/60 bg-muted/30 p-3 sm:grid-cols-[1fr_120px_110px_36px] sm:items-center sm:p-2"
          >
            <Input
              value={row.name}
              placeholder="e.g. 3rd CA"
              maxLength={60}
              aria-label={`${label} component ${index + 1} name`}
              onChange={(e) => onChange(index, { name: e.target.value })}
            />
            <Input
              type="number"
              min={1}
              max={1000}
              value={row.max}
              placeholder="20"
              aria-label={`${row.name || `${label} component ${index + 1}`} mark limit`}
              onChange={(e) => onChange(index, { max: e.target.value })}
            />
            <span className="text-[12.5px] text-muted-foreground">
              {shares[index] > 0 ? `${shares[index]} of 100` : "—"}
            </span>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label={`Remove ${row.name || "component"}`}
              onClick={() => onRemove(index)}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        ))}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={onAdd}
          disabled={rows.length >= MAX_COMPONENTS}
        >
          <Plus className="h-3.5 w-3.5" />
          Add component
        </Button>
        <span className="text-[12px] text-muted-foreground">
          Marks total <span className="font-medium text-foreground">{marksTotal}</span>
          {" · "}Final result out of{" "}
          <span className="font-medium text-foreground">100</span>
        </span>
      </div>

      {hasDuplicates && (
        <p className="text-[12px] text-destructive">
          Two components share a name — give each one its own.
        </p>
      )}
    </>
  );
}

/**
 * The school's scoresheet, set once in settings and in force until changed.
 *
 * A school decides only what each component is called and what it is marked
 * out of; the share each carries toward the final 100 is derived from those
 * limits, so the result stays on the 0-100 scale every grade band and average
 * assumes.
 *
 * A school with a primary and a secondary section also settles here whether
 * every class follows that one structure or each section has its own — the
 * same decision settles the report card style, so the design each section
 * draws is chosen on this card too.
 */
export function ScoresheetEditor({ canManageDesigns = false }: { canManageDesigns?: boolean }) {
  const { data, isLoading } = useScoresheet();
  const update = useUpdateScoresheet();
  const { toast } = useToast();

  const [mode, setMode] = useState<SectionMode>("same");
  const [shared, setShared] = useState<DraftRow[]>([]);
  const [drafts, setDrafts] = useState<Drafts>(emptyDrafts);
  const [active, setActive] = useState<SectionKey>("primary");
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (data && !dirty) {
      setMode(data.mode);
      setShared(toDrafts(data.default));
      setDrafts({
        nursery: toDrafts(data.sections.nursery),
        primary: toDrafts(data.sections.primary),
        secondary: toDrafts(data.sections.secondary),
      });
    }
  }, [data, dirty]);

  // Live, so the badge follows what the school is typing rather than what was
  // last saved.
  const owns = Object.fromEntries(
    SECTION_KEYS.map((key) => [key, dirty && !sameStructure(drafts[key], shared)]),
  ) as Record<SectionKey, boolean>;

  const invalid =
    isInvalid(shared) ||
    (mode === "separate" && SECTION_KEYS.some((key) => isInvalid(drafts[key])));

  const setRows = (rows: DraftRow[]) => {
    setDirty(true);
    setError(null);
    return rows;
  };

  const mutators = (current: () => DraftRow[], apply: (rows: DraftRow[]) => void) => ({
    onChange: (index: number, patch: Partial<DraftRow>) =>
      apply(setRows(current().map((row, j) => (j === index ? { ...row, ...patch } : row)))),
    onAdd: () => apply(setRows([...current(), { name: "", max: "" }])),
    onRemove: (index: number) =>
      apply(setRows(current().filter((_, j) => j !== index))),
  });

  const sharedMutators = mutators(
    () => shared,
    (rows) => setShared(rows),
  );
  const sectionMutators = mutators(
    () => drafts[active],
    (rows) => setDrafts((current) => ({ ...current, [active]: rows })),
  );

  const save = () => {
    setError(null);
    update.mutate(
      {
        mode,
        default: toInput(shared),
        // A section still marking exactly what the school-wide set marks is
        // sent as null rather than as a copy, so it goes on inheriting — and a
        // later change to the shared set reaches it instead of leaving a
        // silent duplicate behind.
        sections: Object.fromEntries(
          SECTION_KEYS.map((key) => [
            key,
            sameStructure(drafts[key], shared) ? null : toInput(drafts[key]),
          ]),
        ) as Record<SectionKey, ScoresheetRowInput[] | null>,
      },
      {
        onSuccess: (saved) => {
          setShared(toDrafts(saved.default));
          setDrafts({
            nursery: toDrafts(saved.sections.nursery),
            primary: toDrafts(saved.sections.primary),
            secondary: toDrafts(saved.sections.secondary),
          });
          setMode(saved.mode);
          setDirty(false);
          toast(
            saved.locked
              ? "Scoresheet saved — it applies from the next term"
              : "Scoresheet saved",
          );
        },
        onError: (err: Error) => setError(err.message || "Could not save the scoresheet"),
      },
    );
  };

  return (
    <Card className="premium-card">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-[15px]">
          <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-primary/20">
            <SlidersHorizontal className="h-4 w-4 text-primary" />
          </span>
          Scoresheet
        </CardTitle>
        <CardDescription>
          What a subject&apos;s marks are made of. Set it once and every term uses
          it until you change it.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoading ? (
          <Skeleton className="h-32 w-full" />
        ) : (
          <>
            {data?.locked && (
              <p className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-[12px] leading-relaxed text-amber-700 dark:text-amber-300">
                {data.applied_term_name} already has published results, so this
                change will be in force from the next term. Existing results are
                left exactly as they are.
              </p>
            )}

            <div className="space-y-2">
              <p className="text-[12px] font-medium">Who follows this scoresheet?</p>
              <div className="grid gap-2 sm:grid-cols-2" role="radiogroup" aria-label="Who follows this scoresheet">
                {(
                  [
                    ["same", "Every class", "One scoresheet for the whole school"],
                    [
                      "separate",
                      "Per section",
                      "Nursery, primary and secondary each have their own",
                    ],
                  ] as const
                ).map(([value, title, hint]) => (
                  <button
                    key={value}
                    type="button"
                    role="radio"
                    aria-checked={mode === value}
                    onClick={() => {
                      if (mode === value) return;
                      setMode(value);
                      setDirty(true);
                      setError(null);
                    }}
                    className={`rounded-xl border px-4 py-3 text-left transition ${
                      mode === value
                        ? "border-primary/60 bg-primary/10"
                        : "border-border/60 bg-muted/30 hover:border-primary/30"
                    }`}
                  >
                    <span className="block text-[13px] font-medium">{title}</span>
                    <span className="mt-0.5 block text-[11.5px] leading-relaxed text-muted-foreground">
                      {hint}
                    </span>
                  </button>
                ))}
              </div>
            </div>

            {mode === "separate" && (
              <div className="flex flex-wrap gap-1.5 rounded-xl bg-muted/40 p-1">
                {SECTION_KEYS.map((key) => (
                  <button
                    key={key}
                    type="button"
                    aria-pressed={active === key}
                    onClick={() => setActive(key)}
                    className={`flex-1 rounded-lg px-3 py-2 text-[12.5px] font-medium transition ${
                      active === key
                        ? "bg-background shadow-sm"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {SECTION_LABELS[key]}
                    {owns[key] && (
                      <span className="ml-1.5 text-[10px] uppercase tracking-wide text-primary">
                        own
                      </span>
                    )}
                  </button>
                ))}
              </div>
            )}

            {mode === "same" ? (
              <RowsEditor rows={shared} label="Scoresheet" {...sharedMutators} />
            ) : (
              <>
                {!owns[active] && (
                  <p className="rounded-xl border border-border/60 bg-muted/30 px-4 py-3 text-[11.5px] leading-relaxed text-muted-foreground">
                    {SECTION_LABELS[active]} classes follow the school&apos;s
                    scoresheet as it is. Change anything here and{" "}
                    {SECTION_LABELS[active].toLowerCase()} gets its own.
                  </p>
                )}
                <RowsEditor
                  rows={drafts[active]}
                  label={`${SECTION_LABELS[active]} scoresheet`}
                  {...sectionMutators}
                />
              </>
            )}

            {error && <p className="text-[12px] text-destructive">{error}</p>}

            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border/60 pt-4">
              <p className="max-w-md text-[11.5px] leading-relaxed text-muted-foreground/90">
                Each component&apos;s share of the final 100 is worked out from its
                mark limit, so you only decide what each is marked out of.
                {data?.applied_term_name ? ` In force for ${data.applied_term_name}.` : ""}
              </p>
              <Button
                onClick={save}
                disabled={invalid || !dirty || update.isPending}
                isLoading={update.isPending}
              >
                Save scoresheet
              </Button>
            </div>

            {mode === "separate" && <SectionDesigns canManage={canManageDesigns} />}
          </>
        )}
      </CardContent>
    </Card>
  );
}

/**
 * Which report card each section draws.
 *
 * The designs themselves are built in the report card designer; this is only
 * the school saying which one each section gets. A section left on the school
 * default goes on following it, so a school that only marks its primary
 * differently says so once.
 */
function SectionDesigns({ canManage }: { canManage: boolean }) {
  const { data: designs, isLoading } = useSectionDesigns();
  const { data: templates } = useReportCardTemplates();
  const update = useUpdateSectionDesigns();
  const { toast } = useToast();

  const save = (section: SectionKey, templateId: string | null) => {
    update.mutate(
      { [section]: templateId },
      {
        onSuccess: () => toast(`${SECTION_LABELS[section]} report card updated`),
        onError: (err: Error) =>
          toast(err.message || "Could not save the report card", "error"),
      },
    );
  };

  return (
    <div className="space-y-3 rounded-xl border border-border/60 p-4">
      <div>
        <p className="text-[12px] font-medium">Report card for each section</p>
        <p className="mt-0.5 text-[11.5px] leading-relaxed text-muted-foreground">
          {canManage
            ? "Pick a design per section. One left on the default keeps following it."
            : "Only a school admin can change which design a section uses."}
        </p>
      </div>

      {isLoading ? (
        <Skeleton className="h-10 w-full" />
      ) : (
        <div className="space-y-2">
          {SECTION_KEYS.map((key) => {
            const design = designs?.[key];
            return (
              <div key={key} className="grid items-center gap-2 sm:grid-cols-[110px_1fr]">
                <span className="text-[12.5px]">{SECTION_LABELS[key]}</span>
                <Select
                  value={design?.template_id ?? "default"}
                  disabled={!canManage || update.isPending}
                  onValueChange={(value) => save(key, value === "default" ? null : value)}
                >
                  <SelectTrigger aria-label={`${SECTION_LABELS[key]} report card`}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="default">
                      {design?.name ? `School default — ${design.name}` : "School default card"}
                    </SelectItem>
                    {(templates ?? []).map((template) => (
                      <SelectItem key={template.id} value={template.id}>
                        {template.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            );
          })}
          {!SECTION_KEYS.some((key) => designs?.[key]?.applied) && (
            <p className="text-[11.5px] leading-relaxed text-muted-foreground/90">
              A design you pick here applies once this card is saved with
              per-section scoresheets.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
