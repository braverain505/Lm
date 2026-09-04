/**
 * Report Card Template System
 *
 * Schools can choose from different report card visual styles.
 * Templates are stored in localStorage and applied via CSS class on the report card sheet.
 */

export type TemplateId = "classic" | "modern" | "elegant" | "minimal";

export interface ReportTemplate {
  id: TemplateId;
  name: string;
  description: string;
  accent: string;       // Primary accent color for preview thumbnail
  accentLight: string;  // Lighter variant for bg
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

const STORAGE_KEY = "clearis.report_template";

/** Get the currently selected template ID. Falls back to "classic". */
export function getSelectedTemplate(): TemplateId {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored && REPORT_TEMPLATES.some((t) => t.id === stored)) {
      return stored as TemplateId;
    }
  } catch {
    /* SSR or storage unavailable */
  }
  return "classic";
}

/** Save the selected template ID to localStorage. */
export function setSelectedTemplate(id: TemplateId): void {
  try {
    localStorage.setItem(STORAGE_KEY, id);
  } catch {
    /* SSR or storage unavailable */
  }
}

/** Get a template definition by ID. */
export function getTemplate(id: TemplateId): ReportTemplate {
  return REPORT_TEMPLATES.find((t) => t.id === id) ?? REPORT_TEMPLATES[0];
}
