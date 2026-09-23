"use client";

import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { restrictToVerticalAxis, restrictToWindowEdges } from "@dnd-kit/modifiers";
import {
  SortableContext,
  arrayMove,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import {
  ChevronDown,
  ChevronUp,
  Copy,
  Eye,
  EyeOff,
  GripVertical,
  LayoutTemplate,
  Pencil,
  Plus,
  Trash2,
} from "lucide-react";
import { useMemo, useRef, useState } from "react";

import {
  REPORT_THEMES,
  type ReportCard,
  type ReportLayout,
  type ReportTheme,
  type ReportWidget,
  type ReportWidgetType,
} from "@clearis/shared";

import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ReportCardDocument } from "@/components/report-card-document";
import { REPORT_TEMPLATES } from "@/lib/report-templates";
import {
  WIDGET_CATALOG,
  canAdd,
  moveWidget,
  newWidget,
  prop,
  removeWidget,
  setWidgetProp,
  updateWidget,
  widgetDef,
} from "@/lib/report-layout";
import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------ *
 * The sample card the preview draws.
 *
 * Deliberately synthetic and clearly labelled: the designer must never
 * show a real child's marks, and it must not need a student to exist
 * before a school can design its card. Every field the renderer reads
 * gets a plausible value so no block renders as "—".
 * ------------------------------------------------------------------ */
const U = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;

export const SAMPLE_CARD: ReportCard = {
  school: {
    name: "Brightfield Academy",
    short_name: "Brightfield",
    motto: "Knowledge, Character, Service",
    logo_url: null,
  },
  student: {
    student_id: U(1),
    admission_no: "BFA/2026/014",
    full_name: "Aisha Bello",
    gender: "female",
    photo_url: null,
    date_of_birth: "2013-04-18",
  },
  enrollment_id: U(2),
  term: { id: U(3), name: "First Term" },
  session: { id: U(4), name: "2026/2027" },
  class_arm: { id: U(5), full_name: "JSS 1 A" },
  academic_year: "2026/2027",
  report_date: "2026-12-11",
  subjects: [
    {
      subject_id: U(10),
      subject_name: "Mathematics",
      total: 87,
      grade_letter: "A",
      grade_point: 4,
      remark: "Excellent",
      position: 1,
      is_core: true,
      components: [
        { id: "ca1", name: "CA1", max_score: 20, weight: 20, score: 18 },
        { id: "ca2", name: "CA2", max_score: 20, weight: 20, score: 17 },
        { id: "exam", name: "Exam", max_score: 60, weight: 60, score: 52 },
      ],
    },
    {
      subject_id: U(11),
      subject_name: "English Language",
      total: 74,
      grade_letter: "B",
      grade_point: 3,
      remark: "Very Good",
      position: 4,
      is_core: true,
      components: [
        { id: "ca1", name: "CA1", max_score: 20, weight: 20, score: 15 },
        { id: "ca2", name: "CA2", max_score: 20, weight: 20, score: 14 },
        { id: "exam", name: "Exam", max_score: 60, weight: 60, score: 45 },
      ],
    },
    {
      subject_id: U(12),
      subject_name: "Basic Science",
      total: 68,
      grade_letter: "B",
      grade_point: 3,
      remark: "Very Good",
      position: 7,
      is_core: false,
      components: [
        { id: "ca1", name: "CA1", max_score: 20, weight: 20, score: 14 },
        { id: "ca2", name: "CA2", max_score: 20, weight: 20, score: 12 },
        { id: "exam", name: "Exam", max_score: 60, weight: 60, score: 42 },
      ],
    },
  ],
  psychomotor: [
    { learning_area: "Handwriting", achievement_level: "Very Good" },
    { learning_area: "Physical Education", achievement_level: "Excellent" },
    { learning_area: "ICT Skills", achievement_level: "Good" },
  ],
  psychomotor_average: "Very Good",
  conduct: "Respectful and attentive",
  attendance_pct: 96,
  homeroom_teacher: "Mr. J. Adeyemi",
  next_term_date: "2027-01-12",
  next_term_label: "Second Term",
  grading_key: [
    { letter: "A", min_score: 75, max_score: 100, remark: "Excellent" },
    { letter: "B", min_score: 65, max_score: 74, remark: "Very Good" },
    { letter: "C", min_score: 50, max_score: 64, remark: "Good" },
    { letter: "D", min_score: 40, max_score: 49, remark: "Fair" },
    { letter: "F", min_score: 0, max_score: 39, remark: "Needs Improvement" },
  ],
  comments: {
    principal: "A diligent term's work. Keep up the standard.",
    vice_principal: "Strong in Mathematics; spend more time on Basic Science.",
    homeroom: "A polite and hardworking member of the class.",
  },
  summary: {
    subjects_published: 3,
    total: 229,
    average: 76.3,
    grade_letter: "A",
    remark: "Excellent",
    class_rank: 2,
    class_size: 28,
  },
  best_in_subjects: [
    {
      subject_id: U(10),
      subject_name: "Mathematics",
      top_score: 87,
      is_best: true,
      tied: false,
      co_leaders: [],
    },
  ],
  can_comment: false,
  can_manage_psychomotor: false,
};

/* ------------------------------------------------------------------ */

function PaletteItem({
  type,
  disabled,
  onAdd,
  onDragPointerDown,
}: {
  type: ReportWidgetType;
  disabled: boolean;
  /** Clicking the block adds it; dragging it in places it where it lands. */
  onAdd: () => void;
  /** Lets the parent tell a fresh click apart from the click a drop emits. */
  onDragPointerDown: () => void;
}) {
  const def = widgetDef(type);
  // No inline transform: the DragOverlay draws the thing being dragged, so the
  // palette entry itself stays put and the drop preview stays crisp.
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: `palette:${type}`,
    data: { kind: "palette", widgetType: type },
    disabled,
  });
  const Icon = def.icon;
  const dragListeners = listeners ?? {};
  return (
    <button
      ref={setNodeRef}
      type="button"
      {...attributes}
      {...dragListeners}
      // Each interaction starts with a pointerdown, so this is where a fresh
      // click is distinguished from the click a completed drop would emit.
      onPointerDown={(event) => {
        onDragPointerDown();
        dragListeners.onPointerDown?.(event);
      }}
      onClick={() => onAdd()}
      disabled={disabled}
      title={disabled ? `${def.label} is already on this card` : def.description}
      className={cn(
        "flex w-full items-start gap-2.5 rounded-lg border border-transparent px-2.5 py-2 text-left transition-all duration-150",
        disabled
          ? "cursor-not-allowed opacity-40"
          : "cursor-grab hover:border-border/70 hover:bg-accent active:cursor-grabbing",
        isDragging && "opacity-40",
      )}
    >
      <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground/70" />
      <span className="min-w-0">
        <span className="block truncate text-[12.5px] font-medium">{def.label}</span>
        <span className="block text-[11px] leading-snug text-muted-foreground/60">
          {def.description}
        </span>
      </span>
    </button>
  );
}

function CanvasItem({
  widget,
  index,
  total,
  selected,
  onSelect,
  onMove,
  onToggleHidden,
  onRemove,
  onDuplicate,
}: {
  widget: ReportWidget;
  index: number;
  total: number;
  selected: boolean;
  onSelect: () => void;
  onMove: (to: number) => void;
  onToggleHidden: () => void;
  onRemove: () => void;
  onDuplicate: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: widget.id,
    data: { kind: "canvas" },
  });
  const def = widgetDef(widget.type);
  const Icon = def.icon;
  const half = prop<string>(widget, "width", "full") === "half";

  return (
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={cn(
        "group flex items-center gap-2 rounded-lg border bg-card px-2.5 py-2 transition-colors",
        selected ? "border-primary/50 bg-primary/[0.04]" : "border-border/70",
        isDragging && "z-10 shadow-pop",
        widget.hidden && "opacity-50",
      )}
      onClick={onSelect}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect();
        }
      }}
    >
      {/* The drag handle is the only drag surface, so the row's buttons stay
          clickable and the whole thing is still keyboard-reachable. */}
      <button
        type="button"
        {...listeners}
        {...attributes}
        aria-label={`Reorder ${def.label}`}
        className="cursor-grab touch-none rounded p-0.5 text-muted-foreground/40 hover:text-foreground active:cursor-grabbing"
      >
        <GripVertical className="h-3.5 w-3.5" />
      </button>

      <Icon className="h-3.5 w-3.5 shrink-0 text-muted-foreground/70" />

      <span className="min-w-0 flex-1">
        <span className="block truncate text-[12.5px] font-medium">
          {typeof widget.props?.title === "string" && widget.props.title
            ? (widget.props.title as string)
            : def.label}
        </span>
        <span className="block text-[10.5px] text-muted-foreground/50">
          {def.label}
          {half && " · half width"}
          {widget.hidden && " · hidden"}
        </span>
      </span>

      <div className="flex shrink-0 items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
        <button
          type="button"
          aria-label="Move up"
          disabled={index === 0}
          onClick={(e) => {
            e.stopPropagation();
            onMove(index - 1);
          }}
          className="rounded p-1 text-muted-foreground/60 hover:bg-accent hover:text-foreground disabled:opacity-30"
        >
          <ChevronUp className="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          aria-label="Move down"
          disabled={index === total - 1}
          onClick={(e) => {
            e.stopPropagation();
            onMove(index + 1);
          }}
          className="rounded p-1 text-muted-foreground/60 hover:bg-accent hover:text-foreground disabled:opacity-30"
        >
          <ChevronDown className="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          aria-label={widget.hidden ? "Show on the card" : "Hide from the card"}
          onClick={(e) => {
            e.stopPropagation();
            onToggleHidden();
          }}
          className="rounded p-1 text-muted-foreground/60 hover:bg-accent hover:text-foreground"
        >
          {widget.hidden ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
        </button>
        <button
          type="button"
          aria-label="Duplicate"
          onClick={(e) => {
            e.stopPropagation();
            onDuplicate();
          }}
          className="rounded p-1 text-muted-foreground/60 hover:bg-accent hover:text-foreground"
        >
          <Copy className="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          aria-label="Remove"
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }}
          className="rounded p-1 text-muted-foreground/60 hover:bg-destructive/10 hover:text-destructive"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}

function Inspector({
  widget,
  onProp,
}: {
  widget: ReportWidget | null;
  /** Writes one setting on the selected block. The parent owns the layout, so
   * the inspector never keeps a copy that could drift from what gets saved. */
  onProp: (key: string, value: unknown) => void;
}) {
  if (!widget) {
    return (
      <div className="px-3 py-6 text-center text-[12px] text-muted-foreground/60">
        Pick a block on the card to change its settings.
      </div>
    );
  }
  const def = widgetDef(widget.type);
  const fields = def.fields ?? [];
  const width = prop<string>(widget, "width", "full");

  return (
    <div className="space-y-3.5 p-3">
      <div>
        <p className="text-[12.5px] font-semibold">{def.label}</p>
        <p className="mt-0.5 text-[11px] leading-snug text-muted-foreground/60">
          {def.description}
        </p>
      </div>

      {fields.length === 0 && (
        <p className="text-[11px] text-muted-foreground/60">
          This block has no settings — it always draws the same way.
        </p>
      )}

      {fields.map((field) => {
        const value = widget.props?.[field.key];
        if (field.kind === "boolean") {
          const checked = prop(widget, field.key, false);
          return (
            <label
              key={field.key}
              className="flex cursor-pointer items-center justify-between gap-3"
            >
              <span className="text-[12px] font-medium">{field.label}</span>
              <input
                type="checkbox"
                checked={checked}
                onChange={(e) => onProp(field.key, e.target.checked)}
                className="h-3.5 w-3.5 accent-[hsl(var(--primary))]"
              />
            </label>
          );
        }
        if (field.kind === "textarea") {
          return (
            <div key={field.key} className="space-y-1">
              <Label htmlFor={`f-${field.key}`}>{field.label}</Label>
              <textarea
                id={`f-${field.key}`}
                rows={4}
                value={typeof value === "string" ? value : ""}
                placeholder={field.placeholder}
                onChange={(e) => onProp(field.key, e.target.value)}
                className="w-full resize-y rounded-xl border border-border/80 bg-background/50 px-3 py-2 text-[13px] shadow-sm focus-visible:border-primary/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/10"
              />
              {field.help && (
                <p className="text-[10.5px] text-muted-foreground/60">{field.help}</p>
              )}
            </div>
          );
        }
        if (field.kind === "number") {
          return (
            <div key={field.key} className="space-y-1">
              <Label htmlFor={`f-${field.key}`}>{field.label}</Label>
              <Input
                id={`f-${field.key}`}
                type="number"
                min={field.min}
                max={field.max}
                value={typeof value === "number" ? value : (def.defaults?.[field.key] as number) ?? 0}
                onChange={(e) => onProp(field.key, Number(e.target.value))}
              />
            </div>
          );
        }
        if (field.kind === "select") {
          return (
            <div key={field.key} className="space-y-1">
              <Label htmlFor={`f-${field.key}`}>{field.label}</Label>
              <select
                id={`f-${field.key}`}
                value={typeof value === "string" ? value : ""}
                onChange={(e) => onProp(field.key, e.target.value)}
                className="h-9 w-full rounded-xl border border-border/80 bg-background/50 px-3 text-[13px]"
              >
                {(field.options ?? []).map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>
          );
        }
        return (
          <div key={field.key} className="space-y-1">
            <Label htmlFor={`f-${field.key}`}>{field.label}</Label>
            <Input
              id={`f-${field.key}`}
              value={typeof value === "string" ? value : ""}
              placeholder={field.placeholder}
              onChange={(e) => onProp(field.key, e.target.value)}
            />
            {field.help && <p className="text-[10.5px] text-muted-foreground/60">{field.help}</p>}
          </div>
        );
      })}

      <div className="space-y-1 border-t border-border/60 pt-3.5">
        <Label htmlFor="f-width">Width</Label>
        <select
          id="f-width"
          value={width}
          onChange={(e) => onProp("width", e.target.value)}
          className="h-9 w-full rounded-xl border border-border/80 bg-background/50 px-3 text-[13px]"
        >
          <option value="full">Full width</option>
          <option value="half">
            Half width — pairs with the next half-width block beside it
          </option>
        </select>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */

export interface ReportCardDesignerProps {
  layout: ReportLayout;
  onChange: (layout: ReportLayout) => void;
  onDuplicateWidgetHint?: (message: string) => void;
}

/**
 * The drag-and-drop builder.
 *
 * Drag to reorder the blocks on the card; drag a block out of the palette (or
 * click it) to add it; select a block to change its settings; switch to Preview
 * to see the real A4 card.
 *
 * The component is fully controlled (`layout` in, `onChange` out) so the page
 * owns undo, save, and the "unsaved changes" state — the builder never holds a
 * private copy that could drift from what gets saved.
 */
export function ReportCardDesigner({
  layout,
  onChange,
  onDuplicateWidgetHint,
}: ReportCardDesignerProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draggingType, setDraggingType] = useState<ReportWidgetType | null>(null);
  const [view, setView] = useState<"design" | "preview">("design");
  // A finished drag also fires a click on the palette block it started from;
  // the flag lets that one click be swallowed rather than adding the block
  // twice (once where it was dropped, once at the end).
  const droppedRef = useRef(false);

  // The card itself is a drop target, so a palette block dropped on empty space
  // lands at the end rather than being rejected.
  const { setNodeRef: setCanvasRef } = useDroppable({
    id: "canvas",
    data: { kind: "canvas" },
  });

  const sensors = useSensors(
    // A small distance threshold so a click still selects a block instead of
    // being swallowed as a micro-drag.
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const selected = useMemo(
    () => layout.widgets.find((w) => w.id === selectedId) ?? null,
    [layout.widgets, selectedId],
  );

  const grouped = useMemo(() => {
    const groups = new Map<string, typeof WIDGET_CATALOG>();
    for (const def of WIDGET_CATALOG) {
      const list = groups.get(def.group) ?? [];
      list.push(def);
      groups.set(def.group, list);
    }
    return Array.from(groups.entries());
  }, []);

  function addWidget(type: ReportWidgetType, at?: number) {
    if (!canAdd(layout, type)) {
      onDuplicateWidgetHint?.(
        `A card can only have one ${widgetDef(type).label.toLowerCase()}.`,
      );
      return;
    }
    const widget = newWidget(type);
    const widgets = [...layout.widgets];
    widgets.splice(at ?? widgets.length, 0, widget);
    onChange({ ...layout, widgets });
    setSelectedId(widget.id);
  }

  function addFromPalette(type: ReportWidgetType) {
    if (droppedRef.current) {
      droppedRef.current = false;
      return;
    }
    addWidget(type);
  }

  function duplicateWidget(widget: ReportWidget) {
    if (widgetDef(widget.type).unique) {
      onDuplicateWidgetHint?.(
        `A card can only have one ${widgetDef(widget.type).label.toLowerCase()}.`,
      );
      return;
    }
    const index = layout.widgets.findIndex((w) => w.id === widget.id);
    const copy: ReportWidget = {
      ...newWidget(widget.type),
      props: { ...(widget.props ?? {}) },
    };
    const widgets = [...layout.widgets];
    widgets.splice(index + 1, 0, copy);
    onChange({ ...layout, widgets });
    setSelectedId(copy.id);
  }

  function handleDragStart(event: DragStartEvent) {
    const data = event.active.data.current;
    if (data?.kind === "palette") {
      droppedRef.current = true;
      setDraggingType(data.widgetType as ReportWidgetType);
    }
  }

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    setDraggingType(null);
    if (!over) return;

    const data = active.data.current;
    if (data?.kind === "palette") {
      const index = layout.widgets.findIndex((w) => w.id === over.id);
      addWidget(data.widgetType as ReportWidgetType, index === -1 ? undefined : index);
      return;
    }
    if (active.id === over.id) return;
    const from = layout.widgets.findIndex((w) => w.id === active.id);
    const to = layout.widgets.findIndex((w) => w.id === over.id);
    if (from === -1 || to === -1) return;
    onChange({ ...layout, widgets: arrayMove(layout.widgets, from, to) });
  }

  const draggingDef = draggingType ? widgetDef(draggingType) : null;

  return (
    <div className="space-y-3">
      {/* View switch: designing and proof-reading want different canvases. */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-1 rounded-lg border border-border/70 p-0.5">
          <button
            type="button"
            onClick={() => setView("design")}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-[12px] font-medium transition-colors",
              view === "design" ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-accent",
            )}
          >
            <LayoutTemplate className="h-3.5 w-3.5" /> Design
          </button>
          <button
            type="button"
            onClick={() => setView("preview")}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-[12px] font-medium transition-colors",
              view === "preview" ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-accent",
            )}
          >
            <Pencil className="h-3.5 w-3.5" /> Preview
          </button>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-muted-foreground/60">Theme</span>
          <div className="flex items-center gap-1">
            {REPORT_TEMPLATES.map((t) => (
              <button
                key={t.id}
                type="button"
                title={`${t.name} — ${t.description}`}
                aria-label={`Use the ${t.name} theme`}
                onClick={() => onChange({ ...layout, theme: t.id as ReportTheme })}
                className={cn(
                  "h-6 w-6 rounded-full border-2 transition-transform",
                  layout.theme === t.id
                    ? "border-foreground/60 scale-110"
                    : "border-transparent hover:scale-110",
                )}
                style={{ background: t.accent }}
              />
            ))}
          </div>
        </div>
      </div>

      {view === "preview" ? (
        <div className="report-card-stage">
          <ReportCardDocument card={SAMPLE_CARD} layout={layout} />
          <p className="mt-2 text-center text-[11px] text-muted-foreground/60">
            Sample data — a real card shows the selected student&apos;s published results.
          </p>
        </div>
      ) : (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
          onDragCancel={() => setDraggingType(null)}
          modifiers={[restrictToVerticalAxis, restrictToWindowEdges]}
        >
          <div className="grid gap-3 lg:grid-cols-[15rem_minmax(0,1fr)_16rem]">
            {/* Palette */}
            <div className="flex max-h-[36rem] flex-col rounded-xl border border-border/70 bg-card">
              <div className="border-b border-border/60 px-3 py-2.5">
                <p className="text-[12.5px] font-semibold">Blocks</p>
                <p className="text-[10.5px] text-muted-foreground/60">
                  Drag onto the card, or click to add
                </p>
              </div>
              <div className="scrollbar-thin flex-1 space-y-2 overflow-y-auto p-2">
                {grouped.map(([group, defs]) => (
                  <div key={group} className="space-y-0.5">
                    <p className="px-2.5 pt-1.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground/50">
                      {group}
                    </p>
                    {defs.map((def) => (
                      <PaletteItem
                        key={def.type}
                        type={def.type}
                        disabled={!canAdd(layout, def.type)}
                        onAdd={() => addFromPalette(def.type)}
                        onDragPointerDown={() => {
                          droppedRef.current = false;
                        }}
                      />
                    ))}
                  </div>
                ))}
              </div>
            </div>

            {/* Canvas */}
            <div
              ref={setCanvasRef}
              className="rounded-xl border border-border/70 bg-muted/20 p-2.5"
            >
              <SortableContext
                items={layout.widgets.map((w) => w.id)}
                strategy={verticalListSortingStrategy}
              >
                <div className="space-y-1.5">
                  {layout.widgets.map((widget, index) => (
                    <CanvasItem
                      key={widget.id}
                      widget={widget}
                      index={index}
                      total={layout.widgets.length}
                      selected={widget.id === selectedId}
                      onSelect={() => setSelectedId(widget.id)}
                      onMove={(to) => onChange(moveWidget(layout, index, to))}
                      onToggleHidden={() =>
                        onChange(updateWidget(layout, widget.id, { hidden: !widget.hidden }))
                      }
                      onRemove={() => {
                        onChange(removeWidget(layout, widget.id));
                        if (selectedId === widget.id) setSelectedId(null);
                      }}
                      onDuplicate={() => duplicateWidget(widget)}
                    />
                  ))}
                </div>
              </SortableContext>

              {layout.widgets.length === 0 && (
                <p className="py-10 text-center text-[12px] text-muted-foreground/60">
                  The card is empty. Drag a block in from the left.
                </p>
              )}
            </div>

            {/* Inspector */}
            <div className="max-h-[36rem] overflow-y-auto rounded-xl border border-border/70 bg-card">
              <div className="border-b border-border/60 px-3 py-2.5">
                <p className="text-[12.5px] font-semibold">Settings</p>
              </div>
              <Inspector
                widget={selected}
                onProp={(key, value) => {
                  if (!selected) return;
                  onChange(setWidgetProp(layout, selected.id, key, value));
                }}
              />
            </div>
          </div>

          <DragOverlay dropAnimation={null}>
            {draggingDef && (
              <div className="flex items-center gap-2 rounded-lg border border-primary/40 bg-card px-3 py-2 shadow-pop">
                <draggingDef.icon className="h-3.5 w-3.5 text-primary" />
                <span className="text-[12.5px] font-medium">{draggingDef.label}</span>
                <Badge variant="default">
                  <Plus className="h-2.5 w-2.5" /> add
                </Badge>
              </div>
            )}
          </DragOverlay>
        </DndContext>
      )}
    </div>
  );
}

