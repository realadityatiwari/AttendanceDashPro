import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { SubjectAttendanceGrid } from "./SubjectAttendanceGrid";
import type { SubjectResponse } from "@/types/api";
import { SubjectCategory } from "@/types/api";

/**
 * 25.UX-4 regression coverage: the Subjects Overview grid distinguishes
 * "no enrollment at all" from "enrolled, but nothing attendance-applicable",
 * and never renders a silent blank grid for the latter.
 */

const subjectState = { subjects: undefined as SubjectResponse[] | undefined };
const overviewState = { overview: { subjects: [] } as { subjects: unknown[] } };

vi.mock("@/hooks/useApi", () => ({
  useSubjects: () => ({ ...subjectState, isLoading: false, isError: false, mutate: vi.fn() }),
  useAnalyticsOverview: () => ({ ...overviewState, isLoading: false, isError: false, mutate: vi.fn() }),
}));

vi.mock("./SubjectAttendanceCard", () => ({
  SubjectAttendanceCard: ({ subject }: { subject: SubjectResponse }) => (
    <div data-testid="subject-card">{subject.code}</div>
  ),
}));

const subject = (code: string, attendanceApplicable: boolean): SubjectResponse => ({
  id: code,
  code,
  name: `Subject ${code}`,
  tag: null,
  category: SubjectCategory.THEORY,
  quiz_applicable: true,
  attendance_applicable: attendanceApplicable,
});

describe("25.UX-4: SubjectAttendanceGrid state coverage", () => {
  it("renders one card per attendance-applicable subject", () => {
    subjectState.subjects = [subject("CSE301", true), subject("NON01", false)];
    render(<SubjectAttendanceGrid />);
    expect(screen.getAllByTestId("subject-card")).toHaveLength(1);
    expect(screen.getByText("CSE301")).toBeInTheDocument();
  });

  it("renders an explicit empty state when no subject is attendance-applicable", () => {
    subjectState.subjects = [subject("NON01", false)];
    render(<SubjectAttendanceGrid />);
    expect(screen.queryByTestId("subject-card")).not.toBeInTheDocument();
    expect(screen.getByText("No attendance to track")).toBeInTheDocument();
  });

  it("keeps the no-enrollment empty state distinct", () => {
    subjectState.subjects = [];
    render(<SubjectAttendanceGrid />);
    expect(screen.getByText("No subjects found")).toBeInTheDocument();
  });
});
