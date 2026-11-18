/**
 * Student progress tracking — the shapes the API returns and the two readings
 * the page makes of them.
 *
 * The feature answers "is this child getting better?", and the only honest
 * display of that is: a direction, the size of the latest move, and the series it
 * came from. A mark with no earlier mark to compare against is shown as
 * "needs another mark" rather than guessed at — the API already decides that
 * (``direction: "insufficient"``), so the page must not turn it into "steady".
 */

export type TrendDirection = "improving" | "declining" | "steady" | "insufficient";
export type TrendBasis = "terms" | "components" | "none";

export interface Trend {
  direction: TrendDirection;
  delta: number | null;
  change: number | null;
  samples: number;
  basis: TrendBasis;
}

export interface TermPoint {
  term_id: string;
  term_name: string;
  value: number;
  status?: string | null;
}

export interface ComponentPoint {
  component_id: string;
  name: string;
  percent: number | null;
}

export interface SubjectProgress {
  subject_id: string;
  subject_name: string;
  is_core: boolean;
  latest: number | null;
  trend: Trend;
  terms: TermPoint[];
  components: { term_name: string | null; series: ComponentPoint[] } | null;
}

export interface StudentProgress {
  student_id: string;
  admission_no: string;
  full_name: string;
  gender: string;
  overall: { series: TermPoint[]; trend: Trend };
  subjects: SubjectProgress[];
}

export interface ProgressPayload {
  arm: { id: string; full_name: string };
  session: { id: string; name: string };
  terms: { id: string; name: string; term_no: number }[];
  subjects: { id: string; name: string; is_core: boolean }[];
  core_configured: boolean;
  students: StudentProgress[];
}

/** What the trend badge says. Never calls insufficient data "steady". */
export function trendLabel(trend: Trend): string {
  switch (trend.direction) {
    case "improving":
      return "Improving";
    case "declining":
      return "Falling";
    case "steady":
      return "Steady";
    default:
      return "Needs another mark";
  }
}

/** The tone the badge wears — good, bad, neutral, or no signal at all. */
export function trendTone(trend: Trend): "up" | "down" | "flat" | "none" {
  if (trend.direction === "improving") return "up";
  if (trend.direction === "declining") return "down";
  if (trend.direction === "steady") return "flat";
  return "none";
}

/** "+4.2" / "−3.0" / "—", for the small number beside the arrow. */
export function deltaLabel(trend: Trend): string {
  if (trend.delta === null || trend.delta === undefined) return "—";
  const value = Math.round(trend.delta * 10) / 10;
  if (value > 0) return `+${value}`;
  if (value < 0) return `−${Math.abs(value)}`;
  return "0";
}

/** The series a sparkline should draw: term totals, else this term's components. */
export function seriesFor(subject: SubjectProgress): number[] {
  if (subject.terms.length >= 2) return subject.terms.map((point) => point.value);
  const components = subject.components?.series ?? [];
  return components
    .map((point) => point.percent)
    .filter((value): value is number => value !== null && value !== undefined);
}

/**
 * An SVG polyline for a series, normalised into a box.
 *
 * A flat series draws along the middle rather than pinned to the top, so a pupil
 * who has not moved reads as a level line instead of a rise from zero.
 */
export function sparklinePoints(
  values: number[],
  width = 72,
  height = 24,
  pad = 3,
): string {
  if (values.length === 0) return "";
  if (values.length === 1) {
    const y = height / 2;
    return `${pad},${y} ${width - pad},${y}`;
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min;
  const innerHeight = height - pad * 2;
  return values
    .map((value, index) => {
      const x = pad + (index * (width - pad * 2)) / (values.length - 1);
      const ratio = span === 0 ? 0.5 : (value - min) / span;
      const y = pad + (1 - ratio) * innerHeight;
      return `${Math.round(x * 10) / 10},${Math.round(y * 10) / 10}`;
    })
    .join(" ");
}