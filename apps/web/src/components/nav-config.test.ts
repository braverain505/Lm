import { describe, expect, it } from "vitest";

import { activeHref, pageMeta, visiblePanel } from "./nav-config";

/**
 * A page nobody can navigate to is a page that does not exist, which is how the
 * broadsheet and cumulative sheets sat before: built, permission-gated, and
 * unreachable from the app. These pin them into the navigation for exactly the
 * roles the API already trusts with `results.report_card`.
 */

const hrefsFor = (permissions: string[], role: string, homeroom = false) =>
  visiblePanel(permissions, false, role, homeroom).flatMap((section) =>
    section.items.map((i) => i.href),
  );

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

describe("the teacher's own scoresheet", () => {
  it("offers View Scoresheet to the roles that enter marks", () => {
    for (const role of ["teacher", "homeroom_teacher"]) {
      expect(hrefsFor(["results.view", "results.enter"], role)).toContain("/results/scoresheet");
    }
  });

  it("keeps it away from leadership, who read grids through the results desk", () => {
    const hrefs = hrefsFor(["results.view", "results.verify"], "principal");
    expect(hrefs).not.toContain("/results/scoresheet");
  });

  it("names the page rather than inheriting the score-entry title", () => {
    // `/results/scoresheet` is not `/results/score`, whatever startsWith says.
    expect(pageMeta("/results/scoresheet")).toEqual({
      title: "View Scoresheet",
      breadcrumb: "Academics",
    });
    expect(pageMeta("/results/score")).toEqual({ title: "Score Entry", breadcrumb: "Academics" });
  });
});

describe("which nav item a page belongs to", () => {
  const hrefs = ["/dashboard", "/results", "/results/score", "/results/scoresheet"];

  it("picks the page itself, not the section it sits in", () => {
    expect(activeHref("/results/scoresheet", hrefs)).toBe("/results/scoresheet");
    expect(activeHref("/results/score", hrefs)).toBe("/results/score");
    expect(activeHref("/results", hrefs)).toBe("/results");
  });

  it("does not light up the score grid for the scoresheet page", () => {
    // The bug this guards: "/results/scoresheet".startsWith("/results/score").
    expect(activeHref("/results/scoresheet", hrefs)).not.toBe("/results/score");
  });

  it("keeps a page lit for its own sub-routes", () => {
    expect(activeHref("/results/comments", ["/results", "/results/comments"])).toBe("/results/comments");
  });

  it("treats the root as the dashboard", () => {
    expect(activeHref("/", hrefs)).toBe("/dashboard");
  });

  it("ignores a query string and a trailing slash", () => {
    expect(activeHref("/classes/", ["/classes"])).toBe("/classes");
    expect(activeHref("/results", ["/classes?view=subjects", "/results"])).toBe("/results");
  });

  it("lights nothing when the page is not in the list", () => {
    expect(activeHref("/billing", hrefs)).toBeNull();
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


describe("the class teacher's own records", () => {
  const teacherPerms = ["results.view", "results.enter", "results.comment"];

  it("shows psychomotor to a class teacher who carries the plain teacher role", () => {
    // The rule is the assignment, not the label: schools set the form teacher in
    // the class and usually leave them on the ordinary teacher role.
    const hrefs = hrefsFor(teacherPerms, "teacher", true);
    expect(hrefs).toContain("/results/psychomotor");
    expect(hrefs).toContain("/results/comments");
  });

  it("hides them from a teacher who is nobody's class teacher", () => {
    const hrefs = hrefsFor(teacherPerms, "teacher", false);
    expect(hrefs).not.toContain("/results/psychomotor");
    expect(hrefs).not.toContain("/results/comments");
  });

  it("hides them even when the role label says homeroom_teacher but no class is theirs", () => {
    const hrefs = hrefsFor(teacherPerms, "homeroom_teacher", false);
    expect(hrefs).not.toContain("/results/psychomotor");
  });

  it("keeps them away from leadership, who hold the permission but teach no class", () => {
    const hrefs = hrefsFor(["results.comment", "results.report_card"], "principal", false);
    expect(hrefs).not.toContain("/results/psychomotor");
  });
});
