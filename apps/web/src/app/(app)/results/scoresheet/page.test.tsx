import type { ScoreCard } from "@clearis/shared";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

/**
 * The read-back view is only worth having if it cannot become a second place to
 * type marks: a teacher opening "View Scoresheet" to check what landed must not
 * be able to change it by accident, and a half-entered grid must read as half
 * entered rather than as finished. So this drives the real page with the network
 * stubbed and asserts what it renders — including that it renders no fields.
 */

const { downloadCsv } = vi.hoisted(() => ({ downloadCsv: vi.fn() }));

vi.mock("@/lib/csv", async () => {
  const actual = await vi.importActual<typeof import("@/lib/csv")>("@/lib/csv");
  return { ...actual, downloadCsv };
});

const useScoreCard = vi.hoisted(() => vi.fn());

vi.mock("@/hooks/use-api", () => ({
  useSessions: () => ({ data: [{ id: "sess-1", name: "2026/2027", is_current: true }] }),
  useTerms: () => ({ data: [{ id: "term-1", name: "First Term", status: "open" }] }),
  useMyAssignments: () => ({
    data: [
      { arm_id: "arm-1", arm_name: "Primary 3A", subject_id: "sub-1", subject_name: "Mathematics", assignment_id: "asg-1" },
      { arm_id: "arm-1", arm_name: "Primary 3A", subject_id: "sub-2", subject_name: "Nigerian History", assignment_id: "asg-2" },
      { arm_id: "arm-9", arm_name: "Primary 5", subject_id: "sub-3", subject_name: "English Studies", assignment_id: "asg-3" },
    ],
  }),
  useScoreCard,
}));

import { ToastProvider } from "@/components/toast";

import ViewScoresheetPage from "./page";

const MATHS: ScoreCard = {
  arm: { id: "arm-1", full_name: "Primary 3A" },
  subject: { id: "sub-1", name: "Mathematics" },
  term: { id: "term-1", name: "First Term" },
  components: [
    { id: "comp-1", name: "1st CA", max_score: 20, weight: 40 },
    { id: "comp-2", name: "2nd CA", max_score: 20, weight: 60 },
  ],
  students: [
    {
      enrollment_id: "enr-1",
      student_id: "stu-1",
      admission_no: "ECWA-2026-0169",
      full_name: "Victor Clinton",
      scores: { "comp-1": 18, "comp-2": null },
      total: 36,
      grade_letter: "D",
      status: "draft",
    },
    {
      enrollment_id: "enr-2",
      student_id: "stu-2",
      admission_no: "ECWA-2026-0170",
      full_name: "Holiness Andekuba",
      scores: { "comp-1": null, "comp-2": null },
      total: null,
      grade_letter: null,
      status: "draft",
    },
  ],
};

const HISTORY: ScoreCard = {
  ...MATHS,
  subject: { id: "sub-2", name: "Nigerian History" },
  components: [{ id: "comp-1", name: "Exam", max_score: 60, weight: 100 }],
  students: [
    {
      ...MATHS.students[0],
      enrollment_id: "enr-3",
      admission_no: "ECWA-2026-0171",
      full_name: "Faith Godwin Agbe",
      scores: { "comp-1": 48 },
      total: 80,
      grade_letter: "A",
    },
  ],
};

const cardFor = (subjectId: string): ScoreCard =>
  subjectId === "sub-1" ? MATHS : { ...HISTORY };

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <ViewScoresheetPage />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** Choose the teacher's class, which is what opens the sheets. */
async function chooseClass(name = "Primary 3A") {
  const user = userEvent.setup();
  await user.selectOptions(screen.getByLabelText("Class"), screen.getByRole("option", { name }));
  return user;
}

describe("View Scoresheet — the teacher's own marks, read back", () => {
  beforeEach(() => {
    downloadCsv.mockClear();
    useScoreCard.mockReset();
    useScoreCard.mockImplementation((_armId: string, subjectId: string) => ({
      data: cardFor(subjectId),
      isLoading: false,
      error: null,
    }));
  });

  it("lists each assigned class once, however many subjects are taught there", () => {
    renderPage();

    const classes = screen
      .getByLabelText("Class")
      .querySelectorAll("option");
    expect(Array.from(classes).map((option) => option.textContent)).toEqual([
      "Choose class...",
      "Primary 3A",
      "Primary 5",
    ]);
  });

  it("shows the saved marks for each subject the teacher teaches that class", async () => {
    renderPage();
    await chooseClass();

    expect(await screen.findByText("Mathematics")).toBeInTheDocument();
    expect(screen.getByText("Nigerian History")).toBeInTheDocument();
    // The teacher's other class is not on this sheet.
    expect(screen.queryByText("English Studies")).not.toBeInTheDocument();
  });

  it("renders no field to type in — the record is not editable from here", async () => {
    renderPage();
    await chooseClass();
    await screen.findByText("Mathematics");

    expect(screen.queryAllByRole("spinbutton")).toHaveLength(0);
    expect(screen.queryAllByRole("textbox")).toHaveLength(0);
    // The only controls are the term, the class and the download buttons.
    expect(screen.getAllByRole("combobox")).toHaveLength(2);
  });

  it("prints an unentered mark as a dash and the saved total as it stands", async () => {
    renderPage();
    await chooseClass();
    await screen.findByText("Victor Clinton");

    // One CA marked, the other not: 18 on screen, a dash for the blank.
    expect(screen.getByText("18")).toBeInTheDocument();
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
    expect(screen.getByText("36")).toBeInTheDocument();
    // The pupil with nothing entered has no total either.
    expect(screen.getByText("Holiness Andekuba")).toBeInTheDocument();
  });

  it("says how much of the grid is filled in rather than implying it is complete", async () => {
    renderPage();
    await chooseClass();

    expect(await screen.findByText(/1 of 2 pupils marked/)).toBeInTheDocument();
    expect(screen.getByText("In progress")).toBeInTheDocument();
  });

  it("asks the API for the chosen term and each subject of the chosen class", async () => {
    renderPage();
    await chooseClass();
    await screen.findByText("Mathematics");

    // The grid is asked for in the school's chosen order, surname by default.
    await waitFor(() =>
      expect(useScoreCard).toHaveBeenCalledWith("arm-1", "sub-1", "term-1", "surname"),
    );
    expect(useScoreCard).toHaveBeenCalledWith("arm-1", "sub-2", "term-1", "surname");
    // Nothing is requested for a class the teacher did not choose.
    expect(useScoreCard).not.toHaveBeenCalledWith("arm-9", "sub-3", "term-1", "surname");
  });

  it("downloads the saved marks, with blanks left blank", async () => {
    renderPage();
    const user = await chooseClass();
    await screen.findByText("Victor Clinton");

    await user.click(screen.getAllByRole("button", { name: /spreadsheet/i })[0]);

    expect(downloadCsv).toHaveBeenCalledTimes(1);
    const [filename, rows] = downloadCsv.mock.calls[0];
    expect(filename).toBe("scoresheet-primary-3a-mathematics-first-term.csv");
    expect(rows).toEqual([
      ["Student", "Admission no", "1st CA (/20)", "2nd CA (/20)", "Total", "Grade"],
      ["Victor Clinton", "ECWA-2026-0169", "18", "", 36, "D"],
      ["Holiness Andekuba", "ECWA-2026-0170", "", "", "", ""],
    ]);
  });
});
