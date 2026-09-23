"use client";

import { motion } from "framer-motion";
import { Check, Palette } from "lucide-react";

import type { ReportTheme } from "@clearis/shared";

import { REPORT_TEMPLATES, type TemplateId } from "@/lib/report-templates";
import { cn } from "@/lib/utils";

const ease = [0.25, 0.46, 0.45, 0.94] as const;

function ThemeThumbnail({
  template,
  selected,
}: {
  template: (typeof REPORT_TEMPLATES)[number];
  selected: boolean;
}) {
  return (
    <div
      className="relative flex flex-col overflow-hidden rounded-xl border transition-all duration-300"
      style={{
        borderColor: selected ? template.accent : template.preview.borderColor,
        background: template.preview.bodyBg,
        boxShadow: selected
          ? `0 4px 14px ${template.accent}22, 0 0 0 2px ${template.accent}33`
          : "0 1px 3px rgba(0,0,0,0.04)",
      }}
    >
      {/* Mini header */}
      <div
        className="flex items-center gap-2 px-4 py-3"
        style={{ background: template.preview.headerBg, color: template.preview.headerText }}
      >
        <div className="h-5 w-5 rounded-full border border-white/30 bg-white/20" />
        <div className="flex-1 space-y-1">
          <div className="h-2 w-20 rounded bg-white/30" />
          <div className="h-1.5 w-14 rounded bg-white/15" />
        </div>
      </div>

      {/* Mini body */}
      <div className="flex flex-col gap-2 p-3">
        <div className="flex gap-2">
          <div className="h-6 w-16 rounded border" style={{ borderColor: template.preview.borderColor }} />
          <div className="flex-1 space-y-1">
            <div className="h-1.5 w-16 rounded bg-current/10" />
            <div className="h-1.5 w-10 rounded bg-current/5" />
          </div>
        </div>

        <div className="space-y-1">
          <div className="flex gap-1">
            {[...Array(4)].map((_, i) => (
              <div
                key={i}
                className="h-1.5 flex-1 rounded"
                style={{
                  background: i === 0 ? template.accent + "20" : template.preview.borderColor,
                }}
              />
            ))}
          </div>
          {[...Array(3)].map((_, i) => (
            <div key={i} className="flex gap-1">
              {[...Array(4)].map((_, j) => (
                <div
                  key={j}
                  className="h-1.5 flex-1 rounded"
                  style={{
                    background: j === 0 ? template.accent + "15" : template.preview.borderColor + "80",
                  }}
                />
              ))}
            </div>
          ))}
        </div>
      </div>

      {selected && (
        <motion.div
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ type: "spring", stiffness: 300, damping: 20 }}
          className="absolute right-2 top-2 flex h-6 w-6 items-center justify-center rounded-full"
          style={{ background: template.accent }}
        >
          <Check className="h-3.5 w-3.5 text-white" strokeWidth={3} />
        </motion.div>
      )}
    </div>
  );
}

interface ReportTemplatePickerProps {
  /** The theme of the design currently in effect — this is a controlled input. */
  value: TemplateId;
  /** Persist the choice. Omit to render the themes read-only. */
  onChange?: (id: TemplateId) => void;
  disabled?: boolean;
}

/**
 * The card style picker.
 *
 * A theme belongs to the school's saved design, so this is controlled and has no
 * storage of its own: the caller decides whether selecting a style edits the
 * design (admins) or simply shows which style is in use (everyone else).
 */
export function ReportTemplatePicker({
  value,
  onChange,
  disabled = false,
}: ReportTemplatePickerProps) {
  const interactive = !!onChange && !disabled;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-violet-50 to-rose-50 ring-1 ring-violet-100">
          <Palette className="h-5 w-5 text-violet-600" />
        </div>
        <div>
          <h3 className="text-sm font-semibold tracking-tight text-foreground">Card style</h3>
          <p className="text-xs text-muted-foreground/60">
            {interactive
              ? "Applies to the school's current report card design, for everyone"
              : "The style your school's report cards are printed in"}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {REPORT_TEMPLATES.map((template, idx) => (
          <motion.button
            key={template.id}
            type="button"
            disabled={!interactive}
            onClick={() => onChange?.(template.id as ReportTheme)}
            className={cn(
              "group relative flex flex-col items-start gap-3 rounded-2xl border-2 p-4 text-left transition-all duration-300",
              value === template.id
                ? "border-foreground/20 bg-foreground/[0.02]"
                : "border-transparent bg-white hover:border-foreground/10 hover:bg-foreground/[0.01]",
              interactive
                ? "hover:-translate-y-0.5 hover:shadow-lg"
                : "cursor-default",
            )}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: idx * 0.08, ease }}
            whileTap={interactive ? { scale: 0.98 } : undefined}
          >
            <ThemeThumbnail template={template} selected={value === template.id} />

            <div className="w-full">
              <p className="text-sm font-semibold text-foreground">{template.name}</p>
              <p className="mt-1 text-xs leading-relaxed text-muted-foreground/60">
                {template.description}
              </p>
            </div>

            <div
              className="absolute right-3 top-3 h-3 w-3 rounded-full ring-2 ring-white"
              style={{ background: template.accent }}
            />
          </motion.button>
        ))}
      </div>

      {!interactive && (
        <p className="text-xs text-muted-foreground/60">
          Only a school admin can change the card style — ask them, or open the Report card
          designer.
        </p>
      )}
    </div>
  );
}
