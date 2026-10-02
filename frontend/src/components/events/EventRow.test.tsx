import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { EventRow } from "./EventRow";
import { ClassType, EventType, type AcademicEventResponse } from "@/types/api";

/**
 * UIA-032 regression coverage: the round date tile already carries the start
 * date, so a single-day event no longer repeats it as full date text; a
 * multi-day event still renders the range (the tile alone cannot express the
 * end date).
 */

function makeEvent(overrides: Partial<AcademicEventResponse> = {}): AcademicEventResponse {
  return {
    id: "e1",
    event_type: EventType.QUIZ_DAY,
    start_date: "2026-10-05",
    end_date: "2026-10-05",
    subject_id: null,
    elective_slot: null,
    resolved_subject_id: null,
    resolved_subject_code: null,
    resolved_subject_name: null,
    class_type: null,
    is_working_day: null,
    substitution_schedule_override: null,
    note: null,
    active: true,
    ...overrides,
  };
}

describe("UIA-032: EventRow date presentation", () => {
  it("shows the date tile without repeating the full date for a single-day event", () => {
    render(<EventRow event={makeEvent()} />);

    // Tile: month + day (formatShortDate emits an uppercase month).
    expect(screen.getByText("OCT")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    // No second, full-date rendering of the same day.
    expect(screen.queryByText("5 Oct 2026")).not.toBeInTheDocument();
  });

  it("keeps the full date text for multi-day ranges", () => {
    render(
      <EventRow
        event={makeEvent({ start_date: "2026-10-05", end_date: "2026-10-09" })}
      />
    );

    expect(screen.getByText("5 Oct 2026 – 9 Oct 2026")).toBeInTheDocument();
  });

  it("still renders the event title and the calendar link", () => {
    render(<EventRow event={makeEvent({ class_type: ClassType.LECTURE })} />);
    expect(screen.getByRole("link", { name: /open the calendar/i })).toHaveAttribute(
      "href",
      "/calendar"
    );
  });
});
