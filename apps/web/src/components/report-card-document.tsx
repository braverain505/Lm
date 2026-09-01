"use client";

import type { ReportCard } from "@schoolos/shared";

const API_BASE = (
  process.env.NEXT_PUBLIC_API_URL ??
  "https://schoolos-api-5066.onrender.com/api"
).replace(/\/$/, "");

/** Resolve relative API URLs to absolute URLs for cross-origin image loading. */
function resolveUrl(url?: string | null): string | undefined {
  if (!url) return undefined;
  if (url.startsWith("http")) return url;
  // Relative path like /api/uploads/... → prepend API base without /api suffix
  const base = API_BASE.replace(/\/api$/, "");
  return `${base}${url}`;
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

/* ------------------------------------------------------------------ */

function PhotoFrame({ src, fallback }: { src?: string | null; fallback: string }) {
  const resolvedSrc = resolveUrl(src);
  return (
    <div className="rc-photo">
      {resolvedSrc ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={resolvedSrc} alt="Student" crossOrigin="anonymous" />
      ) : (
        <span className="rc-photo-fallback">{fallback}</span>
      )}
    </div>
  );
}

function LogoFrame({ src, fallback }: { src?: string | null; fallback: string }) {
  const resolvedSrc = resolveUrl(src);
  return (
    <div className="rc-logo">
      {resolvedSrc ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={resolvedSrc} alt="School crest" crossOrigin="anonymous" />
      ) : (
        <span className="rc-logo-fallback">{fallback}</span>
      )}
    </div>
  );
}

export function ReportCardDocument({ card }: { card: ReportCard }) {
  const summary = card.summary;
  const avgPct = summary.average ?? 0;
  const avgBand = card.grading_key.find(
    (b) => avgPct >= b.min_score && avgPct <= b.max_score,
  );
  const position =
    summary.class_rank != null
      ? summary.class_rank >= 1 && summary.class_rank <= 3
        ? ordinal(summary.class_rank)
        : `${summary.class_rank}th`
      : "—";
  const remark = summary.remark ?? avgBand?.remark ?? summary.grade_letter ?? "—";

  return (
    <div className="rc-sheet">
      <div className="rc-pad">
        {/* -------- Header: photo | identity | logo -------- */}
        <header className="rc-header">
          <PhotoFrame src={card.student.photo_url} fallback={initials(card.student.full_name)} />
          <div>
            <h1 className="rc-school-name">{card.school.name}</h1>
            {card.school.motto && (
              <p className="rc-motto">“{card.school.motto}”</p>
            )}
            <div className="rc-rule" />
            <h2 className="rc-title">Report Card</h2>
            <p className="rc-session">{card.academic_year} Academic Session</p>
          </div>
          <LogoFrame src={card.school.logo_url} fallback={initials(card.school.name)} />
        </header>

        {/* -------- Student information -------- */}
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
            <p>
              <span>Date of Birth</span>
              <strong>{formatDay(card.student.date_of_birth)}</strong>
            </p>
          </div>
          <div>
            <p>
              <span>Term</span>
              <strong>{card.term.name}</strong>
            </p>
            <p>
              <span>Academic Year</span>
              <strong>{card.session.name}</strong>
            </p>
            <p>
              <span>Report Date</span>
              <strong>{formatDay(card.report_date)}</strong>
            </p>
          </div>
        </section>

        {/* -------- Assessment columns -------- */}
        <div className="rc-columns">
          {/* Cognitive domain */}
          <section className="rc-panel rc-panel-navy">
            <header className="rc-panel-header">
              <h3>Cognitive Domain</h3>
              <p>Knowledge, Understanding &amp; Thinking Skills</p>
            </header>
            <table className="rc-table">
              <thead>
                <tr>
                  <th>Subject</th>
                  {card.subjects[0]?.components.map((c) => (
                    <th key={c.id} className="num">
                      {c.name}
                      <span className="rc-comp-max">/{Math.round(c.max_score)}</span>
                    </th>
                  ))}
                  <th className="num">Total</th>
                  <th className="ctr">Grade</th>
                  <th>Remark</th>
                </tr>
              </thead>
              <tbody>
                {card.subjects.map((s) => (
                  <tr key={s.subject_id}>
                    <td>
                      {s.subject_name}
                      {s.is_core && <span className="rc-core"> *</span>}
                    </td>
                    {s.components.map((c) => (
                      <td key={c.id} className="num">
                        {c.score ?? "—"}
                      </td>
                    ))}
                    <td className="num">{s.total ?? "—"}</td>
                    <td className="ctr">{s.grade_letter ?? "—"}</td>
                    <td>{s.remark ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="rc-avg">
              <span>Cognitive Domain Average</span>
              <strong>
                {summary.average == null ? "—" : `${summary.average}% (${summary.grade_letter ?? ""})`}
              </strong>
            </div>
          </section>

          {/* Psychomotor domain */}
          <section className="rc-panel rc-panel-green">
            <header className="rc-panel-header">
              <h3>Psychomotor Domain</h3>
              <p>Skills, Practical Abilities &amp; Physical Development</p>
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
            <div className="rc-avg">
              <span>Psychomotor Domain Average</span>
              <strong>{card.psychomotor_average ?? "—"}</strong>
            </div>
          </section>
        </div>

        {/* -------- Grading key -------- */}
        {card.grading_key.length > 0 && (
          <section className="rc-grading">
            <h3>Grading Key</h3>
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
        )}

        {/* -------- Performance summary -------- */}
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
          <div className="rc-metric">
            <span className="k">Position in Class</span>
            <span className="v">{position}</span>
            <span className="s">Out of {summary.class_size}</span>
          </div>
          <div className="rc-metric">
            <span className="k">Attendance</span>
            <span className="v">{formatPct(card.attendance_pct)}</span>
            <span className="s">This term</span>
          </div>
          <div className="rc-metric">
            <span className="k">Conduct</span>
            <span className="v" style={{ fontSize: 15 }}>
              {card.conduct ?? "—"}
            </span>
            <span className="s">Overall</span>
          </div>
        </section>

        {/* -------- Best in core subject -------- */}
        {card.best_in_subjects.length > 0 && (
          <section className="rc-awards">
            <h3>Best in Subject</h3>
            <div className="rc-award-list">
              {card.best_in_subjects.map((b) => (
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
        )}

        {/* -------- Next term -------- */}
        <section className="rc-next">
          Next Term Begins:{" "}
          <strong>{card.next_term_date ? formatFull(card.next_term_date) : "To be announced"}</strong>
        </section>

        {/* -------- Comments -------- */}
        <section className="rc-comments">
          <h3>Comments</h3>
          <div className="rc-comment-grid">
            <div className="rc-comment">
              <h4>Principal&rsquo;s Comment</h4>
              <p>{card.comments.principal ?? "—"}</p>
              <div className="rc-sign">
                <div className="rc-sign-line" />
                <div className="who">Principal</div>
                <div className="date">{formatDay(card.report_date)}</div>
              </div>
            </div>
            <div className="rc-comment">
              <h4>Vice Principal&rsquo;s Comment</h4>
              <p>{card.comments.vice_principal ?? "—"}</p>
              <div className="rc-sign">
                <div className="rc-sign-line" />
                <div className="who">Vice Principal</div>
                <div className="date">{formatDay(card.report_date)}</div>
              </div>
            </div>
            <div className="rc-comment">
              <h4>Homeroom Teacher&rsquo;s Comment</h4>
              <p>{card.comments.homeroom ?? "—"}</p>
              <div className="rc-sign">
                <div className="rc-sign-line" />
                <div className="who">{card.homeroom_teacher ?? "Homeroom Teacher"}</div>
                <div className="date">{formatDay(card.report_date)}</div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}