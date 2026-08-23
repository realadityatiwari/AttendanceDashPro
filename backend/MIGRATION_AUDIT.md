# MIGRATION AUDIT (Phase 5.0)

> ## ⚠️ HISTORICAL DOCUMENT (superseded 2026-08-23)
>
> This document is the Phase 5.0 pre-migration readiness audit, written when the
> migration from Firebase/Firestore to PostgreSQL had not yet been executed and
> the backend auth boundary was still scaffolded. Since then:
> - The Firebase → PostgreSQL data migration **was executed** (Phase 4.5) and the
>   results independently verified (`backend/migration_reports/`).
> - The backend adopted **PostgreSQL-native JWT authentication** — the "Firebase
>   Admin SDK *must* be integrated" requirement (section 13) was superseded by
>   native JWT, and **Firebase is now fully retired** (Phases 14A–14E;
>   `firebase_uid` removed by migration `e1f2a3b4c5d6`).
>
> Preserved for historical provenance. Do not treat as a description of current
> state.

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
| **Attendance Facts** | Firestore (`attendance`) | **Server-side authoritative source.** (Note: `localStorage` may contain newer unflushed mutations). |
| **Lab Records** | Firestore (`laboratory`) | **Server-side authoritative source.** |
| **Academic Events** | PostgreSQL Baseline / REQUIRES PRODUCT DECISION | Baseline replaces legacy student-created events, which are now globally defined. The decision to completely discard legacy student-created events requires a formal product decision. |
| **UI Settings** | N/A (Discarded) | Theme and simulation flags are not migrated to PostgreSQL. |

**Firestore vs localStorage Authority (KNOWN LIMITATION / MIGRATION RISK):**
Firestore is the authoritative **SERVER-SIDE** legacy source available for migration. `localStorage` acts as a client-side cache and is potentially newer. The legacy code does *not* strictly guarantee that every local mutation reaches Firestore before the browser closes (e.g., offline usage or network failure). Any unflushed `localStorage` state is unrecoverable server-side. The two stores are NOT guaranteed identical.

## 5. Firebase Admin vs Firestore Access Separation
**Status:** REQUIRES DESIGN
The future migration tooling requires distinct capabilities:
- **A. Firebase Authentication Administration:** Required by migration scripts to extract the user list, extract `email` (to parse `roll_number`), and link to `uid`.
- **B. Firebase ID-token verification:** Required by the FastAPI `deps.py` for runtime authentication (`verify_id_token`).
- **C. Firestore Data Extraction:** Required by migration scripts to extract legacy `students` documents.
*Note: Implementing token verification (B) for the frontend does NOT automatically give the migration tool access to all legacy Firestore data (C). The migration tool will need a Python script using `firebase-admin` and a service account to query Firestore and Auth.*

## 6. Migration User Identity Mapping
**Status:** CONFLICT / REQUIRES DESIGN
Mapping legacy identity to the PostgreSQL `User` model:
- **PostgreSQL `User.id`**: A native `UUID`. This is NOT the Firebase UID.
- **PostgreSQL `User.firebase_uid`**: Stores the string Firebase UID. This is the immutable linkage key. It has a UNIQUE constraint.
- **PostgreSQL `User.roll_number`**: Must be extracted from the Firebase Auth pseudo-email (`[rollNumber]@student.app`). It has a UNIQUE constraint.
- **PostgreSQL `User.name`**: Derived from Firestore `profile.name`.

**Conflict Resolution Strategy (Future):**
- **Missing Firestore Profile:** The user has an Auth account but no Firestore doc. Create a `User` using the `roll_number` as a fallback `name`.
- **Profile Roll Number conflicts with Firebase Email:** Trust the Firebase Auth Email as authoritative.
- **Duplicate Roll Numbers:** If two Firebase UIDs map to the same `roll_number`, quarantine the second account (CONFLICT).
- **Malformed Pseudo-emails:** Quarantine if it cannot be cleanly parsed to a roll number.

## 7. Attendance Mapping
**Status:** REQUIRES DESIGN
The PostgreSQL `AttendanceRecord` schema uses `user_id`, `class_session_id`, and `status`. It does NOT store `date, subject, class_type` directly.

**Conceptual Migration Mapping:**
1. Parse legacy key `YYYY-MM-DD:SUBJECT:TYPE`.
2. Extract `date`, map subject code to `Subject.id`, map type to `ClassType`.
3. **Resolve `ClassSession`**: Query PostgreSQL `class_sessions` for `(date, subject_id, class_type)`.
4. If found, insert `AttendanceRecord(user_id, class_session_id, status)`.

**Edge Cases & Classifications:**
- **Standard 1:1 Match**: SUPPORTED.
- **Multiple sessions (same subject, same type, same date)**: AMBIGUOUS (Legacy keys cannot distinguish them).
- **Lecture + Tutorial on same date**: SUPPORTED (Types differ).
- **Practical sessions**: SUPPORTED.
- **Unknown subject**: CONFLICT / REQUIRES MANUAL REVIEW. (Do NOT discard. Quarantine the record).
- **Session does not exist in baseline (e.g. substitutions, makeups)**: CONFLICT / REQUIRES DESIGN (Should the migration script dynamically generate `ClassSession` records? Currently NO, unless designed to do so).

## 8. Laboratory Mapping
**Status:** REQUIRES DESIGN
The PostgreSQL `LaboratoryRecord` requires `user_id` and `experiment_id`. It has a UNIQUE constraint on `(user_id, experiment_id)`.

**Conceptual Migration Mapping:**
1. From legacy `laboratory` object, iterate over subject codes.
2. Resolve subject code to `Subject.id`.
3. For each legacy experiment, resolve `Subject.id` + `experimentNumber` to `LaboratoryExperiment.id`.
4. If missing/unknown `experimentNumber`, quarantine (CONFLICT).
5. Map `signatureStatus`, `dateConducted`, `marks`, `remarks`.

## 9. BCS-054 Handling
**Status:** VERIFIED
- **PostgreSQL Baseline for BCS-054 Quiz III:** Preserved as `date = NULL`, `status = UNRESOLVED`. Do not change this.
- **Legacy Attendance on 2026-10-23:** The existence of legacy attendance facts on `2026-10-23` for BCS-054 simply means a class occurred on that date. It must NOT automatically mean that 2026-10-23 is the official Quiz III date.

## 10. Validation Strategy Correction
**Status:** PLANNED
Validation must produce a detailed reconciliation report rather than a simple count match:
- **Successfully Resolved Records:** Count of attendance/lab records successfully mapped.
- **Quarantined/Conflicting Records:** Log of unknown subjects, missing class sessions, ambiguous sessions, or duplicate roll numbers.
- **Intentionally Skipped Records:** Derived data that is intentionally dropped.
- **Foreign-Key Integrity:** No orphaned records.
- **Identity Mapping:** 1:1 linkage between `firebase_uid` and `users.id`.

## 11. Idempotency Correction
**Status:** PLANNED
A rerun of the migration script must not blindly overwrite or duplicate data. Idempotency keys must be strictly defined:
- **User:** Unique on `firebase_uid`. `ON CONFLICT (firebase_uid) DO UPDATE SET name = EXCLUDED.name`.
- **AttendanceRecord:** Unique constraint `uq_user_class_session` (`user_id`, `class_session_id`). `ON CONFLICT ON CONSTRAINT uq_user_class_session DO UPDATE SET status = EXCLUDED.status`.
- **LabRecord:** Unique constraint `uq_user_experiment` (`user_id`, `experiment_id`). `ON CONFLICT ON CONSTRAINT uq_user_experiment DO UPDATE`.

## 12. Rollback Strategy Correction
**Status:** PLANNED
A single global transaction for thousands of users is too risky and prevents partial success.
- **Per-User Transaction Boundaries:** Wrap the migration of a *single user* (UPSERT User + INSERT Attendance + INSERT Lab) inside its own `BEGIN ... COMMIT`.
- If one user's data is corrupted, `ROLLBACK` just that user and log them in the reconciliation report, allowing the rest of the cohort to migrate successfully.
- Ensures retryability for failed users.

## 13. Firebase Admin Dependency
**Status:** BLOCKED
The current backend has `deps.py` stubbed out with `HTTP 501 Not Implemented`. Firebase Admin SDK *must* be integrated into the FastAPI backend (with a service account JSON).
**Note:** Successful Firebase/Firestore extraction has NOT been runtime-verified because valid Firebase Admin credentials are unavailable.

## 14. Migration Blockers
**Status:** BLOCKED
1. **Firebase Admin SDK is not configured.**
2. Migration tooling (capable of Firestore extraction, Auth extraction, and Postgres reconciliation) does not exist.
3. ClassSession dynamic generation vs. quarantine policy is not yet designed.

## 15. Recommended Phase 5.1 Scope
**Status:** REQUIRES DESIGN
1. Generate Firebase Admin Service Account credentials securely.
2. Implement `auth.verify_id_token` in `backend/app/api/dependencies/deps.py`.
3. Design the Python migration CLI script architecture to address the quarantine/reconciliation requirements.

## 16. Post-Migration Integrity Audit (Phase 5.5)
**Status:** VERIFIED

The Firebase to PostgreSQL live migration has been executed and the state independently verified.

**PostgreSQL Post-Migration State:**
- Users: 29 (Migrated)
- AttendanceRecords: 83 (Migrated)
- LaboratoryRecords: 0
- ClassSessions: 684
- LaboratoryExperiments: 0
- PostgreSQL Writes: 112 (29 users + 83 attendance)
- Failed Users: 0

**BCS-054 Invariant:**
- Subject: BCS-054 Quiz Cycle 3
- Preserved State: `date = NULL`, `status = UNRESOLVED`

**Unresolved/Quarantined Records (Requires Manual Product Decision):**
*Laboratory (1 record):*
- `Od675BhQ8KSvPv8DAIi140tAJdT2` - `BCS-551` (UNKNOWN_EXPERIMENT - Missing authoritative curriculum data)

*Attendance Missing Session (2 records):*
- `HCRbV7Kld3Wo9IHLJHRGlBau4Mq2` - `2026-07-17:BCS-058:T` (MISSING_SESSION - ClassSession does not exist)
- `HCRbV7Kld3Wo9IHLJHRGlBau4Mq2` - `2026-07-16:BCS-054:T` (MISSING_SESSION - ClassSession does not exist)

*Attendance Ambiguous (7 records):*
- `HCRbV7Kld3Wo9IHLJHRGlBau4Mq2` - `2026-07-30:BCS-552:P2` (AMBIGUOUS - Found 2 candidate ClassSessions)
- `HCRbV7Kld3Wo9IHLJHRGlBau4Mq2` - `2026-08-10:BCS-551:P` (AMBIGUOUS - Found 2 candidate ClassSessions)
- `HCRbV7Kld3Wo9IHLJHRGlBau4Mq2` - `2026-08-03:BCS-551:P1` (AMBIGUOUS - Found 2 candidate ClassSessions)
- `HCRbV7Kld3Wo9IHLJHRGlBau4Mq2` - `2026-08-06:BCS-552:P2` (AMBIGUOUS - Found 2 candidate ClassSessions)
- `HCRbV7Kld3Wo9IHLJHRGlBau4Mq2` - `2026-08-03:BCS-551:P2` (AMBIGUOUS - Found 2 candidate ClassSessions)
- `HCRbV7Kld3Wo9IHLJHRGlBau4Mq2` - `2026-08-06:BCS-552:P1` (AMBIGUOUS - Found 2 candidate ClassSessions)
- `HCRbV7Kld3Wo9IHLJHRGlBau4Mq2` - `2026-07-30:BCS-552:P1` (AMBIGUOUS - Found 2 candidate ClassSessions)
