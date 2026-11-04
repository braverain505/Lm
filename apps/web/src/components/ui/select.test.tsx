import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./select";

/**
 * Radix only shows a selected label in a closed trigger when `SelectItem`
 * renders `SelectItemText` (it portals that text into `SelectValue`). Without
 * it the trigger stays blank until the menu is opened.
 */
describe("Select", () => {
  it("shows the selected item's label while closed", () => {
    const { container } = render(
      <Select value="male">
        <SelectTrigger>
          <SelectValue placeholder="Choose gender" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="unspecified">Not specified</SelectItem>
          <SelectItem value="male">Male</SelectItem>
          <SelectItem value="female">Female</SelectItem>
        </SelectContent>
      </Select>,
    );

    expect(container.textContent).toContain("Male");
    expect(container.textContent).not.toContain("Choose gender");
  });

  it("shows the placeholder while nothing is selected", () => {
    const { container } = render(
      <Select value="">
        <SelectTrigger>
          <SelectValue placeholder="Choose class" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="arm-1">JSS 1A</SelectItem>
        </SelectContent>
      </Select>,
    );

    expect(container.textContent).toContain("Choose class");
    expect(container.textContent).not.toContain("JSS 1A");
  });
});