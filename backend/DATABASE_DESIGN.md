# Database Design (Phase 2)

> ## ⚠️ HISTORICAL DOCUMENT (superseded in part 2026-08-23)
>
> This document is the original Phase 2 relational design. The `User` entity no
> longer "links Firebase UID to application data": the `users.firebase_uid` column
> was removed by migration `e1f2a3b4c5d6` (Phase 14D). Firebase is retired; identity
> is `users.id` (UUID) with `users.roll_number` as the canonical login credential.
> The remainder of the entity/relationship design remains accurate. Preserved for
> historical provenance.

This document formalizes the relational database architecture for AttendanceDash Pro. It translates the observed existing domain (from Phase 1 schemas and JS behavior) into a normalized PostgreSQL schema using SQLAlchemy.

## 1. Entity List & Purpose

| Entity | Purpose |
| :--- | :--- |
| `User` | Represents the application user/student. Links Firebase UID to application data. |
| `AcademicSession` | Represents the broader academic year (e.g., "2026-27"). |
| `Semester` | Represents a specific term within a session (e.g., "V Semester"). |
| `Section` | Represents a cohort/group (e.g., "CSE-51"). Added to avoid hardcoding branch logic. |
| `Subject` | Represents an academic course (theory or lab). |
| `StudentEnrollment` | Maps a student to specific subjects (supports electives). |
| `TimetableEntry` | Represents the *recurring* weekly schedule definition. |
| `ClassSession` | Represents an *actual* occurrence of a class on a specific date. |
| `AttendanceRecord` | The explicit attendance fact for a student in a class session. |
| `AcademicEvent` | Calendar overrides (holidays, extra classes) affecting teaching days. |
| `QuizCycle` | Represents the overarching quiz period (e.g., "1st Quiz"). |
| `QuizSchedule` | Maps a subject to a quiz cycle with a specific date and status. |
| `EligibilityPolicy` | Stores the target thresholds (e.g., 70%, 75%) for a quiz cycle. |
| `LabExperiment` | Defines the required experiments for a lab subject. |
| `LabRecord` | Tracks a student's completion and signature status for an experiment. |

## 2. Relationships & Cardinality

- **User** (1) to **StudentEnrollment** (M)
- **Subject** (1) to **StudentEnrollment** (M)
- **Semester** (1) to **Subject** (M)
- **Session** (1) to **Semester** (M)
- **Section** (1) to **User** (M)
- **Subject** (1) to **TimetableEntry** (M)
- **Subject** (1) to **ClassSession** (M)
- **TimetableEntry** (1) to **ClassSession** (M)
- **ClassSession** (1) to **AttendanceRecord** (M)
- **User** (1) to **AttendanceRecord** (M)
- **QuizCycle** (1) to **EligibilityPolicy** (1)
- **QuizCycle** (1) to **QuizSchedule** (M)
- **Subject** (1) to **QuizSchedule** (M)
- **Subject** (1) to **LabExperiment** (M)
- **LabExperiment** (1) to **LabRecord** (M)
- **User** (1) to **LabRecord** (M)

## 3. Date/Time Strategy

- **Academic Date**: `DATE` (Python `datetime.date`). Used for `ClassSession.date`, `AcademicEvent.start_date`, `QuizSchedule.date`, `LabRecord.date_conducted`.
- **Exact Timestamp**: `TIMESTAMP WITH TIME ZONE` (Python `datetime.datetime(tzinfo)`). Used for audit fields (`created_at`, `updated_at`, `signed_on`).
- **Timezone**: All application logic and timestamps assume the institutional timezone of `Asia/Kolkata`.

## 4. Pending Attendance Strategy

- The `AttendanceRecord.status` column uses an Enum: `ATTENDED`, `MISSED`, `PENDING`.
- **Strategy**: To avoid pre-generating thousands of `PENDING` records for the whole semester, `AttendanceRecord` rows are only inserted when attendance is actually taken for a `ClassSession`, or when a student explicitly marks a class as `PENDING` (e.g. they know the class happened but they are unsure of their status).
- **Rule**: A missing `AttendanceRecord` for an existing `ClassSession` implies the record hasn't been created yet. However, if a record *is* explicitly created as `PENDING`, it must never count mathematically as `ATTENDED` or `MISSED`.

## 5. Quiz Policy & Schedule Representation

We expand beyond a simple `target_percentage`:
- **`QuizCycle`**: Defines the cycle (1, 2, 3).
- **`EligibilityPolicy`**: Linked to the cycle. Stores `lecture_threshold`, `combined_threshold`, and applies globally to that cycle.
- **`QuizSchedule`**: Links a `Subject` to a `QuizCycle`. Contains `date` (DATE) and `schedule_status` (Enum: `SCHEDULED`, `UNRESOLVED`, `CANCELLED`).

## 6. BCS-054 Q3 Representation (Source-Data Discrepancy)

- It is explicitly modeled in `QuizSchedule` for subject BCS-054 and Cycle 3 with:
  - `date`: `NULL`
  - `schedule_status`: `UNRESOLVED`
- **Reason:** The official Quiz Test Schedule PDF confirms Department Elective-I (BCS-054) happens during Week 15 (19-24 Oct) but lacks an explicit date, whereas `timetable.json` asserts `2026-10-23`. We treat this as a source-data discrepancy and leave it UNRESOLVED so the database accurately reflects "we know this cycle exists for this subject, but the exact date is insufficiently confirmed."

## 7. Section/Cohort Decision

- While the legacy system is hardcoded for CSE-51, we introduce a lightweight `Section` table.
- Users are assigned to a `Section`.
- This prevents hardcoding the "CSE-51" string throughout the application and provides a non-destructive path to multi-tenancy in Phase 4.

## 8. Laboratory Persistence Model

- `LabExperiment`: Defines `experiment_number` (1-10) and `title`.
- `LabRecord`: Tracks student progress.
  - `signature_status` (Enum: `PENDING`, `SIGNED`)
  - `date_conducted` (DATE)
  - `signed_on` (TIMESTAMP WITH TIME ZONE)
  - `marks` (FLOAT)
  - `remarks` (TEXT)
- **Constraint**: `UNIQUE(student_id, experiment_id)`.

## 9. Derived vs. Source Data

- **Persisted**: Facts (e.g., "Student X attended Class Y on Date Z").
- **Not Persisted**: Derived statistics (e.g., 75% attendance, 3 safe skips, "is eligible for quiz"). These will be calculated dynamically by the Phase 1 domain engines when queried by the services.

## 10. Seed/Reference Data Strategy

- A deterministic seed script will populate `AcademicSession`, `Semester`, `Section`, `Subject`, `TimetableEntry`, `QuizCycle`, `EligibilityPolicy`, and `QuizSchedule` using the S3.10 baseline facts.
- It will **not** create any fake users or attendance records.
