import { describe, expect, it } from "vitest";

import {
  deltaLabel,
  seriesFor,
  sparklinePoints,
  trendLabel,
  trendTone,
  type SubjectProgress,
  type Trend,
} from "./progress";

const trend = (over: Partial<Trend> = {}): Trend => ({
  direction: "improving",
  delta: 4,
  change: 6,
  samples: 2,
  basis: "terms",
  ...over,
});

describe("what a trend says", () => {
  it("names each direction plainly", () => {
    expect(trendLabel(trend())).toBe("Improving");
    expect(trendLabel(trend({ direction: "declining" }))).toBe("Falling");
    expect(trendLabel(trend({ direction: "steady" }))).toBe("Steady");
  });

  it("never calls an unproven direction steady", () => {
    // One observation is not a trend; the page must say so rather than "Steady".
    expect(trendLabel(trend({ direction: "insufficient", delta: null }))).toBe(
      "Needs another mark",
    );
    expect(trendTone(trend({ direction: "insufficient" }))).toBe("none");
  });

  it("tones the direction for colouring", () => {
    expect(trendTone(trend())).toBe("up");
    expect(trendTone(trend({ direction: "declining" }))).toBe("down");
    expect(trendTone(trend({ direction: "steady" }))).toBe("flat");
  });

  it("signs the movement", () => {
    expect(deltaLabel(trend({ delta: 4.25 }))).toBe("+4.3");
    expect(deltaLabel(trend({ delta: -3 }))).toBe("−3");
    expect(deltaLabel(trend({ delta: 0 }))).toBe("0");
    expect(deltaLabel(trend({ delta: null }))).toBe("—");
  });
});

const subject = (over: Partial<SubjectProgress> = {}): SubjectProgress => ({
  subject_id: "s1",
  subject_name: "Mathematics",
  is_core: true,
  latest: 61,
  trend: trend(),
  terms: [
    { term_id: "t1", term_name: "First Term", value: 48 },
    { term_id: "t2", term_name: "Second Term", value: 61 },
  ],
  components: null,
  ...over,
});

describe("which series a sparkline draws", () => {
  it("prefers term totals once there are two", () => {
    expect(seriesFor(subject())).toEqual([48, 61]);
  });

  it("falls back to this term's components when a single term exists", () => {
    const single = subject({
      terms: [{ term_id: "t1", term_name: "First Term", value: 55 }],
      components: {
        term_name: "First Term",
        series: [
          { component_id: "c1", name: "1st CA", percent: 50 },
          { component_id: "c2", name: "2nd CA", percent: 80 },
        ],
      },
    });
    expect(seriesFor(single)).toEqual([50, 80]);
  });

  it("drops a component with no mark instead of drawing a zero", () => {
    const single = subject({
      terms: [],
      components: {
        term_name: "First Term",
        series: [
          { component_id: "c1", name: "1st CA", percent: 50 },
          { component_id: "c2", name: "2nd CA", percent: null },
        ],
      },
    });
    expect(seriesFor(single)).toEqual([50]);
  });
});

describe("the sparkline geometry", () => {
  it("draws one point per observation, inside the box", () => {
    const points = sparklinePoints([50, 80], 72, 24, 3)
      .split(" ")
      .map((pair) => pair.split(",").map(Number));
    expect(points).toHaveLength(2);
    for (const [x, y] of points) {
      expect(x).toBeGreaterThanOrEqual(3);
      expect(x).toBeLessThanOrEqual(69);
      expect(y).toBeGreaterThanOrEqual(3);
      expect(y).toBeLessThanOrEqual(21);
    }
    // Rising series: the later point is higher up the box.
    expect(points[1][1]).toBeLessThan(points[0][1]);
  });

  it("draws a flat series along the middle, not pinned to the top", () => {
    const points = sparklinePoints([60, 60, 60], 72, 24, 3)
      .split(" ")
      .map((pair) => pair.split(",").map(Number));
    expect(points.every(([, y]) => y === 12)).toBe(true);
  });

  it("survives a single observation", () => {
    expect(sparklinePoints([42])).not.toBe("");
    expect(sparklinePoints([])).toBe("");
  });
});