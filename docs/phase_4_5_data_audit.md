# AttendanceDash Pro — Phase 4.5 Data Integrity & Account Foundation Audit

Date: 2026-08-13 · Mode: READ-ONLY (no mutations performed)
Scope: factual state of the development database before deciding preserve vs. reset of historical attendance.

---

## 1. Database Inventory

PostgreSQL instance: docker container `attendancedashpro_db`, database `attendancedash`, user `postgres`.
Alembic head: `8a2b3c4d5e6f` (1 revision — initial schema).

| Table | Rows | PK | Relevant FKs | Key date columns | Key status columns |
|---|---|---|---|---|---|
| `users` | 29 | `id` (uuid) | `section_id → sections.id` | `created_at`, `updated_at` | `firebase_uid` (NOT NULL, UNIQUE), `roll_number` (UNIQUE), `hashed_password` (nullable) |
| `sections` | 1 | `id` | `semester_id → semesters.id` | — | `name` (UNIQUE) |
| `semesters` | 1 | `id` | `session_id → academic_sessions.id` | `start_date`, `end_date` | — |
| `academic_sessions` | 1 | `id` | — | `start_date`, `end_date` | `is_active` |
| `subjects` | 9 | `id` | `semester_id → semesters.id` | — | `category` (THEORY/LAB), `quiz_applicable`, `attendance_applicable`, `code` |
| `student_enrollments` | 9 | `id` | `user_id → users.id`, `subject_id → subjects.id` | — | — (no status column) |
| `timetable_entries` | 28 | `id` | `subject_id → subjects.id` | — | `day_of_week` (int), `class_type`, `start_time`, `end_time` |
| `class_sessions` | 684 | `id` | `subject_id → subjects.id`, `timetable_entry_id → timetable_entries.id` | `date` | `class_type`, `is_extra`, `is_cancelled` |
| `attendance_records` | 83 | `id` | `user_id → users.id`, `class_session_id → class_sessions.id`; UNIQUE `(user_id, class_session_id)` | `created_at`, `updated_at` | `status` (ATTENDED/MISSED/PENDING) |
| `academic_events` | 0 | `id` | `subject_id → subjects.id` | `start_date`, `end_date` | `event_type`, `is_working_day`, `active` |
| `quiz_cycles` | 3 | `id` | — | — | `cycle_number` (UNIQUE), `label` |
| `quiz_schedules` | 18 | `id` | `subject_id → subjects.id`, `quiz_cycle_id → quiz_cycles.id` | `date` (nullable) | `schedule_status` (SCHEDULED/UNRESOLVED/CANCELLED) |
| `eligibility_policies` | 3 | `id` | `quiz_cycle_id → quiz_cycles.id` | — | `lecture_threshold`, `combined_threshold` |
| `laboratory_experiments` | 0 | `id` | `subject_id → subjects.id` | — | — |
| `laboratory_records` | 0 | `id` | `user_id → users.id`, `experiment_id → laboratory_experiments.id` | — | `signature_status` (PENDING/SIGNED) |
| `alembic_version` | 1 | `version_num` | — | — | — |

Enum types in use: `attendancestatus` (ATTENDED, MISSED, PENDING), `classtype` (LECTURE, TUTORIAL, PRACTICAL), `eventtype` (14 values incl. holidays/overrides), `schedulestatus` (SCHEDULED, UNRESOLVED, CANCELLED), `subjectcategory` (THEORY, LAB), `signaturestatus`.

## 2. Development User Identity

| Field | Value |
|---|---|
| PostgreSQL `id` | `9b84e891-120a-4ec5-8801-79ab7bd66c90` |
| Name | Aditya Tiwari |
| Roll number | `2401220100027` (UNIQUE) |
| `firebase_uid` | `HCRbV7Kld3Wo9IHLJHRGlBau4Mq2` (still present; column NOT NULL + UNIQUE) |
| Section | `CSE-51` |
| Semester | V Semester, `2026-07-15` → `2026-12-31` |
| Academic session | `2026-27` (`is_active = true`) |
| User created | `2026-08-12 19:07:31 UTC` |

Passwords/hashes intentionally not reported. Authentication is PostgreSQL + JWT; Firebase is retired.

## 3. Enrollment State

`student_enrollments`: **9 rows, all for this single user** (1 distinct `user_id` across the table).

| Code | Name | Category | Quiz | Attendance |
|---|---|---|---|---|
| BCS-054 | OOS Design with C++ | THEORY | yes | yes |
| BCS-058 | Data Warehousing & Data Mining | THEORY | yes | yes |
| BCS-501 | Database Management System | THEORY | yes | yes |
| BCS-502 | Web Technology | THEORY | yes | yes |
| BCS-503 | Design & Analysis of Algorithm | THEORY | yes | yes |
| BCS-551 | Database Management System Lab | LAB | no | yes |
| BCS-552 | Web Technology Lab | LAB | no | yes |
| BCS-553 | Design & Analysis of Algorithm Lab | LAB | no | yes |
| BNC-501 | Constitution of India | THEORY | yes | yes |

- **MNPM-501 does not exist** in `subjects` (9 subjects total) and has no enrollment. Not invented.
- **BCS-504 does not exist** in the database either. The `subjects` table is the single source of truth.

## 4. Attendance History Range

For user `2401220100027`:

- **Earliest record**: 2026-07-15 (semester start day)
- **Latest record**: 2026-08-11
- **Total records**: 78
- **Status split**: ATTENDED 54 · MISSED 24 · PENDING 0 (no PENDING rows exist anywhere in the table)

By class type: LECTURE 62 (42 att / 20 miss) · TUTORIAL 16 (12 att / 4 miss) · PRACTICAL 0.

- **Creation provenance**: all 78 records were inserted **in one bulk write on 2026-08-12** (`created_at` truncated to day = 2026-08-12 for every row). This is a one-shot import (legacy or manual), not a daily-marked history. It is internally plausible, but its values cannot be cross-verified against any daily log.
- Class sessions in range (2026-07-15 → 2026-08-13): **124 sessions** (all with `timetable_entry_id`, 0 cancelled, 0 extra) — generated from the 28-entry weekly timetable for weekdays only.

## 5. Subject-by-Subject Audit (2026-07-15 → today)

| Subject | Scheduled sessions | Attendance records | Present | Absent | Unmarked |
|---|---|---|---|---|---|
| BCS-054 | 19 | 16 | 10 | 6 | 3 |
| BCS-058 | 18 | 16 | 7 | 9 | 2 |
| BCS-501 | 17 | 11 | 10 | 1 | 6 |
| BCS-502 | 17 | 14 | 11 | 3 | 3 |
| BCS-503 | 18 | 15 | 13 | 2 | 3 |
| BNC-501 | 9 | 6 | 3 | 3 | 3 |
| BCS-551 | 8 | 0 | 0 | 0 | 8 |
| BCS-552 | 10 | 0 | 0 | 0 | 10 |
| BCS-553 | 8 | 0 | 0 | 0 | 8 |
| **Total** | **124** | **78** | **54** | **24** | **46** |

Notes:
- Theory unmarked: 20 sessions (all within 2026-07-15 → 2026-08-11; the last two days, 08-12 and 08-13, have zero records at all).
- Labs (BCS-551/552/553) have **never been marked** — 26 sessions, zero records. The laboratory module is fully inert (`laboratory_experiments` and `laboratory_records` are empty).
- Lab days carry **two parallel sessions** (batch 1 + batch 2, distinct `timetable_entry_id`); the two-batch structure is intentional, not duplication.

## 6. Date Coverage (2026-07-15 → 2026-08-13)

30 days total: 20 weekdays with sessions (5–6 per day), 10 weekend days with 0 sessions (no weekend classes exist).

- Sessions per weekday pattern: Mon 5 · Tue 6 · Wed 6 · Thu 6 · Fri 5.
- Records exist on **18 of 20 working days** (07-15 → 08-11, partial).
- **08-12 and 08-13: 0 records** (marking lag of ~2 days).
- **No cancellations or holidays are modeled anywhere**: `academic_events` is empty (0 rows) and `is_cancelled` is false on all 684 sessions. Therefore every weekday session is currently treated as having happened; a 0-record day means "not marked", never "class did not happen". There is no calendar evidence of any non-teaching day in the period.

Coverage summary: the database contains everything needed to reconstruct the attendance picture — every session is present and joinable; only per-session marking status is missing for the 46 unmarked sessions.

## 7. Data Consistency Checks (read-only)

| Check | Result |
|---|---|
| Duplicate attendance (user, session) | 0 — blocked by UNIQUE `uq_user_class_session` |
| Records pointing to nonexistent sessions | 0 (FK-enforced) |
| Records before 2026-07-15 | 0 |
| Records after semester end (2026-12-31) | 0 |
| Null session dates / null statuses | 0 / 0 |
| Sessions without subject relationship | 0 (FK-enforced) |
| Sessions whose subject differs from timetable entry | 0 |
| Weekend sessions | 0 |
| **Records for subjects the user is not enrolled in** | **5** — all belong to OTHER test users (`Alice`, `Test User`, `Recovery Test Student` ×2, `Test User`), who have **zero enrollments**. **None belong to Aditya Tiwari.** |
| Duplicate sessions (subject, date, class_type) | 73 groups — all the intentional two-batch lab sessions (BCS-551/552/553), each with a distinct `timetable_entry_id`. Not corruption. |
| Quiz schedule duplicates | 0 |
| Quiz schedules with NULL date | 1 — BCS-054 Quiz3 (`UNRESOLVED`), by-design for a future cycle |
| Quiz policy coverage | 3 cycles × 1 policy each (cycle 1: 70.0; cycles 2–3: 75.0) |

**Conclusion: zero structural issues in Aditya Tiwari's data.** The 5 "unenrolled" records are test-user noise outside the target user. The only data gaps are the 46 unmarked sessions described above.

## 8. Firebase Legacy Dependencies

- `users.firebase_uid` is **NOT NULL + UNIQUE** in the schema and still populated (Aditya holds a Firebase-style UID). It is the only schema-level dependency.
- Runtime: `app/core/firebase.py` initializes the Admin SDK at startup (no-ops without credentials file) but **login does not use it** — `POST /auth/login` verifies against `hashed_password` and issues a JWT. Postgres + JWT is fully self-contained for the current architecture.
- Legacy tooling only (not runtime): `scripts/migrate_extract.py`, `scripts/migrate_execute.py`, `scripts/diagnose_failures.py` still reference `firebase_admin`.
- Frontend: **no Firebase JS SDK**. Only `localStorage` usage is the JWT (`access_token`) in `lib/api.ts`, `contexts/AuthContext.tsx`, `app/(auth)/login/page.tsx`. No legacy attendance data in localStorage.
- `StudentProfile` (backend schema + frontend type) still exposes `firebase_uid`.

## 9. Analytics Compatibility

Verified against the actual engines and repositories (read-only):

- `AttendanceRepository.get_subject_counts_up_to_date` / `get_subject_counts_between`: `class_sessions` LEFT OUTER JOIN `attendance_records` — a session without a record yields `status = NULL`, which the service maps to **PENDING**. **No engine requires one record per session.** The 46 unmarked sessions flow through the pipeline as pending by construction.
- `compute_subject_stats` (attendance engine): consumes `(class_type, status)` counts; current % = attended/(attended+missed), forecast % assumes pending are attended; `normalize_class_type` maps P1/P2 → P. All stored values map 1:1 to the enum. **Compatible.**
- `evaluate_quiz_eligibility` / `determine_quiz_threshold` (eligibility engine): window-bounded counts via `get_subject_counts_between`; cycle 1 = 70%, cycles 2–3 = 75%. **Compatible.**
- Dashboard aggregation (`get_sessions_with_status` + `dashboard_service.py`): same outerjoin pattern. **Compatible.**
- Known engine-level nuance (no live impact): unmarked **cancelled** sessions would count as pending because the repo does not filter `is_cancelled` — currently 0 cancelled sessions exist, so nothing is affected.

## 10. Signup Architecture Status (audit only — no implementation)

| Question | Finding |
|---|---|
| Signup endpoint | **None.** `auth.py` exposes only `POST /auth/login` (roll_number + password → JWT). |
| Signup page | **None.** Only `frontend/src/app/(auth)/login/page.tsx` exists. |
| How users are created today | Scripts only: `scripts/setup_single_user.py`, `scripts/set_initial_password.py`, legacy `scripts/migrate_execute.py`. No runtime path. |
| Enrollment during signup | **Not possible.** `student_enrollments` is never written by any endpoint; it is seeded by scripts. |
| Academic info a new user needs | `users`: name, roll_number (UNIQUE), hashed_password, and `firebase_uid` (NOT NULL + UNIQUE). Optional `section_id` — if set, it implies semester + session context (section → semester → academic_session). Enrollments then require existing subject rows. |
| Constraints preventing arbitrary enrollment | `users.roll_number` UNIQUE; `users.firebase_uid` NOT NULL UNIQUE (a retiring-Firebase app has no natural value for new users — needs a policy decision); sections/semesters/sessions must already exist (they do: 1 of each); no enrollment-creation endpoint exists. |
| Minimum work for a real signup flow | Backend: `POST /auth/register` (validate roll/name/password, hash, insert user — decide `firebase_uid` policy), plus an enrollment grant path (e.g., auto-enroll by section template). Frontend: `(auth)/signup` page + form + AuthContext hook-in. No schema migration strictly required if a derived `firebase_uid` (e.g., `legacy:<uuid>`) is acceptable; otherwise the NOT NULL constraint must be relaxed (migration). |

## 11. Data Trust Verdict

### FACTS OBSERVED
- Aditya's 78 records are structurally perfect: no orphans, no duplicates, dates entirely within semester, subjects all enrolled, valid enum statuses.
- The records were bulk-imported on 2026-08-12 — provenance is a single snapshot; values are internally plausible (54/24 split, sensible per-day spread) but not independently verifiable.
- 46 sessions unmarked: 20 theory (07-15 → 08-11) + 26 labs (never marked at all). The last two days (08-12, 08-13) have no records — consistent with ordinary marking lag.
- No cancellations/holidays modeled (`academic_events` empty) — sessions-vs-records comparison is unambiguous.
- The engines consume this data structure without any modification.

### VERDICT: **B — PRESERVE WITH MANUAL CORRECTION**

- **Not C (RESET)**: there is no structural corruption or unreliability in the underlying data. Missing records are legitimately explainable as unmarked classes, and the guidance explicitly excludes resetting for that reason.
- **Not plain A (PRESERVE)**: a clearly identifiable amount of manual re-entry is required — the 20 unmarked theory sessions within the covered window (07-15 → 08-11) and the **entire lab history** (26 sessions, zero records; the lab module is inert with no experiment catalog either).

## 12. Recommended Next Step (for user decision — nothing executed)

1. **Keep the existing data** (no reset, no deletions).
2. **Manually enter the 20 missing theory marks** for 2026-07-15 → 2026-08-11 via the existing record-mutation path (Track-phase marking), or accept them as pending and let live marking continue from today.
3. **Decide the lab policy**: whether BCS-551/552/553 attendance should be marked retroactively (26 sessions) and whether lab sessions should count into attendance summaries — and, if the lab module is to be used, seed `laboratory_experiments` first.
4. **Optionally seed `academic_events`** so future cancelled/holiday days can be modeled (currently none exist; all weekdays are treated as teaching days).
5. **Separately** (Phase 4.5 STEP 2 territory, not implemented): design the real signup flow once the `firebase_uid` NOT NULL policy is decided.

---

*End of audit. No database, schema, engine, or application code was modified.*