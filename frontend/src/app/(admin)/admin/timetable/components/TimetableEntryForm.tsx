"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useAdminSessions, useAdminSemesters, useAdminSections, useAdminSubsectionsStructure, useAdminSubjects } from "@/hooks/useApi";
import { ClassType, ElectiveSlot, TimetableConflict, TimetableConflictResponse } from "@/types/api";

const DAY_OPTIONS = [
  { value: "0", label: "Monday" },
  { value: "1", label: "Tuesday" },
  { value: "2", label: "Wednesday" },
  { value: "3", label: "Thursday" },
  { value: "4", label: "Friday" },
  { value: "5", label: "Saturday" },
  { value: "6", label: "Sunday" },
];

const DAY_LABELS = DAY_OPTIONS.map((o) => o.label);

const CLASS_TYPE_OPTIONS = [
  { value: ClassType.LECTURE, label: "Lecture" },
  { value: ClassType.TUTORIAL, label: "Tutorial" },
  { value: ClassType.PRACTICAL, label: "Practical" },
];

const ELEC_OPTIONS = [
  { value: "", label: "Common subject" },
  { value: ElectiveSlot.ELECTIVE_I, label: "Department Elective-I" },
  { value: ElectiveSlot.ELECTIVE_II, label: "Department Elective-II" },
];

export interface FormValues {
  section_id: string;
  subsection_id: string;
  day_of_week: number;
  start_time: string;
  end_time: string;
  subject_id: string;
  class_type: ClassType;
  room: string;
  elective_slot: string;
  is_active: boolean;
  sort_order: string;
}

export interface TimetableEntryFormProps {
  initial?: Partial<FormValues>;
  isGlobal: boolean;
  /** Server-derived sections visible to the acting admin (from the scoped
   *  timetable list). Used for non-global admins, who cannot call the
   *  HEAD-gated structure endpoints. */
  scopedSections?: { id: string; name: string }[];
  isSubmitting: boolean;
  onSubmit: (values: FormValues) => Promise<void>;
  onCancel: () => void;
  submitLabel?: string;
}

const selectClass =
  "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50";

export function TimetableEntryForm({
  initial = {},
  isGlobal,
  scopedSections = [],
  isSubmitting,
  onSubmit,
  onCancel,
  submitLabel = "Save",
}: TimetableEntryFormProps) {
  const { sessions } = useAdminSessions();
  const [sessionId, setSessionId] = useState("");
  const { semesters } = useAdminSemesters(sessionId || null);
  const [semesterId, setSemesterId] = useState("");
  const { sections } = useAdminSections(semesterId || null);
  const { subjects } = useAdminSubjects();

  const [sectionId, setSectionId] = useState(initial.section_id ?? "");
  const [subsectionId, setSubsectionId] = useState(initial.subsection_id ?? "");
  const { subsections } = useAdminSubsectionsStructure(sectionId || null);
  const [dayOfWeek, setDayOfWeek] = useState(String(initial.day_of_week ?? ""));
  const [startTime, setStartTime] = useState(initial.start_time ?? "");
  const [endTime, setEndTime] = useState(initial.end_time ?? "");
  const [subjectId, setSubjectId] = useState(initial.subject_id ?? "");
  const [classType, setClassType] = useState(initial.class_type ?? "");
  const [room, setRoom] = useState(initial.room ?? "");
  const [electiveSlot, setElectiveSlot] = useState(initial.elective_slot ?? "");
  const [isActive, setIsActive] = useState(initial.is_active ?? true);
  const [sortOrder, setSortOrder] = useState(initial.sort_order ?? "");
  const [error, setError] = useState<{ message: string; status?: number; conflicts?: TimetableConflict[] } | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sectionId || !dayOfWeek || !startTime || !endTime || !subjectId || !classType) {
      setError({ message: "Section, day, start/end time, subject, and class type are required" });
      return;
    }
    if (endTime <= startTime) {
      setError({ message: "End time must be after start time" });
      return;
    }
    setError(null);
    try {
      await onSubmit({
        section_id: sectionId,
        subsection_id: subsectionId,
        day_of_week: parseInt(dayOfWeek, 10),
        start_time: startTime,
        end_time: endTime,
        subject_id: subjectId,
        class_type: classType as ClassType,
        room,
        elective_slot: electiveSlot,
        is_active: isActive,
        sort_order: sortOrder,
      });
    } catch (err: unknown) {
      const e2 = err as Error & { status?: number; body?: TimetableConflictResponse };
      const structuredDetail = e2.body?.detail;
      setError({
        message: e2.message || "Operation failed",
        status: e2.status,
        conflicts: structuredDetail && typeof structuredDetail === "object"
          ? structuredDetail.conflicts
          : undefined,
      });
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && (
        <div
          className={`rounded-md border p-2 text-sm ${
            error.status === 409
              ? "border-warning/40 bg-warning/10 text-warning"
              : "border-destructive/30 bg-destructive/10 text-destructive"
          }`}
        >
          {error.status === 409 && (
            <p className="mb-1 font-medium">Schedule conflict — the backend rejected this entry.</p>
          )}
          <p>{error.message}</p>
          {error.conflicts && error.conflicts.length > 0 && (
            <ul className="mt-1 space-y-0.5">
              {error.conflicts.map((c, i) => (
                <li key={i} className="text-xs">
                  &#8226; {c.subject_code} ({c.section_name}) on {DAY_LABELS[c.day_of_week]} {c.start_time.slice(0, 5)}&ndash;{c.end_time.slice(0, 5)}
                  {c.subsection_name ? ` \u00B7 ${c.subsection_name}` : ""}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {isGlobal && (
        <>
          <div className="space-y-2">
            <label className="text-sm font-medium">Academic session</label>
            <select className={selectClass} value={sessionId} onChange={(e) => { setSessionId(e.target.value); setSemesterId(""); setSectionId(""); }}>
              <option value="">Select a session</option>
              {(sessions ?? []).map((s) => (
                <option key={s.id} value={s.id}>{s.name}{s.is_active ? " (active)" : ""}</option>
              ))}
            </select>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Semester</label>
            <select className={selectClass} value={semesterId} onChange={(e) => { setSemesterId(e.target.value); setSectionId(""); }} disabled={!sessionId}>
              <option value="">Select a semester</option>
              {(semesters ?? []).map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </div>
        </>
      )}

      <div className="space-y-2">
        <label className="text-sm font-medium">Section</label>
        {isGlobal ? (
          <select className={selectClass} value={sectionId} onChange={(e) => { setSectionId(e.target.value); setSubsectionId(""); }} disabled={!semesterId}>
            <option value="">Select a section</option>
            {(sections ?? []).map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        ) : scopedSections.length > 0 ? (
          <select className={selectClass} value={sectionId} onChange={(e) => { setSectionId(e.target.value); setSubsectionId(""); }}>
            <option value="">Select a section</option>
            {scopedSections.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        ) : (
          <p className="text-sm text-muted-foreground">Your assigned section</p>
        )}
      </div>

      <div className="space-y-2">
        <label className="text-sm font-medium">Subsection (optional)</label>
        <select className={selectClass} value={subsectionId} onChange={(e) => setSubsectionId(e.target.value)} disabled={!sectionId}>
          <option value="">Section-wide entry</option>
          {(subsections ?? []).map((s) => (
            <option key={s.id} value={s.id}>{s.name}</option>
          ))}
        </select>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <label className="text-sm font-medium">Day</label>
          <select className={selectClass} value={dayOfWeek} onChange={(e) => setDayOfWeek(e.target.value)}>
            <option value="">Select day</option>
            {DAY_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
        <div className="space-y-2">
          <label className="text-sm font-medium">Class type</label>
          <select className={selectClass} value={classType} onChange={(e) => setClassType(e.target.value)}>
            <option value="">Select type</option>
            {CLASS_TYPE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <label className="text-sm font-medium">Start time</label>
          <Input type="time" value={startTime} onChange={(e) => setStartTime(e.target.value)} />
        </div>
        <div className="space-y-2">
          <label className="text-sm font-medium">End time</label>
          <Input type="time" value={endTime} onChange={(e) => setEndTime(e.target.value)} />
        </div>
      </div>

      <div className="space-y-2">
        <label className="text-sm font-medium">Subject</label>
        <select className={selectClass} value={subjectId} onChange={(e) => setSubjectId(e.target.value)}>
          <option value="">Select subject</option>
          {(subjects?.items ?? []).map((s) => (
            <option key={s.id} value={s.id}>{s.code} — {s.name}</option>
          ))}
        </select>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <label className="text-sm font-medium">Elective slot</label>
          <select className={selectClass} value={electiveSlot} onChange={(e) => setElectiveSlot(e.target.value)}>
            {ELEC_OPTIONS.map((o) => (
              <option key={o.label} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
        <div className="space-y-2">
          <label className="text-sm font-medium">Room</label>
          <Input placeholder="e.g. 201" value={room} onChange={(e) => setRoom(e.target.value)} maxLength={100} />
        </div>
      </div>

      <div className="flex items-center gap-4">
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />
          Active
        </label>
        <div className="flex-1" />
        <label className="flex items-center gap-2 text-sm">
          <span className="text-muted-foreground">Sort order:</span>
          <Input type="number" className="w-20 h-8" value={sortOrder} onChange={(e) => setSortOrder(e.target.value)} />
        </label>
      </div>

      <div className="flex justify-end gap-2 pt-2">
        <Button type="button" variant="outline" onClick={onCancel} disabled={isSubmitting}>Cancel</Button>
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          {submitLabel}
        </Button>
      </div>
    </form>
  );
}