import { REPORT_THEMES, REPORT_WIDGET_TYPES, type ReportWidget } from "@clearis/shared";
import { describe, expect, it } from "vitest";

import {
  DEFAULT_LAYOUT,
  WIDGET_CATALOG,
  canAdd,
  cloneLayout,
  emptyLayout,
  isKnownTheme,
  moveWidget,
  newWidget,
  prop,
  propText,
  removeWidget,
  setWidgetProp,
  themeClass,
  updateWidget,
  widgetDef,
  widgetTitle,
} from "./report-layout";

/**
 * These tests pin the client half of the report-card contract. The API validates
 * the same closed widget list (`app/schemas/report_card.py`), so a drift here is
 * what makes a design the school built become unsaveable.
 */
describe("WIDGET_CATALOG", () => {
  it("offers exactly the widget types the API accepts", () => {
    expect(WIDGET_CATALOG.map((w) => w.type).sort()).toEqual(
      [...REPORT_WIDGET_TYPES].sort(),
    );
  });

  it("lists each widget type once", () => {
    const types = WIDGET_CATALOG.map((w) => w.type);
    expect(new Set(types).size).toBe(types.length);
  });

  it("gives every widget a label, description, icon and a valid group", () => {
    const groups = new Set([
      "Card furniture",
      "Student & academics",
      "Summary",
      "Comments & sign-off",
      "Custom",
    ]);
    for (const def of WIDGET_CATALOG) {
      expect(def.label.trim()).not.toBe("");
      expect(def.description.trim()).not.toBe("");
      expect(def.icon).toBeTruthy();
      expect(groups.has(def.group)).toBe(true);
    }
  });

  it("marks identity blocks unique, so a card can only carry one", () => {
    const unique = WIDGET_CATALOG.filter((w) => w.unique).map((w) => w.type);
    // The blocks that must not appear twice on one card.
    expect(unique).toContain("header");
    expect(unique).toContain("student_info");
    expect(unique).toContain("cognitive_domain");
  });

  it("only exposes field kinds the inspector knows how to render", () => {
    const kinds = new Set(["text", "textarea", "boolean", "number", "select"]);
    for (const def of WIDGET_CATALOG) {
      for (const field of def.fields ?? []) {
        expect(kinds.has(field.kind)).toBe(true);
        expect(field.key.trim()).not.toBe("");
        if (field.kind === "select") expect(field.options?.length ?? 0).toBeGreaterThan(0);
      }
    }
  });

  it("gives every field a key that is present in the widget's defaults where one exists", () => {
    for (const def of WIDGET_CATALOG) {
      if (!def.defaults) continue;
      for (const field of def.fields ?? []) {
        // Number/textarea fields may legitimately default to nothing (e.g. body).
        if (field.kind === "textarea") continue;
        expect(Object.keys(def.defaults)).toContain(field.key);
      }
    }
  });
});

describe("widgetDef", () => {
  it("returns the catalog entry for a known type", () => {
    expect(widgetDef("header")).toBe(WIDGET_CATALOG.find((w) => w.type === "header"));
  });

  it("degrades to a labelled placeholder for an unknown type", () => {
    // Simulates the catalog and the API contract drifting apart: a school's card
    // must still render rather than crash on load.
    const def = widgetDef("mystery_block" as never);
    expect(def.label).toBe("mystery_block");
    expect(def.group).toBe("Custom");
  });
});

describe("widgetTitle", () => {
  it("prefers the widget's own heading", () => {
    expect(
      widgetTitle({ id: "g", type: "grading_key", props: { title: "Our Key" }, hidden: false }),
    ).toBe("Our Key");
  });

  it("trims a heading that is only whitespace", () => {
    expect(
      widgetTitle({ id: "g", type: "grading_key", props: { title: "   " }, hidden: false }),
    ).toBe("Grading key");
  });
});

describe("newWidget", () => {
  it("starts a widget from the catalog defaults and shows it", () => {
    const w = newWidget("header");
    expect(w.type).toBe("header");
    expect(w.hidden).toBe(false);
    expect(w.props).toEqual(widgetDef("header").defaults);
    // A copy, not the catalog's own object.
    expect(w.props).not.toBe(widgetDef("header").defaults);
  });

  it("gives every instance a unique id", () => {
    const ids = new Set(Array.from({ length: 50 }, () => newWidget("spacer").id));
    expect(ids.size).toBe(50);
    for (const id of ids) expect(id.startsWith("spacer-")).toBe(true);
  });

  it("carries each widget's own defaults, not the header's", () => {
    expect(newWidget("spacer").props).toEqual({ height: 12 });
    expect(newWidget("grading_key").props).toEqual({ title: "Grading Key" });
  });
});

describe("prop", () => {
  const widget = (props: Record<string, unknown>) =>
    ({ id: "w", type: "custom_text", props, hidden: false }) as const;

  it("returns the stored value when its type matches the fallback", () => {
    expect(prop(widget({ title: "Notice" }), "title", "Report Card")).toBe("Notice");
    expect(prop(widget({ show_logo: false }), "show_logo", true)).toBe(false);
    expect(prop(widget({ limit: 4 }), "limit", 6)).toBe(4);
  });

  it("falls back when the setting is missing", () => {
    expect(prop(widget({}), "title", "Report Card")).toBe("Report Card");
    expect(prop(widget({}), "show_logo", true)).toBe(true);
    expect(prop(widget({}), "limit", 6)).toBe(6);
  });

  it("coerces numeric strings — JSONB and <input> both hand numbers back as text", () => {
    expect(prop(widget({ limit: "4" }), "limit", 6)).toBe(4);
    expect(prop(widget({ limit: "" }), "limit", 6)).toBe(6);
    expect(prop(widget({ limit: "not a number" }), "limit", 6)).toBe(6);
  });

  it('coerces the strings "true"/"false" for boolean settings', () => {
    expect(prop(widget({ show_dob: "true" }), "show_dob", false)).toBe(true);
    expect(prop(widget({ show_dob: "false" }), "show_dob", true)).toBe(false);
  });

  it("ignores a value of the wrong type rather than leaking it into the card", () => {
    expect(prop(widget({ title: 42 }), "title", "Report Card")).toBe("Report Card");
    expect(prop(widget({ show_logo: "yes" }), "show_logo", true)).toBe(true);
  });

  it("tolerates a widget with no props object at all", () => {
    // Old or hand-edited rows can arrive without a props bag.
    const bare = { id: "w", type: "spacer", hidden: false } as ReportWidget;
    expect(prop(bare, "height", 12)).toBe(12);
  });
});

describe("propText", () => {
  it("trims the stored text", () => {
    expect(propText({ id: "w", type: "next_term", props: { label: "  Next Term  " }, hidden: false }, "label", "Next Term Begins")).toBe("Next Term");
  });

  it("falls back when the stored text is blank", () => {
    expect(propText({ id: "w", type: "next_term", props: { label: "   " }, hidden: false }, "label", "Next Term Begins")).toBe("Next Term Begins");
  });
});

describe("DEFAULT_LAYOUT", () => {
  it("is a valid, non-empty card", () => {
    expect(DEFAULT_LAYOUT.version).toBe(1);
    expect(REPORT_THEMES).toContain(DEFAULT_LAYOUT.theme);
    expect(DEFAULT_LAYOUT.widgets.length).toBeGreaterThan(0);
  });

  it("carries one of every block the built-in card needs", () => {
    const types = DEFAULT_LAYOUT.widgets.map((w) => w.type);
    for (const type of ["header", "student_info", "cognitive_domain", "psychomotor_domain"]) {
      expect(types).toContain(type);
    }
  });

  it("respects the unique rule — no block appears twice", () => {
    const types = DEFAULT_LAYOUT.widgets.map((w) => w.type);
    expect(new Set(types).size).toBe(types.length);
  });

  it("keeps the half-width pair the old hardcoded card had", () => {
    const cognitive = DEFAULT_LAYOUT.widgets.find((w) => w.type === "cognitive_domain");
    const psychomotor = DEFAULT_LAYOUT.widgets.find((w) => w.type === "psychomotor_domain");
    expect(prop<string>(cognitive!, "width", "full")).toBe("half");
    expect(prop<string>(psychomotor!, "width", "full")).toBe("half");
  });
});

describe("emptyLayout / cloneLayout", () => {
  it("defaults to the classic theme", () => {
    expect(emptyLayout().theme).toBe("classic");
  });

  it("accepts a theme and starts from the built-in card", () => {
    const layout = emptyLayout("elegant");
    expect(layout.theme).toBe("elegant");
    expect(layout.widgets.length).toBe(DEFAULT_LAYOUT.widgets.length);
  });

  it("deep-copies, so editing the clone never mutates the original", () => {
    const original = cloneLayout(DEFAULT_LAYOUT);
    const copy = cloneLayout(original);
    copy.widgets[0].props = { title: "Changed" };
    copy.widgets.pop();
    expect(original.widgets[0].props?.title).not.toBe("Changed");
    expect(original.widgets.length).toBe(DEFAULT_LAYOUT.widgets.length);
  });

  it("tolerates a layout missing its optional fields", () => {
    const clone = cloneLayout({ widgets: [] } as never);
    expect(clone.version).toBe(1);
    expect(clone.theme).toBe("classic");
    expect(clone.widgets).toEqual([]);
  });
});

describe("isKnownTheme / themeClass", () => {
  it("recognises every catalogued theme", () => {
    for (const theme of REPORT_THEMES) expect(isKnownTheme(theme)).toBe(true);
  });

  it("rejects anything else", () => {
    for (const value of ["", "Classic", "neon", 42, null, undefined]) {
      expect(isKnownTheme(value)).toBe(false);
    }
  });

  it("maps a theme onto its stylesheet class", () => {
    expect(themeClass("modern")).toBe("rc-template-modern");
  });
});

describe("moveWidget", () => {
  const layout = () =>
    cloneLayout({
      version: 1,
      theme: "classic",
      widgets: ["a", "b", "c"].map((id) => ({
        id,
        type: "spacer" as const,
        props: {},
        hidden: false,
      })),
    });

  const ids = (l: ReturnType<typeof layout>) => l.widgets.map((w) => w.id);

  it("moves a widget down", () => {
    expect(ids(moveWidget(layout(), 0, 2))).toEqual(["b", "c", "a"]);
  });

  it("moves a widget up", () => {
    expect(ids(moveWidget(layout(), 2, 0))).toEqual(["c", "a", "b"]);
  });

  it("clamps a target past the end instead of dropping the block", () => {
    expect(ids(moveWidget(layout(), 0, 99))).toEqual(["b", "c", "a"]);
  });

  it("clamps a negative target to the top", () => {
    expect(ids(moveWidget(layout(), 2, -5))).toEqual(["c", "a", "b"]);
  });

  it("returns the same layout for an out-of-range source or a no-op move", () => {
    const l = layout();
    expect(moveWidget(l, 9, 0)).toBe(l);
    expect(moveWidget(l, -1, 0)).toBe(l);
    expect(moveWidget(l, 1, 1)).toBe(l);
  });

  it("never mutates the layout it was handed", () => {
    const l = layout();
    moveWidget(l, 0, 2);
    expect(ids(l)).toEqual(["a", "b", "c"]);
  });
});

describe("removeWidget", () => {
  it("removes the block with that id and leaves the rest in order", () => {
    const layout = cloneLayout(DEFAULT_LAYOUT);
    const target = layout.widgets[1];
    const next = removeWidget(layout, target.id);
    expect(next.widgets.map((w) => w.id)).not.toContain(target.id);
    expect(next.widgets.length).toBe(layout.widgets.length - 1);
  });

  it("is a no-op for an unknown id", () => {
    const layout = cloneLayout(DEFAULT_LAYOUT);
    const next = removeWidget(layout, "does-not-exist");
    expect(next.widgets.map((w) => w.id)).toEqual(layout.widgets.map((w) => w.id));
  });

  it("never mutates the source layout", () => {
    const layout = cloneLayout(DEFAULT_LAYOUT);
    const before = layout.widgets.length;
    removeWidget(layout, layout.widgets[0].id);
    expect(layout.widgets.length).toBe(before);
  });
});

describe("updateWidget", () => {
  it("patches only the named block", () => {
    const layout = cloneLayout(DEFAULT_LAYOUT);
    const target = layout.widgets[0];
    const next = updateWidget(layout, target.id, { hidden: true });
    expect(next.widgets.find((w) => w.id === target.id)?.hidden).toBe(true);
    expect(next.widgets.filter((w) => w.id !== target.id).every((w) => !w.hidden)).toBe(true);
  });

  it("keeps the block's id and type", () => {
    const layout = cloneLayout(DEFAULT_LAYOUT);
    const target = layout.widgets[0];
    const next = updateWidget(layout, target.id, { hidden: true });
    const patched = next.widgets.find((w) => w.id === target.id);
    expect(patched?.type).toBe(target.type);
  });

  it("leaves the source layout untouched", () => {
    const layout = cloneLayout(DEFAULT_LAYOUT);
    updateWidget(layout, layout.widgets[0].id, { hidden: true });
    expect(layout.widgets[0].hidden).toBe(false);
  });
});

describe("setWidgetProp", () => {
  it("writes one setting and preserves the others", () => {
    const layout = cloneLayout(DEFAULT_LAYOUT);
    const header = layout.widgets.find((w) => w.type === "header")!;
    const next = setWidgetProp(layout, header.id, "title", "End of Term Report");
    const updated = next.widgets.find((w) => w.id === header.id)!;
    expect(updated.props?.title).toBe("End of Term Report");
    // The untouched settings survive.
    expect(updated.props?.show_photo).toBe(true);
  });

  it("never mutates the source layout or widget", () => {
    const layout = cloneLayout(DEFAULT_LAYOUT);
    const header = layout.widgets.find((w) => w.type === "header")!;
    setWidgetProp(layout, header.id, "title", "Changed");
    expect(header.props?.title).toBe("Report Card");
  });

  it("is a no-op for an unknown id", () => {
    const layout = cloneLayout(DEFAULT_LAYOUT);
    const next = setWidgetProp(layout, "nope", "title", "x");
    expect(next.widgets.map((w) => w.props?.title)).toEqual(
      layout.widgets.map((w) => w.props?.title),
    );
  });
});

describe("canAdd", () => {
  it("blocks a second instance of a unique block", () => {
    const layout = cloneLayout(DEFAULT_LAYOUT);
    expect(canAdd(layout, "header")).toBe(false);
    expect(canAdd(layout, "cognitive_domain")).toBe(false);
  });

  it("allows a unique block the card does not have yet", () => {
    const layout = removeWidget(cloneLayout(DEFAULT_LAYOUT), "header");
    expect(canAdd(layout, "header")).toBe(true);
  });

  it("always allows a repeatable block", () => {
    const layout = cloneLayout(DEFAULT_LAYOUT);
    // The default card has no spacer/signatures/conduct blocks.
    expect(canAdd(layout, "spacer")).toBe(true);
    expect(canAdd(layout, "signatures")).toBe(true);
  });
});
