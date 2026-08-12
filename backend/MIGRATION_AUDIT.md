# MIGRATION AUDIT (Phase 5.0)

## 1. Executive Summary
This document provides a comprehensive readiness analysis for migrating the AttendanceDash Pro legacy application (Firebase/localStorage) to the new PostgreSQL/FastAPI architecture. The analysis identifies source structures, defines authority hierarchies, maps data shapes, and highlights critical migration blockers. **No data has been migrated yet.**

**Status:** PHASE 5.0 AUDIT COMPLETE — READY FOR MIGRATION DESIGN

## 2. Current Architecture
**Status:** SOURCE INSPECTED
The target architecture is governed by PostgreSQL, managed via SQLAlchemy models and Alembic migrations.
- **Reference Data Baseline:** Seeded deterministically via `seed_academic_baseline.py` using `timetable.json`. This provides `AcademicSession`, `Semester`, `Subject`, `TimetableEntry`, `QuizCycle`, `EligibilityPolicy`, and `QuizSchedule`.
- **User Data:** Currently empty. Represented by `User`, `StudentEnrollment`, `AttendanceRecord`, `LabRecord`, and `AcademicEvent`.

## 3. Legacy Data Sources
**Status:** SOURCE INSPECTED
The legacy JS application uses three primary data stores:
1. **Firebase Authentication:** Handles password verification and identity mapping via pseudo-emails.
2. **Firestore (Cloud):** The canonical storage for a student's `AppState` (Profile, Attendance, Laboratory, Settings, Events).
3. **localStorage:** The active runtime state. Operates offline-first, flushing to Firestore (`db.collection('students').doc(uid).set(...)`) upon changes.

## 4. Authority Matrix
**Status:** VERIFIED
Not all legacy data is authoritative. This hierarchy dictates conflict resolution:

| Category | Authoritative Source | Reason |
|---|---|---|
| **Identity (UID, Password)** | Firebase Auth | Passwords exist only here. UID is the global foreign key. |
| **Email/Roll Number** | Firebase Auth | Created identically as `[rollNumber]@student.app`. Roll number can be reliably parsed from this. |
| **Student Name** | Firestore (`profile.name`) | Only captured in the Firestore profile document. |
| **Academic Rules** | PostgreSQL Baseline | Replaces legacy client-side math and `timetable.json`. |
| **Attendance Facts** | Firestore (`attendance`) | Single source of truth for user-marked attendance. |
| **Lab Records** | Firestore (`laboratory`) | Single source of truth for signatures. |
| **Academic Events** | PostgreSQL Baseline | Replaces legacy student-created events, which are now globally defined. |
| **UI Settings** | N/A (Discarded) | Theme and simulation flags are not migrated to PostgreSQL. |

## 5. Firebase Auth Audit
**Status:** SOURCE INSPECTED
- **Account Creation:** `signupUser(name, rollNumber, password)` creates an account.
- **Email format:** `${rollNumber}@student.app`. This is a pseudo-email. The Roll Number can be cleanly extracted by stripping `@student.app`.
- **Passwords:** Exist only in Firebase. They cannot be extracted or migrated to Postgres. Postgres will not store passwords.
- **Identity Linkage:** Multiple Firebase accounts could theoretically be created with different roll numbers if someone manipulates the API, but normal usage enforces a 1:1 UID to Roll Number mapping. The Firebase UID is the immutable primary key for linkage.

## 6. Firestore Data Model
**Status:** SOURCE INSPECTED
Firestore stores documents in the `students` collection, keyed by `uid`.
Document structure (`AppState`):
- `profile`: `{ name, rollNumber, createdAt }` -> Maps to `User`.
- `attendance`: `{"YYYY-MM-DD:SUBJECT:TYPE": "Attended" | "Missed" | "Pending"}` -> Maps to `AttendanceRecord`.
- `laboratory`: `{"SUBJECT": [{experimentNumber, signatureStatus, dateConducted, marks, remarks}]}` -> Maps to `LabRecord`.
- `academicEvents`: `{"YYYY-MM-DD": [events]}` -> **DISCARDED** (Student-created events are obsolete).
- `settings`: `{ theme, simulationMode }` -> **DISCARDED**.

## 7. localStorage Data Model
**Status:** SOURCE INSPECTED
- `app_state_${uid}`: Contains the exact `AppState` structure as Firestore, but acts as a fast local cache.
- `attendance_tracker_states`: V1 legacy cache.
**Rule:** `localStorage` is volatile and client-bound. The migration script will ONLY read from Firestore. If a user has unflushed `localStorage` data, it cannot be migrated server-side.

## 8. Attendance Mapping
**Status:** VERIFIED
Legacy attendance keys are `dateStr:subjectCode:classType` (e.g., `2026-10-23:BCS-054:L`).
Values are `Attended`, `Missed`, `Pending`.

**Mapping Strategy:**
1. Parse Date from key -> `date`
2. Parse Subject from key -> Lookup `Subject.id`
3. Parse Type from key (`L`, `T`, `P1`, `P2`) -> Map to `ClassType` Enum.
4. Value -> Map to `AttendanceStatus` Enum.
5. Create `AttendanceRecord(user_id, date, subject_id, class_type, status)`.

**Safety:** This is a lossless 1:1 fact mapping. 

## 9. Derived vs Source Facts
**Status:** VERIFIED
Only **Source Facts** will be migrated.
- **Migrate:** Profile names, raw attendance states (`Attended/Missed`), lab signatures.
- **Discard/Recompute:** `total`, `completed`, `pending`, `present`, `absent`, quiz eligibility flags, percentage scores, optimization projections. The FastAPI engines will recalculate these dynamically from the migrated source facts.

## 10. Reset Tracker Analysis
**Status:** BLOCKED — REQUIRES DESIGN
The legacy JS app allows `clearStates()` which destructively empties the Firestore `attendance` and `laboratory` objects.
PostgreSQL relies on persistent fact tables. Destructively deleting foreign-keyed rows is anti-pattern.
**Recommendation:** The migration will ignore reset history. A future Phase must implement a non-destructive "Epoch" or "Soft Delete" mechanism in the DB if resetting is still desired.

## 11. Conflict Matrix
**Status:** SOURCE INSPECTED
| Conflict | Detection | Resolution |
|---|---|---|
| Mismatched Roll Number (Auth vs Profile) | Compare `email.split('@')[0]` vs `profile.rollNumber` | Trust Firebase Auth Email as the authoritative identity. |
| Attendance for unknown subject | Subject Code not in DB baseline | Discard the record (orphan). |
| Attendance on non-working day | Date conflicts with DB `AcademicEvent` | Keep record (could be a makeup class), or flag for manual review. |
| Duplicate Firestore Documents | Unlikely (keyed by UID) | Merge or take latest `updated_at`. |

## 12. BCS-054 Handling
**Status:** VERIFIED
Legacy `timetable.json` asserted BCS-054 Quiz III is `2026-10-23`.
PostgreSQL officially asserts this is `UNRESOLVED` (`date=NULL`).
**Action:** No attendance or quiz records need to be modified. The PostgreSQL baseline already correctly represents the unresolved state, and the new eligibility engine handles it seamlessly.

## 13. Proposed Migration Dependency Order
**Status:** VERIFIED (Design Only)
1. Firebase Admin SDK extracts all Auth Users.
2. Firestore export extracts all `students` documents.
3. For each user:
   a. Extract `uid`, parse `roll_number` from email.
   b. Extract `name` from Firestore profile.
   c. UPSERT `User` in PostgreSQL.
4. For each user's `attendance` object:
   a. Parse keys, lookup `Subject` IDs.
   b. INSERT `AttendanceRecord` batch.
5. For each user's `laboratory` object:
   a. Parse keys, lookup `Subject` IDs and `LabExperiment` IDs.
   b. INSERT `LabRecord` batch.

## 14. Validation Strategy
**Status:** REQUIRES DESIGN (Future Execution)
- Count matching: `Firestore attendance keys == Postgres AttendanceRecord rows`.
- Idempotency: Running migration twice must result in identical state (using `ON CONFLICT DO UPDATE`).
- Null checks: Ensure no `AttendanceRecord` links to a non-existent `Subject`.

## 15. Rollback Strategy
**Status:** REQUIRES DESIGN (Future Execution)
- Enclose the entire migration inside a single PostgreSQL Transaction (`BEGIN ... COMMIT`).
- On any data corruption exception, `ROLLBACK`.
- Do not modify or delete the source Firestore documents.

## 16. Firebase Admin Dependency
**Status:** BLOCKED
The current backend has `deps.py` stubbed out with `HTTP 501 Not Implemented`.
**CRITICAL:** Firebase Admin SDK *must* be integrated into the FastAPI backend (with a service account JSON) before the migration scripts can securely verify tokens or extract the Auth user list.

## 17. Migration Blockers
**Status:** BLOCKED
1. **Firebase Admin SDK is not configured.**
2. Migration CLI/scripts do not yet exist.

## 18. Recommended Phase 5.1 Scope
**Status:** REQUIRES DESIGN
1. Generate Firebase Admin Service Account credentials securely.
2. Implement `auth.verify_id_token` in `backend/app/api/dependencies/deps.py`.
3. Verify the frontend can successfully authenticate.
4. Write the Python migration CLI script (`migrate_firestore.py`).
