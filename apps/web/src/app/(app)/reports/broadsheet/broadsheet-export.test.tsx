import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

/**
 * The row shape is covered by lib/exports.test.ts. What that cannot catch is the
 * wiring: whether the exam office's Download button is actually reachable on the
 * page, actually reaches the handler, and hands over the class, term and rows
 * that were on screen. So this drives the real page — the permission gate, the
 * term/class pickers and the query — with the network and the download boundary
 * stubbed.
 */

// vi.mock is hoisted above these declarations, so the spy has to be hoisted with it.
const { downloadCsv } = vi.hoisted(() => ({ downloadCsv: vi.fn() }));

vi.mock("@/lib/csv", async () => {
  const actual = await vi.importActual<typeof import("@/lib/csv")>("@/lib/csv");
  return { ...actual, downloadCsv };
});

vi.mock("@/providers/auth-provider", () => ({
  useAuth: () => ({
    activeSchool: { permissions: ["results.report_card"] },
  }),
}));

vi.mock("@/hooks/use-api", () => ({
  useActiveSchoolId: () => "school-1",
  useSessions: () => ({ data: [{ id: "sess-1", name: "2025/2026", is_current: true }] }),
  useTerms: () => ({ data: [{ id: "term-1", name: "First Term" }] }),
  useArms: () => ({ data: [{ id: "arm-1", full_name: "JSS 2B" }] }),
}));

vi.mock("@clearis/shared", async () => {
  const actual = await vi.importActual<typeof import("@clearis/shared")>("@clearis/shared");
  return { ...actual, api: { schoolFetch: vi.fn() } };
});

import { api } from "@clearis/shared";

import BroadsheetPage from "./page";

const CARD = {
  student: { full_name: "Amaka Okafor", admission_no: "BFA/2024/018" },
  enrollment_id: "enr-1",
  class_arm: { id: "arm-1", full_name: "JSS 2B" },
  term: { id: "term-1", name: "First Term" },
  subjects: [
    { subject_id: "m", subject_name: "Mathematics", total: 93 },
    { subject_id: "e", subject_name: "English Language", total: 74 },
  ],
  summary: { average: 83.5 },
};

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <BroadsheetPage />
    </QueryClientProvider>,
  );
}

describe("Broadsheet — downloading the sheet", () => {
  beforeEach(() => {
    downloadCsv.mockClear();
    vi.mocked(api.schoolFetch).mockReset();
    vi.mocked(api.schoolFetch).mockResolvedValue([CARD] as never);
  });

  it("serves the button but keeps it disabled until a class and term are chosen", () => {
    renderPage();

    const button = screen.getByRole("button", { name: /download spreadsheet/i });
    expect(button).toBeDisabled();
  });

  it("hands the chosen class and term's grid to the CSV writer", async () => {
    const user = userEvent.setup();
    renderPage();

    // The two bare selects on this page are term first, then class.
    const selects = screen.getAllByRole("combobox");
    await user.selectOptions(selects[0], "term-1");
    await user.selectOptions(selects[1], "arm-1");

    // The grid renders from the fetched cards.
    await screen.findByText("Amaka Okafor");

    const button = screen.getByRole("button", { name: /download spreadsheet/i });
    await waitFor(() => expect(button).toBeEnabled());
    await user.click(button);

    expect(downloadCsv).toHaveBeenCalledTimes(1);
    const [filename, rows] = downloadCsv.mock.calls[0];
    expect(filename).toBe("broadsheet-jss-2b-first-term.csv");
    expect(rows).toEqual([
      ["Student", "Admission no", "Mathematics", "English Language", "Average"],
      ["Amaka Okafor", "BFA/2024/018", 93, 74, 83.5],
    ]);
  });

  it("asks the API for the class and term the user picked", async () => {
    const user = userEvent.setup();
    renderPage();

    const selects = screen.getAllByRole("combobox");
    await user.selectOptions(selects[0], "term-1");
    await user.selectOptions(selects[1], "arm-1");
    await screen.findByText("Amaka Okafor");

    expect(api.schoolFetch).toHaveBeenCalledWith(
      "school-1",
      "/results/broadsheet?arm_id=arm-1&term_id=term-1",
    );
  });
});
