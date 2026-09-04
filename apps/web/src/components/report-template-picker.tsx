"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Check, Palette, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  REPORT_TEMPLATES,
  getSelectedTemplate,
  setSelectedTemplate,
  type TemplateId,
} from "@/lib/report-templates";

const ease = [0.25, 0.46, 0.45, 0.94] as const;

function TemplateThumbnail({ template, selected }: { template: (typeof REPORT_TEMPLATES)[number]; selected: boolean }) {
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
          <div className="h-2 w-20 rounded bg-white/30" style={{ fontFamily: template.preview.fontFamily }} />
          <div className="h-1.5 w-14 rounded bg-white/15" />
        </div>
      </div>

      {/* Mini body */}
      <div className="flex flex-col gap-2 p-3">
        {/* Student info mock */}
        <div className="flex gap-2">
          <div className="h-6 w-16 rounded border" style={{ borderColor: template.preview.borderColor }} />
          <div className="flex-1 space-y-1">
            <div className="h-1.5 w-16 rounded bg-current/10" />
            <div className="h-1.5 w-10 rounded bg-current/5" />
          </div>
        </div>

        {/* Table mock */}
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

        {/* Summary bar mock */}
        <div className="flex gap-1">
          {[...Array(3)].map((_, i) => (
            <div
              key={i}
              className="h-3 flex-1 rounded"
              style={{ background: template.accent + "10" }}
            />
          ))}
        </div>
      </div>

      {/* Selected badge */}
      <AnimatePresence>
        {selected && (
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            exit={{ scale: 0 }}
            transition={{ type: "spring", stiffness: 300, damping: 20 }}
            className="absolute right-2 top-2 flex h-6 w-6 items-center justify-center rounded-full"
            style={{ background: template.accent }}
          >
            <Check className="h-3.5 w-3.5 text-white" strokeWidth={3} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

interface ReportTemplatePickerProps {
  /** If provided, control externally. Otherwise uses internal state. */
  value?: TemplateId;
  onChange?: (id: TemplateId) => void;
}

export function ReportTemplatePicker({ value, onChange }: ReportTemplatePickerProps) {
  const [selected, setSelected] = useState<TemplateId>(value ?? getSelectedTemplate());

  function handleSelect(id: TemplateId) {
    setSelected(id);
    setSelectedTemplate(id);
    onChange?.(id);
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-violet-50 to-rose-50 ring-1 ring-violet-100">
          <Palette className="h-5 w-5 text-violet-600" />
        </div>
        <div>
          <h3 className="text-sm font-semibold tracking-tight text-foreground">Report Card Templates</h3>
          <p className="text-xs text-muted-foreground/60">Choose a visual style for your school&apos;s report cards</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {REPORT_TEMPLATES.map((template, idx) => (
          <motion.button
            key={template.id}
            onClick={() => handleSelect(template.id)}
            className={cn(
              "group relative flex flex-col items-start gap-3 rounded-2xl border-2 p-4 text-left transition-all duration-300",
              selected === template.id
                ? "border-foreground/20 bg-foreground/[0.02]"
                : "border-transparent bg-white hover:border-foreground/10 hover:bg-foreground/[0.01] hover:-translate-y-0.5 hover:shadow-lg",
            )}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: idx * 0.08, ease }}
            whileTap={{ scale: 0.98 }}
          >
            <TemplateThumbnail template={template} selected={selected === template.id} />

            <div className="w-full">
              <div className="flex items-center gap-2">
                <p className="text-sm font-semibold text-foreground">{template.name}</p>
                {selected === template.id && (
                  <motion.span
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-semibold text-primary"
                  >
                    <Sparkles className="h-2.5 w-2.5" /> Active
                  </motion.span>
                )}
              </div>
              <p className="mt-1 text-xs leading-relaxed text-muted-foreground/60">{template.description}</p>
            </div>

            {/* Accent color dot */}
            <div
              className="absolute right-3 top-3 h-3 w-3 rounded-full ring-2 ring-white"
              style={{ background: template.accent }}
            />
          </motion.button>
        ))}
      </div>
    </div>
  );
}
