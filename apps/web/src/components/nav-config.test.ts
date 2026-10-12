import { describe, expect, it } from "vitest";

import { pageMeta, visiblePanel } from "./nav-config";

/**
 * A page nobody can navigate to is a page that does not exist, which is how the
 * broadsheet and cumulative sheets sat before: built, permission-gated, and
 * unreachable from the app. These pin them into the navigation for exactly the
 * roles the API already trusts with `results.report_card`.
 */

const hrefsFor = (permissions: string[], role: string) =>
  visiblePanel(permissions, false, role).flatMap((section) => section.items.map((i) => i.href));

describe("result sheets in the navigation", () => {
  it("lists the broadsheet and cumulative results for the exam office", () => {
    const hrefs = hrefsFor(["results.report_card"], "exam_officer");
    expect(hrefs).toContain("/reports/broadsheet");
    expect(hrefs).toContain("/reports/cumulative");
  });

  it("lists them for the principal, who holds the same permission", () => {
    const hrefs = hrefsFor(["results.report_card"], "principal");
    expect(hrefs).toContain("/reports/broadsheet");
    expect(hrefs).toContain("/reports/cumulative");
  });

  it("hides them from a teacher, who may enter scores but never a card", () => {
    const hrefs = hrefsFor(["results.enter", "results.view"], "teacher");
    expect(hrefs).not.toContain("/reports/broadsheet");
    expect(hrefs).not.toContain("/reports/cumulative");
    expect(hrefs).not.toContain("/reports");
  });

  it("keeps them in the Result Generation group alongside the cards", () => {
    const section = visiblePanel(["results.report_card"], false, "exam_officer").find(
      (group) => group.label === "Result Generation",
    );
    expect(section).toBeDefined();
    expect(section!.items.map((item) => item.href)).toEqual(
      expect.arrayContaining(["/reports", "/reports/broadsheet", "/reports/cumulative"]),
    );
  });
});

describe("result sheet page titles", () => {
  it("names the broadsheet page rather than inheriting the report-cards match", () => {
    // `/reports/broadsheet` also starts with `/reports`, so this fails if the
    // longest-prefix match ever regresses.
    expect(pageMeta("/reports/broadsheet")).toEqual({
      title: "Broadsheet",
      breadcrumb: "Result Generation",
    });
  });

  it("names the cumulative page", () => {
    expect(pageMeta("/reports/cumulative")).toEqual({
      title: "Cumulative Results",
      breadcrumb: "Result Generation",
    });
  });

  it("still names the report cards desk", () => {
    expect(pageMeta("/reports").title).toBe("Report Cards");
  });
});
