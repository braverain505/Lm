/**
 * Report card visual themes.
 *
 * A theme is a *property of a school's saved design* (``layout.theme``), not a
 * browser preference — this file only describes what each one looks like so the
 * designer can draw its swatches and previews. The styles themselves live in
 * ``report-card-templates.css`` under ``.rc-template-<id>``.
 *
 * The four here are the ones the app shipped with, so a school that liked its
 * old card keeps it: the designer's "Classic" theme renders exactly what the
 * hardcoded card did.
 */
import type { ReportTheme } from "@clearis/shared";

export type TemplateId = ReportTheme;

export interface ReportTemplate {
  id: TemplateId;
  name: string;
  description: string;
  accent: string;       // Primary accent color for the swatch
  accentLight: string;  // Lighter variant for backgrounds
  preview: {
    headerBg: string;
    headerText: string;
    bodyBg: string;
    borderColor: string;
    fontFamily: string;
  };
}

export const REPORT_TEMPLATES: ReportTemplate[] = [
  {
    id: "classic",
    name: "Classic",
    description: "Traditional navy & gold with serif fonts — timeless and formal.",
    accent: "#1b2c4a",
    accentLight: "#e8ecf3",
    preview: {
      headerBg: "#1b2c4a",
      headerText: "#ffffff",
      bodyBg: "#fcfaf4",
      borderColor: "#d9d2c2",
      fontFamily: 'Georgia, "Times New Roman", serif',
    },
  },
  {
    id: "modern",
    name: "Modern",
    description: "Clean white layout with vibrant blue accents and sans-serif typography.",
    accent: "#2563eb",
    accentLight: "#eff6ff",
    preview: {
      headerBg: "#2563eb",
      headerText: "#ffffff",
      bodyBg: "#ffffff",
      borderColor: "#e2e8f0",
      fontFamily: 'ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif',
    },
  },
  {
    id: "elegant",
    name: "Elegant",
    description: "Deep purple tones with gold accents — sophisticated and premium.",
    accent: "#5b21b6",
    accentLight: "#f5f3ff",
    preview: {
      headerBg: "#5b21b6",
      headerText: "#ffffff",
      bodyBg: "#fefcff",
      borderColor: "#ddd6fe",
      fontFamily: 'ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif',
    },
  },
  {
    id: "minimal",
    name: "Minimal",
    description: "Black & white with generous whitespace — clean and distraction-free.",
    accent: "#18181b",
    accentLight: "#f4f4f5",
    preview: {
      headerBg: "#18181b",
      headerText: "#ffffff",
      bodyBg: "#ffffff",
      borderColor: "#e4e4e7",
      fontFamily: 'ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif',
    },
  },
];

/** Get a theme definition by ID (falls back to the first). */
export function getTemplate(id: TemplateId): ReportTemplate {
  return REPORT_TEMPLATES.find((t) => t.id === id) ?? REPORT_TEMPLATES[0];
}
