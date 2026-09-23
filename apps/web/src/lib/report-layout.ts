/**
 * The report card widget catalog.
 *
 * A school's card is a *document they own*: an ordered list of widgets plus a
 * theme, stored server-side per school (see the API's
 * `app/schemas/report_card.py`, which validates the same closed type list).
 * This module is the client half of that contract and the single place that
 * knows what each widget is called, what it can be configured with, and what a
 * new instance of it starts as.
 *
 * Three rules keep the designer honest:
 *
 * 1. **The catalog is closed.** `REPORT_WIDGET_TYPES` in `@clearis/shared` is
 *    the list the API accepts; every entry here must be one of them, so a
 *    design built in the designer can always be saved.
 * 2. **Nothing is stored that a widget does not use.** `defaultPropsFor` is the
 *    only source of a new widget's settings, so a design never accumulates
 *    options from an older shape of the same widget.
 * 3. **A missing setting is not an error.** Renderers read props through
 *    `prop()` with a default, so a design saved before a setting existed still
 *    draws — it just gets the documented default.
 */
import {
  Activity,
  Award,
  BarChart3,
  CalendarCheck,
  CalendarClock,
  FileText,
  Heart,
  ListChecks,
  MessageSquareText,
  Minus,
  PenLine,
  Table2,
  Type,
  User,
  type LucideIcon,
} from "lucide-react";

import {
  REPORT_THEMES,
  type ReportLayout,
  type ReportTheme,
  type ReportWidget,
  type ReportWidgetType,
} from "@clearis/shared";

// --- Settings a widget exposes in the inspector --------------------------------

export interface WidgetField {
  key: string;
  label: string;
  kind: "text" | "textarea" | "boolean" | "number" | "select";
  options?: { value: string; label: string }[];
  placeholder?: string;
  help?: string;
  min?: number;
  max?: number;
}

export interface WidgetDefinition {
  type: ReportWidgetType;
  label: string;
  group: "Card furniture" | "Student & academics" | "Summary" | "Comments & sign-off" | "Custom";
  description: string;
  icon: LucideIcon;
  /** Drawn as a full-width block rather than a compact chip in the palette. */
  /** Identity/academic blocks that must not appear twice on one card. */
  unique?: boolean;
  /** What a brand-new instance of this widget starts as. */
  defaults?: Record<string, unknown>;
  fields?: WidgetField[];
}

const TEXT = (key: string, label: string, placeholder?: string, help?: string): WidgetField => ({
  key,
  label,
  kind: "text",
  placeholder,
  help,
});
const BOOL = (key: string, label: string, help?: string): WidgetField => ({
  key,
  label,
  kind: "boolean",
  help,
});
const NUM = (key: string, label: string, min?: number, max?: number): WidgetField => ({
  key,
  label,
  kind: "number",
  min,
  max,
});

/**
 * Every widget the designer offers.
 *
 * Order here is the palette's order, grouped by `group` — it is not the order
 * they appear on a card (that is each school's own, dragged into place).
 */
export const WIDGET_CATALOG: WidgetDefinition[] = [
  {
    type: "header",
    label: "Card header",
    group: "Card furniture",
    description: "School name, crest, motto, student photo and the card title.",
    icon: FileText,
    unique: true,
    defaults: { title: "Report Card", show_photo: true, show_logo: true, show_motto: true },
    fields: [
      TEXT("title", "Title", "Report Card"),
      BOOL("show_photo", "Student photo"),
      BOOL("show_logo", "School crest"),
      BOOL("show_motto", "School motto"),
    ],
  },
  {
    type: "student_info",
    label: "Student details",
    group: "Student & academics",
    description: "Name, admission number, class, term and report date.",
    icon: User,
    unique: true,
    defaults: { show_dob: true, show_session: true },
    fields: [BOOL("show_dob", "Date of birth"), BOOL("show_session", "Academic year")],
  },
  {
    type: "cognitive_domain",
    label: "Subject results table",
    group: "Student & academics",
    description: "Every subject with its assessment components, total, grade and remark.",
    icon: Table2,
    unique: true,
    defaults: {
      title: "Cognitive Domain",
      subtitle: "Knowledge, Understanding & Thinking Skills",
      show_components: true,
      show_remarks: true,
      show_core_marker: true,
      show_average: true,
    },
    fields: [
      TEXT("title", "Heading", "Cognitive Domain"),
      TEXT("subtitle", "Sub-heading"),
      BOOL("show_components", "Break the score into components"),
      BOOL("show_remarks", "Remark column"),
      BOOL("show_core_marker", "Mark core subjects with *"),
      BOOL("show_average", "Domain average line"),
    ],
  },
  {
    type: "psychomotor_domain",
    label: "Psychomotor & affective",
    group: "Student & academics",
    description: "Skills and behaviour areas with their achievement levels.",
    icon: Activity,
    unique: true,
    defaults: {
      title: "Psychomotor Domain",
      subtitle: "Skills, Practical Abilities & Physical Development",
      show_average: true,
    },
    fields: [
      TEXT("title", "Heading", "Psychomotor Domain"),
      TEXT("subtitle", "Sub-heading"),
      BOOL("show_average", "Domain average line"),
    ],
  },
  {
    type: "performance_summary",
    label: "Performance summary",
    group: "Summary",
    description: "Overall average, grade, position in class, attendance and conduct.",
    icon: BarChart3,
    unique: true,
    defaults: { show_attendance: true, show_conduct: true, show_position: true },
    fields: [
      BOOL("show_position", "Position in class"),
      BOOL("show_attendance", "Attendance"),
      BOOL("show_conduct", "Conduct"),
    ],
  },
  {
    type: "grading_key",
    label: "Grading key",
    group: "Summary",
    description: "The school's grade bands and what each one means.",
    icon: ListChecks,
    defaults: { title: "Grading Key" },
    fields: [TEXT("title", "Heading", "Grading Key")],
  },
  {
    type: "best_in_subjects",
    label: "Subject awards",
    group: "Summary",
    description: "Subjects where this student took the top score.",
    icon: Award,
    defaults: { title: "Best in Subject", limit: 6 },
    fields: [
      TEXT("title", "Heading", "Best in Subject"),
      NUM("limit", "Maximum subjects shown", 1, 12),
    ],
  },
  {
    type: "attendance",
    label: "Attendance",
    group: "Summary",
    description: "This term's attendance rate as its own block.",
    icon: CalendarCheck,
    defaults: { title: "Attendance", note: "This term" },
    fields: [TEXT("title", "Heading", "Attendance"), TEXT("note", "Caption", "This term")],
  },
  {
    type: "conduct",
    label: "Conduct",
    group: "Summary",
    description: "The student's conduct or behaviour remark as its own block.",
    icon: Heart,
    defaults: { title: "Conduct", note: "Overall" },
    fields: [TEXT("title", "Heading", "Conduct"), TEXT("note", "Caption", "Overall")],
  },
  {
    type: "next_term",
    label: "Next term begins",
    group: "Summary",
    description: "The resumption date at the foot of the card.",
    icon: CalendarClock,
    defaults: { label: "Next Term Begins", fallback: "To be announced" },
    fields: [
      TEXT("label", "Label", "Next Term Begins"),
      TEXT("fallback", "Shown when no date is set", "To be announced"),
    ],
  },
  {
    type: "comments",
    label: "Comments",
    group: "Comments & sign-off",
    description: "Principal, vice principal and homeroom teacher remarks.",
    icon: MessageSquareText,
    unique: true,
    defaults: {
      title: "Comments",
      principal_label: "Principal's Comment",
      vice_principal_label: "Vice Principal's Comment",
      homeroom_label: "Homeroom Teacher's Comment",
      show_signature_lines: true,
      show_vice_principal: true,
    },
    fields: [
      TEXT("title", "Heading", "Comments"),
      TEXT("principal_label", "Principal slot", "Principal's Comment"),
      TEXT("vice_principal_label", "Vice principal slot", "Vice Principal's Comment"),
      TEXT("homeroom_label", "Homeroom teacher slot", "Homeroom Teacher's Comment"),
      BOOL("show_vice_principal", "Include the vice principal slot"),
      BOOL("show_signature_lines", "Signature lines"),
    ],
  },
  {
    type: "signatures",
    label: "Signature block",
    group: "Comments & sign-off",
    description: "A sign-off area for named officers. Use for a second page or a stamp.",
    icon: PenLine,
    defaults: {
      title: "Signatures",
      principal_label: "Principal",
      vice_principal_label: "Vice Principal",
      homeroom_label: "Homeroom Teacher",
      show_dates: true,
    },
    fields: [
      TEXT("title", "Heading", "Signatures"),
      TEXT("principal_label", "First signatory", "Principal"),
      TEXT("vice_principal_label", "Second signatory", "Vice Principal"),
      TEXT("homeroom_label", "Third signatory", "Homeroom Teacher"),
      BOOL("show_dates", "Date under each signature"),
    ],
  },
  {
    type: "custom_text",
    label: "Custom text note",
    group: "Custom",
    description: "Your own heading and paragraph — school rules, a promotion note, anything.",
    icon: Type,
    defaults: { title: "Notice", body: "" },
    fields: [
      TEXT("title", "Heading", "Notice"),
      {
        key: "body",
        label: "Text",
        kind: "textarea",
        placeholder: "Type the note that should appear on every card…",
        help: "Appears on every card this design is used for.",
      },
    ],
  },
  {
    type: "spacer",
    label: "Spacer",
    group: "Card furniture",
    description: "Blank vertical space, to push blocks apart.",
    icon: Minus,
    defaults: { height: 12 },
    fields: [NUM("height", "Height in pixels", 4, 120)],
  },
];

const BY_TYPE = new Map(WIDGET_CATALOG.map((w) => [w.type, w]));

export function widgetDef(type: ReportWidgetType): WidgetDefinition {
  const def = BY_TYPE.get(type);
  if (def) return def;
  // Defensive: the catalog and the API contract are two halves of one list, but
  // if they ever drift, an unknown type renders as a labelled placeholder rather
  // than crashing a school's card.
  return {
    type,
    label: type,
    group: "Custom",
    description: "Unknown widget",
    icon: Type,
  };
}

/** The label the designer lists an instance under (its own heading if it has one). */
export function widgetTitle(widget: ReportWidget): string {
  const heading = widget.props?.title;
  if (typeof heading === "string" && heading.trim()) return heading.trim();
  return widgetDef(widget.type).label;
}

/** A fresh instance of a widget, with the catalog's defaults and a stable id. */
export function newWidget(type: ReportWidgetType): ReportWidget {
  const def = widgetDef(type);
  return {
    id: `${type}-${Math.random().toString(36).slice(2, 9)}`,
    type,
    props: { ...(def.defaults ?? {}) },
    hidden: false,
  };
}

/**
 * Read a widget setting, falling back to the catalog default.
 *
 * Renderers use this rather than reading `props` directly, so a design saved
 * before a setting existed draws with the documented default instead of
 * `undefined` leaking into the card.
 *
 * When the fallback is a string literal whose value you branch on, instantiate
 * the type (`prop<string>(w, "width", "full")`) — otherwise TypeScript narrows
 * `T` to the literal itself and rejects comparisons against its other values.
 */
export function prop<T extends string | number | boolean>(
  widget: ReportWidget,
  key: string,
  fallback: T,
): T {
  const raw = widget.props?.[key];
  if (typeof raw === typeof fallback) return raw as T;
  // Numbers arrive from JSONB and from <input> as strings; coerce rather than
  // silently discarding a value the school typed.
  if (typeof fallback === "number" && raw != null && `${raw}`.trim() !== "") {
    const parsed = Number(raw);
    if (Number.isFinite(parsed)) return parsed as T;
  }
  if (typeof fallback === "boolean") {
    if (raw === "true") return true as T;
    if (raw === "false") return false as T;
  }
  return fallback;
}

/** String setting, trimmed, with the default when blank. */
export function propText(widget: ReportWidget, key: string, fallback = ""): string {
  const raw = prop(widget, key, fallback);
  const text = typeof raw === "string" ? raw.trim() : `${raw}`;
  return text || fallback;
}

// --- The card a school gets before it designs one -------------------------------

/**
 * The built-in card, widget for widget — the same document the API falls back to
 * (`BUILTIN_DEFAULT_LAYOUT`). A school that opens the designer and saves nothing
 * keeps printing exactly this.
 */
export const DEFAULT_LAYOUT: ReportLayout = {
  version: 1,
  theme: "classic",
  widgets: [
    { id: "header", type: "header", props: { title: "Report Card", show_photo: true, show_logo: true, show_motto: true }, hidden: false },
    { id: "student_info", type: "student_info", props: { show_dob: true, show_session: true }, hidden: false },
    // Half-width pair: these two sit side by side, exactly as the card did
    // before the designer existed (the API's built-in layout says the same).
    { id: "cognitive_domain", type: "cognitive_domain", props: { width: "half" }, hidden: false },
    { id: "psychomotor_domain", type: "psychomotor_domain", props: { width: "half" }, hidden: false },
    { id: "grading_key", type: "grading_key", props: { title: "Grading Key" }, hidden: false },
    { id: "performance_summary", type: "performance_summary", props: {}, hidden: false },
    { id: "best_in_subjects", type: "best_in_subjects", props: { title: "Best in Subject" }, hidden: false },
    { id: "next_term", type: "next_term", props: { label: "Next Term Begins" }, hidden: false },
    { id: "comments", type: "comments", props: {}, hidden: false },
  ],
};

export function emptyLayout(theme: ReportTheme = "classic"): ReportLayout {
  return { ...cloneLayout(DEFAULT_LAYOUT), theme };
}

/** Deep copy of a layout — the designer edits by value so Cancel is a true undo. */
export function cloneLayout(layout: ReportLayout): ReportLayout {
  return {
    version: layout.version ?? 1,
    theme: layout.theme ?? "classic",
    widgets: (layout.widgets ?? []).map((w) => ({
      id: w.id,
      type: w.type,
      props: { ...(w.props ?? {}) },
      hidden: !!w.hidden,
    })),
  };
}

export function isKnownTheme(value: unknown): value is ReportTheme {
  return typeof value === "string" && (REPORT_THEMES as readonly string[]).includes(value);
}

/**
 * The CSS class that applies a theme to a card sheet.
 *
 * Themes are carried by the existing `report-card-templates.css`, so the four
 * styles a school could pick before the designer existed still look identical.
 */
export function themeClass(theme: ReportTheme): string {
  return `rc-template-${theme}`;
}

// --- Editing helpers ------------------------------------------------------------

/** Move a widget within the layout (drag-and-drop and the up/down buttons). */
export function moveWidget(layout: ReportLayout, from: number, to: number): ReportLayout {
  const widgets = [...layout.widgets];
  if (from < 0 || from >= widgets.length) return layout;
  const clamped = Math.max(0, Math.min(widgets.length - 1, to));
  if (from === clamped) return layout;
  const [moved] = widgets.splice(from, 1);
  widgets.splice(clamped, 0, moved);
  return { ...layout, widgets };
}

export function removeWidget(layout: ReportLayout, id: string): ReportLayout {
  return { ...layout, widgets: layout.widgets.filter((w) => w.id !== id) };
}

export function updateWidget(
  layout: ReportLayout,
  id: string,
  patch: Partial<Omit<ReportWidget, "id">>,
): ReportLayout {
  return {
    ...layout,
    widgets: layout.widgets.map((w) => (w.id === id ? { ...w, ...patch } : w)),
  };
}

export function setWidgetProp(
  layout: ReportLayout,
  id: string,
  key: string,
  value: unknown,
): ReportLayout {
  return {
    ...layout,
    widgets: layout.widgets.map((w) =>
      w.id === id ? { ...w, props: { ...(w.props ?? {}), [key]: value } } : w,
    ),
  };
}

/** Widgets still available to add: the palette greys out `unique` duplicates. */
export function canAdd(layout: ReportLayout, type: ReportWidgetType): boolean {
  if (!widgetDef(type).unique) return true;
  return !layout.widgets.some((w) => w.type === type);
}
