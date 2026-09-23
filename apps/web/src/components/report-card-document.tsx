"use client";

import { useState } from "react";

import type { ReportCard, ReportLayout, ReportWidget } from "@clearis/shared";

import { DEFAULT_LAYOUT, prop, propText, themeClass, widgetDef } from "@/lib/report-layout";

// Same base the API client uses (@clearis/shared): same-origin /api/proxy on
// Vercel (a Next route that forwards to the backend), or a direct API URL when
// NEXT_PUBLIC_API_URL is set.
const API_BASE = (
  process.env.NEXT_PUBLIC_API_URL ??
  "/api/proxy"
).replace(/\/$/, "");

/** Resolve a backend image URL to something a browser <img> can load.
 *
 * - data:/blob:/http(s): URLs are absolute and load as-is — school logos are
 *   stored as base64 data URLs, and mangling them (e.g. prepending an origin)
 *   produces a src that can never load.
 * - backend-rooted paths like /api/uploads/... (student photos) are mapped onto
 *   the same API base the rest of the app uses, so they stay same-origin and
 *   work with canvas-based PDF export. */
function resolveUrl(url?: string | null): string | undefined {
  if (!url) return undefined;
  if (/^(https?:|data:|blob:)/i.test(url)) return url;
  if (url.startsWith("/api/")) return `${API_BASE}${url.slice(4)}`;
  return url.startsWith("/") ? `${API_BASE}${url}` : url;
}

/* ---- date/ordinal helpers (pure, small) ---- */

function ordinal(n: number): string {
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
}

const DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

function formatFull(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso + "T00:00:00");
  if (Number.isNaN(d.getTime())) return "—";
  return `${DAYS[d.getDay()]}, ${ordinal(d.getDate())} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}

function formatDay(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso + "T00:00:00");
  if (Number.isNaN(d.getTime())) return "—";
  return `${ordinal(d.getDate())} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}

function formatPct(n: number | null): string {
  return n == null ? "—" : `${Math.round(n)}%`;
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
}

/**
 * Group the flat widget list into printed rows.
 *
 * A widget set to `width: "half"` pairs with the next half-width widget beside
 * it; everything else gets a row of its own. This is what lets the built-in card
 * keep its original two-column "Cognitive | Psychomotor" band while a school can
 * rearrange the blocks freely — the pairing is a property of the widgets, not a
 * hardcoded section in the markup.
 */
export function layoutRows(widgets: ReportWidget[]): ReportWidget[][] {
  const rows: ReportWidget[][] = [];
  let pending: ReportWidget | null = null;
  for (const widget of widgets) {
    if (prop<string>(widget, "width", "full") === "half") {
      if (pending) {
        rows.push([pending, widget]);
        pending = null;
      } else {
        pending = widget;
      }
      continue;
    }
    if (pending) {
      rows.push([pending]);
      pending = null;
    }
    rows.push([widget]);
  }
  if (pending) rows.push([pending]);
  return rows;
}

/* ------------------------------------------------------------------ */

function PhotoFrame({ src, fallback }: { src?: string | null; fallback: string }) {
  const resolvedSrc = resolveUrl(src);
  const [failed, setFailed] = useState(false);
  if (!resolvedSrc || failed) {
    return (
      <div className="rc-photo">
        <span className="rc-photo-fallback">{fallback}</span>
      </div>
    );
  }
  return (
    <div className="rc-photo">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={resolvedSrc} alt="Student" onError={() => setFailed(true)} />
    </div>
  );
}

function LogoFrame({ src, fallback }: { src?: string | null; fallback: string }) {
  const resolvedSrc = resolveUrl(src);
  const [failed, setFailed] = useState(false);
  if (!resolvedSrc || failed) {
    return (
      <div className="rc-logo">
        <span className="rc-logo-fallback">{fallback}</span>
      </div>
    );
  }
  return (
    <div className="rc-logo">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={resolvedSrc} alt="School crest" onError={() => setFailed(true)} />
    </div>
  );
}

/** One signatory line: rule, name, role, date. */
function Signature({
  who,
  role,
  date,
  showLine = true,
  showDate = true,
}: {
  who: string;
  role?: string;
  date?: string;
  showLine?: boolean;
  showDate?: boolean;
}) {
  return (
    <div className="rc-sign">
      {showLine && <div className="rc-sign-line" />}
      <div className="who">{who}</div>
      {role && <div className="role">{role}</div>}
      {showDate && date && <div className="date">{date}</div>}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Widgets — each one draws a single block of the card, from its own
 * settings, and reads every setting through `prop` so a design saved
 * before that setting existed still renders.                        */
/* ------------------------------------------------------------------ */

function HeaderWidget({ widget, card }: { widget: ReportWidget; card: ReportCard }) {
  return (
    <header className="rc-header">
      {prop(widget, "show_photo", true) && (
        <PhotoFrame src={card.student.photo_url} fallback={initials(card.student.full_name)} />
      )}
      <div>
        <h1 className="rc-school-name">{card.school.name}</h1>
        {prop(widget, "show_motto", true) && card.school.motto && (
          <p className="rc-motto">&ldquo;{card.school.motto}&rdquo;</p>
        )}
        <div className="rc-rule" />
        <h2 className="rc-title">{propText(widget, "title", "Report Card")}</h2>
        <p className="rc-session">{card.academic_year} Academic Session</p>
      </div>
      {prop(widget, "show_logo", true) && (
        <LogoFrame src={card.school.logo_url} fallback={initials(card.school.name)} />
      )}
    </header>
  );
}

function StudentInfoWidget({ widget, card }: { widget: ReportWidget; card: ReportCard }) {
  return (
    <section className="rc-info">
      <div>
        <p>
          <span>Student Name</span>
          <strong>{card.student.full_name}</strong>
        </p>
        <p>
          <span>Admission No.</span>
          <strong>{card.student.admission_no}</strong>
        </p>
        <p>
          <span>Class</span>
          <strong>{card.class_arm.full_name}</strong>
        </p>
        {prop(widget, "show_dob", true) && (
          <p>
            <span>Date of Birth</span>
            <strong>{formatDay(card.student.date_of_birth)}</strong>
          </p>
        )}
      </div>
      <div>
        <p>
          <span>Term</span>
          <strong>{card.term.name}</strong>
        </p>
        {prop(widget, "show_session", true) && (
          <p>
            <span>Academic Year</span>
            <strong>{card.session.name}</strong>
          </p>
        )}
        <p>
          <span>Report Date</span>
          <strong>{formatDay(card.report_date)}</strong>
        </p>
      </div>
    </section>
  );
}

function CognitiveWidget({ widget, card }: { widget: ReportWidget; card: ReportCard }) {
  const summary = card.summary;
  const showComponents = prop(widget, "show_components", true);
  const components = card.subjects[0]?.components ?? [];
  return (
    <section className="rc-panel rc-panel-navy">
      <header className="rc-panel-header">
        <h3>{propText(widget, "title", "Cognitive Domain")}</h3>
        <p>{propText(widget, "subtitle", "Knowledge, Understanding & Thinking Skills")}</p>
      </header>
      <table className="rc-table">
        <thead>
          <tr>
            <th>Subject</th>
            {showComponents &&
              components.map((c) => (
                <th key={c.id} className="num">
                  {c.name}
                  <span className="rc-comp-max">/{Math.round(c.max_score)}</span>
                </th>
              ))}
            <th className="num">Total</th>
            <th className="ctr">Grade</th>
            {prop(widget, "show_remarks", true) && <th>Remark</th>}
          </tr>
        </thead>
        <tbody>
          {card.subjects.map((s) => (
            <tr key={s.subject_id}>
              <td>
                {s.subject_name}
                {prop(widget, "show_core_marker", true) && s.is_core && (
                  <span className="rc-core"> *</span>
                )}
              </td>
              {showComponents &&
                s.components.map((c) => (
                  <td key={c.id} className="num">
                    {c.score ?? "—"}
                  </td>
                ))}
              <td className="num">{s.total ?? "—"}</td>
              <td className="ctr">{s.grade_letter ?? "—"}</td>
              {prop(widget, "show_remarks", true) && <td>{s.remark ?? "—"}</td>}
            </tr>
          ))}
        </tbody>
      </table>
      {prop(widget, "show_average", true) && (
        <div className="rc-avg">
          <span>Cognitive Domain Average</span>
          <strong>
            {summary.average == null ? "—" : `${summary.average}% (${summary.grade_letter ?? ""})`}
          </strong>
        </div>
      )}
    </section>
  );
}

function PsychomotorWidget({ widget, card }: { widget: ReportWidget; card: ReportCard }) {
  return (
    <section className="rc-panel rc-panel-green">
      <header className="rc-panel-header">
        <h3>{propText(widget, "title", "Psychomotor Domain")}</h3>
        <p>{propText(widget, "subtitle", "Skills, Practical Abilities & Physical Development")}</p>
      </header>
      <table className="rc-table">
        <thead>
          <tr>
            <th>Learning Area</th>
            <th className="ctr">Achievement Level</th>
          </tr>
        </thead>
        <tbody>
          {card.psychomotor.length === 0 ? (
            <tr>
              <td colSpan={2} className="ctr" style={{ color: "var(--rc-muted)" }}>
                No assessments recorded
              </td>
            </tr>
          ) : (
            card.psychomotor.map((row) => (
              <tr key={row.learning_area}>
                <td>{row.learning_area}</td>
                <td className="ctr">{row.achievement_level}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
      {prop(widget, "show_average", true) && (
        <div className="rc-avg">
          <span>Psychomotor Domain Average</span>
          <strong>{card.psychomotor_average ?? "—"}</strong>
        </div>
      )}
    </section>
  );
}

function GradingKeyWidget({ widget, card }: { widget: ReportWidget; card: ReportCard }) {
  if (card.grading_key.length === 0) return null;
  return (
    <section className="rc-grading">
      <h3>{propText(widget, "title", "Grading Key")}</h3>
      <div className="rc-bands">
        {card.grading_key.map((b) => (
          <div key={b.letter} className="rc-band">
            <em>{b.letter}</em>
            <span>
              {Math.round(b.min_score)}–{Math.round(b.max_score)}
            </span>
            <b>{b.remark ?? "—"}</b>
          </div>
        ))}
      </div>
    </section>
  );
}

function SummaryWidget({ widget, card }: { widget: ReportWidget; card: ReportCard }) {
  const summary = card.summary;
  const avgPct = summary.average ?? 0;
  const avgBand = card.grading_key.find((b) => avgPct >= b.min_score && avgPct <= b.max_score);
  const position =
    summary.class_rank != null
      ? summary.class_rank >= 1 && summary.class_rank <= 3
        ? ordinal(summary.class_rank)
        : `${summary.class_rank}th`
      : "—";
  const remark = summary.remark ?? avgBand?.remark ?? summary.grade_letter ?? "—";

  return (
    <section className="rc-summary">
      <div className="rc-metric">
        <span className="k">Overall Average</span>
        <span className="v">{summary.average == null ? "—" : `${summary.average}%`}</span>
        <span className="s">{summary.grade_letter ? `(${summary.grade_letter})` : ""}</span>
      </div>
      <div className="rc-metric">
        <span className="k">Overall Grade</span>
        <span className="v">{summary.grade_letter ?? "—"}</span>
        <span className="s">{remark}</span>
      </div>
      {prop(widget, "show_position", true) && (
        <div className="rc-metric">
          <span className="k">Position in Class</span>
          <span className="v">{position}</span>
          <span className="s">Out of {summary.class_size}</span>
        </div>
      )}
      {prop(widget, "show_attendance", true) && (
        <div className="rc-metric">
          <span className="k">Attendance</span>
          <span className="v">{formatPct(card.attendance_pct)}</span>
          <span className="s">This term</span>
        </div>
      )}
      {prop(widget, "show_conduct", true) && (
        <div className="rc-metric">
          <span className="k">Conduct</span>
          <span className="v" style={{ fontSize: 13 }}>
            {card.conduct ?? "—"}
          </span>
          <span className="s">Overall</span>
        </div>
      )}
    </section>
  );
}

function AwardsWidget({ widget, card }: { widget: ReportWidget; card: ReportCard }) {
  const limit = prop(widget, "limit", 6);
  const awards = card.best_in_subjects.slice(0, Math.max(1, limit));
  if (awards.length === 0) return null;
  return (
    <section className="rc-awards">
      <h3>{propText(widget, "title", "Best in Subject")}</h3>
      <div className="rc-award-list">
        {awards.map((b) => (
          <div key={b.subject_id} className="rc-award">
            <strong>★ {b.subject_name}</strong>
            <span>
              Top score {b.top_score}%
              {b.tied &&
                ` · shared with ${b.co_leaders
                  .filter((n) => n !== card.student.full_name)
                  .join(", ")}`}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}

function AttendanceWidget({ widget, card }: { widget: ReportWidget; card: ReportCard }) {
  return (
    <section className="rc-block rc-attendance">
      <div className="rc-block-head">
        <h3>{propText(widget, "title", "Attendance")}</h3>
        <p>{propText(widget, "note", "This term")}</p>
      </div>
      <p className="rc-block-value">{formatPct(card.attendance_pct)}</p>
    </section>
  );
}

function ConductWidget({ widget, card }: { widget: ReportWidget; card: ReportCard }) {
  return (
    <section className="rc-block rc-conduct">
      <div className="rc-block-head">
        <h3>{propText(widget, "title", "Conduct")}</h3>
        <p>{propText(widget, "note", "Overall")}</p>
      </div>
      <p className="rc-block-value rc-block-text">{card.conduct ?? "—"}</p>
    </section>
  );
}

function NextTermWidget({ widget, card }: { widget: ReportWidget; card: ReportCard }) {
  const label = propText(widget, "label", "Next Term Begins");
  const fallback = propText(widget, "fallback", "To be announced");
  return (
    <section className="rc-next">
      {label}:{" "}
      <strong>{card.next_term_date ? formatFull(card.next_term_date) : fallback}</strong>
    </section>
  );
}

function CommentsWidget({ widget, card }: { widget: ReportWidget; card: ReportCard }) {
  const showLines = prop(widget, "show_signature_lines", true);
  const date = formatDay(card.report_date);
  const showVp = prop(widget, "show_vice_principal", true);
  return (
    <section className="rc-comments">
      <h3>{propText(widget, "title", "Comments")}</h3>
      <div className="rc-comment-grid">
        <div className="rc-comment">
          <h4>{propText(widget, "principal_label", "Principal's Comment")}</h4>
          <p>{card.comments.principal ?? "—"}</p>
          <Signature who="Principal" date={date} showLine={showLines} />
        </div>
        {showVp && (
          <div className="rc-comment">
            <h4>{propText(widget, "vice_principal_label", "Vice Principal's Comment")}</h4>
            <p>{card.comments.vice_principal ?? "—"}</p>
            <Signature who="Vice Principal" date={date} showLine={showLines} />
          </div>
        )}
        <div className="rc-comment">
          <h4>{propText(widget, "homeroom_label", "Homeroom Teacher's Comment")}</h4>
          <p>{card.comments.homeroom ?? "—"}</p>
          <Signature
            who={card.homeroom_teacher ?? "Homeroom Teacher"}
            date={date}
            showLine={showLines}
          />
        </div>
      </div>
    </section>
  );
}

function SignaturesWidget({ widget, card }: { widget: ReportWidget; card: ReportCard }) {
  const showDates = prop(widget, "show_dates", true);
  const date = formatDay(card.report_date);
  const names = [
    propText(widget, "principal_label", "Principal"),
    propText(widget, "vice_principal_label", "Vice Principal"),
    propText(widget, "homeroom_label", "Homeroom Teacher"),
  ].filter(Boolean);
  if (names.length === 0) return null;
  return (
    <section className="rc-signblock">
      <h3>{propText(widget, "title", "Signatures")}</h3>
      <div className="rc-signgrid">
        {names.map((name) => (
          <Signature key={name} who={name} date={date} showDate={showDates} />
        ))}
      </div>
    </section>
  );
}

function CustomTextWidget({ widget }: { widget: ReportWidget; card: ReportCard }) {
  const body = propText(widget, "body");
  const title = propText(widget, "title");
  // Nothing to draw yet (a freshly dragged note) — render nothing rather than an
  // empty box on a printed card.
  if (!title && !body) return null;
  return (
    <section className="rc-note">
      {title && <h3>{title}</h3>}
      {body && <p>{body}</p>}
    </section>
  );
}

function SpacerWidget({ widget }: { widget: ReportWidget; card: ReportCard }) {
  return <div className="rc-spacer" style={{ height: prop(widget, "height", 12) }} />;
}

function WidgetView({ widget, card }: { widget: ReportWidget; card: ReportCard }) {
  switch (widget.type) {
    case "header":
      return <HeaderWidget widget={widget} card={card} />;
    case "student_info":
      return <StudentInfoWidget widget={widget} card={card} />;
    case "cognitive_domain":
      return <CognitiveWidget widget={widget} card={card} />;
    case "psychomotor_domain":
      return <PsychomotorWidget widget={widget} card={card} />;
    case "grading_key":
      return <GradingKeyWidget widget={widget} card={card} />;
    case "performance_summary":
      return <SummaryWidget widget={widget} card={card} />;
    case "best_in_subjects":
      return <AwardsWidget widget={widget} card={card} />;
    case "attendance":
      return <AttendanceWidget widget={widget} card={card} />;
    case "conduct":
      return <ConductWidget widget={widget} card={card} />;
    case "next_term":
      return <NextTermWidget widget={widget} card={card} />;
    case "comments":
      return <CommentsWidget widget={widget} card={card} />;
    case "signatures":
      return <SignaturesWidget widget={widget} card={card} />;
    case "custom_text":
      return <CustomTextWidget widget={widget} card={card} />;
    case "spacer":
      return <SpacerWidget widget={widget} card={card} />;
    default:
      // Unreachable through the API (widget types are validated on write), but a
      // card must never crash: an unknown block is labelled, not thrown.
      return (
        <section className="rc-note">
          <h3>{widgetDef(widget.type).label}</h3>
        </section>
      );
  }
}

/**
 * The printable report card.
 *
 * `layout` is the school's saved design (from `useReportCardDesign`, or straight
 * from the public portal's check-in). It is optional only so a caller mid-load
 * can still render something sane — the built-in card — rather than a blank page.
 */
export function ReportCardDocument({
  card,
  layout,
  className,
}: {
  card: ReportCard;
  layout?: ReportLayout | null;
  className?: string;
}) {
  const effective = layout ?? DEFAULT_LAYOUT;
  const visible = effective.widgets.filter((w) => !w.hidden);
  const rows = layoutRows(visible);

  return (
    <div className={`rc-sheet ${themeClass(effective.theme)}${className ? ` ${className}` : ""}`}>
      <div className="rc-pad">
        {rows.map((row) =>
          row.length > 1 ? (
            <div className="rc-columns" key={row.map((w) => w.id).join("+")}>
              {row.map((widget) => (
                <WidgetView key={widget.id} widget={widget} card={card} />
              ))}
            </div>
          ) : (
            <WidgetView key={row[0].id} widget={row[0]} card={card} />
          ),
        )}
      </div>
    </div>
  );
}
