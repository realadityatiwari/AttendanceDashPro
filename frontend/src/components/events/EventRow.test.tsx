import { describe, it, expect, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { EventRow } from "./EventRow";
import { EventFormDialog } from "./EventFormDialog";
import { EVENT_TYPE_RULES } from "./eventRules";
import { ClassType, EventType, type AcademicEventResponse } from "@/types/api";

const mockCreateEvent = vi.fn();
const mockUpdateEvent = vi.fn();

vi.mock("@/hooks/useApi", () => ({
  useSubjects: () => ({ subjects: [], isLoading: false, isError: false }),
  useTimetable: () => ({ timetable: [], isLoading: false, isError: false }),
  useEventMutations: () => ({
    createEvent: mockCreateEvent,
    updateEvent: mockUpdateEvent,
  }),
  useOccurrenceOptions: (forDate: string | null, eventType?: EventType | null) => ({
    options:
      forDate && eventType === EventType.LAB_CANCELLED
        ? [
            {
              timetable_entry_id: "entry-14",
              subject_id: "sub-552",
              subject_code: "BCS-552",
              subject_name: "Web Technology Lab",
              class_type: ClassType.PRACTICAL,
              start_time: "14:00:00",
              end_time: "16:00:00",
              section_id: "sec-1",
              subsection_id: null,
              subsection_name: null,
              elective_slot: null,
              is_slot_anchor: false,
              elective_subjects: [],
              display_label: "BCS-552 — Web Technology Lab",
            },
          ]
        : [],
    dayInfo:
      forDate && eventType === EventType.LAB_CANCELLED
        ? {
            date: forDate,
            schedule_day: "THURSDAY",
            is_working_day: true,
            non_working_reason: null,
          }
        : undefined,
    isLoading: false,
    isError: false,
    mutate: vi.fn(),
  }),
}));

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
    timetable_entry_id: null,
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

  it("renders subject code and lab name without raw period time for a Lab Cancelled event", () => {
    render(
      <EventRow
        event={makeEvent({
          event_type: EventType.LAB_CANCELLED,
          start_date: "2026-10-08",
          end_date: "2026-10-08",
          subject_id: "sub-552",
          resolved_subject_code: "BCS-552",
          resolved_subject_name: "Web Technology Lab",
          timetable_entry_id: "entry-14",
          occurrence_label: null,
          class_type: ClassType.PRACTICAL,
        })}
      />
    );

    expect(screen.getByText("Lab Cancelled")).toBeInTheDocument();
    expect(screen.getByText("Practical")).toBeInTheDocument();
    expect(screen.getByText("BCS-552")).toBeInTheDocument();
    expect(screen.getByText("Web Technology Lab")).toBeInTheDocument();
    expect(screen.queryByText(/14:00/)).not.toBeInTheDocument();
    expect(screen.queryByText("8 Oct 2026")).not.toBeInTheDocument();
  });
});

describe("Lab Cancelled single-day and occurrence semantics", () => {
  it("marks EventType.LAB_CANCELLED as singleDayOnly, requiresTimetableEntry, and Practical in EVENT_TYPE_RULES", () => {
    const rule = EVENT_TYPE_RULES[EventType.LAB_CANCELLED];
    expect(rule.singleDayOnly).toBe(true);
    expect(rule.requiresTimetableEntry).toBe(true);
    expect(rule.allowedClassTypes).toEqual([ClassType.PRACTICAL]);
  });

  it("hides Single day and Date range toggles and End date when Lab Cancelled is selected, and shows ONE canonical practical occurrence with only subject code + lab name and no time", async () => {
    mockCreateEvent.mockReset();
    mockCreateEvent.mockResolvedValue({ id: "created-1" });
    const onSaved = vi.fn();

    render(
      <EventFormDialog
        open={true}
        onOpenChange={vi.fn()}
        event={null}
        onSaved={onSaved}
        isAdmin={true}
      />
    );

    // Ordinary event type (Holiday initially): Single day & Date range toggles are present.
    expect(screen.getByText("Single day")).toBeInTheDocument();
    expect(screen.getByText("Date range")).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Date range"));
    expect(screen.getByLabelText("Start date")).toBeInTheDocument();
    expect(screen.getByLabelText("End date")).toBeInTheDocument();

    // Switch event type to Lab Cancelled.
    fireEvent.change(screen.getByLabelText("Event type"), {
      target: { value: EventType.LAB_CANCELLED },
    });

    // Both "Single day" and "Date range" radio toggles and "End date" are absent; "Single day only" is shown.
    expect(screen.queryByText("Single day")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Single day")).not.toBeInTheDocument();
    expect(screen.queryByText("Date range")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Date range")).not.toBeInTheDocument();
    expect(screen.queryByText("End date")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("End date")).not.toBeInTheDocument();
    expect(screen.getByText("Single day only")).toBeInTheDocument();

    // Single date picker and Scheduled occurrence selector remain present.
    expect(screen.getByLabelText("Event date")).toBeInTheDocument();
    expect(screen.getByLabelText("Scheduled occurrence")).toBeInTheDocument();

    // Set a single date so occurrence options load.
    fireEvent.change(screen.getByLabelText("Event date"), {
      target: { value: "2026-10-08" },
    });

    // Verify the selector shows ONE canonical option with ONLY "<Subject Code> — <Lab/Practical Name>" and no time.
    const occSelect = screen.getByLabelText("Scheduled occurrence") as HTMLSelectElement;
    const optionTexts = Array.from(occSelect.options).map((o) => o.textContent);
    expect(optionTexts).toEqual([
      "Select the class to cancel",
      "BCS-552 — Web Technology Lab",
    ]);
    expect(optionTexts.join(" ")).not.toMatch(/14:00|15:00|16:00/);

    // Select the canonical practical occurrence.
    fireEvent.change(occSelect, { target: { value: "entry-14" } });

    // Submit the form and verify single-day + exact canonical occurrence payload.
    fireEvent.click(screen.getByRole("button", { name: /create event/i }));

    await waitFor(() => {
      expect(mockCreateEvent).toHaveBeenCalledTimes(1);
    });
    const submitted = mockCreateEvent.mock.calls[0][0];
    expect(submitted.event_type).toBe(EventType.LAB_CANCELLED);
    expect(submitted.start_date).toBe("2026-10-08");
    expect(submitted.end_date).toBe("2026-10-08");
    expect(submitted.timetable_entry_id).toBe("entry-14");
    expect(submitted.subject_id).toBe("sub-552");
    expect(submitted.class_type).toBe(ClassType.PRACTICAL);
  });

  it("restores Single day and Date range toggles when switching from Lab Cancelled to an ordinary event type", () => {
    render(
      <EventFormDialog
        open={true}
        onOpenChange={vi.fn()}
        event={null}
        onSaved={vi.fn()}
        isAdmin={true}
      />
    );

    fireEvent.change(screen.getByLabelText("Event type"), {
      target: { value: EventType.LAB_CANCELLED },
    });
    expect(screen.queryByText("Single day")).not.toBeInTheDocument();
    expect(screen.queryByText("Date range")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Event type"), {
      target: { value: EventType.CLASS_CANCELLED },
    });
    expect(screen.getByText("Single day")).toBeInTheDocument();
    expect(screen.getByText("Date range")).toBeInTheDocument();
  });
});


