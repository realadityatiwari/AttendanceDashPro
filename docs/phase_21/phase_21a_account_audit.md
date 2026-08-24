# AttendanceDash Pro — Phase 21A: Account Audit & Cleanup

Status: **COMPLETE & FROZEN** — read-only account audit. No accounts deleted,
no records modified, no deployment.

## 1. Objective

Discover every current login/account, classify them, determine dependent-data
impact, verify the owner account, and produce a deletion plan for user
approval. **Read-only:** zero mutations.

## 2. Database / Environment Inspected

| Item | Value |
|---|---|
| Engine | PostgreSQL 16 |
| Database | `attendancedash` |
| Connection source | `backend/.env` → `DATABASE_URI` (localhost:55432) |
| Host | Docker container `attendancedashpro_db` |
| Environment | **Local development** (disposable per Phase 18C backup model) |
| Production database | **NONE exists** (Phase 21 confirmed) |
| Alembic head | `e1f2a3b4c5d6` (unchanged) |

## 3. Account Schema

| Column | Type | Notes |
|---|---|---|
| `id` | UUID | PK |
| `roll_number` | VARCHAR NOT NULL | Login identifier (unique) |
| `name` | VARCHAR NOT NULL | Display name |
| `hashed_password` | VARCHAR NULL | PBKDF2-SHA256; NULL = cannot log in |
| `role` | enum (STUDENT/ADMIN) | DB-authoritative |
| `section_id` | UUID NULL | FK to sections |
| `created_at` / `updated_at` | timestamptz | |

## 4. Complete Account Inventory (31 accounts)

| # | Login ID | Name | Role | Has PW | Enroll | Att | Notif | Prefs | Classification | Deletion Status |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2401220100027 | Aditya Tiwari | ADMIN | Yes | 9 | 159 | 39 | 1 | A. PROTECTED OWNER | PROTECTED |
| 2 | 1234567890124 | Aditya Tripathi | STUDENT | Yes | 9 | 0 | 17 | 1 | D. LIKELY REAL USER (login-capable) | REQUIRES REVIEW |
| 3 | 9999999999999 | Registration Verification | STUDENT | Yes | 9 | 0 | 17 | 1 | C. LIKELY TEST (established disposable convention) | REQUIRES REVIEW |
| 4 | 2200000000054 | Test User | STUDENT | No | 0 | 1 | 0 | 0 | C. LIKELY TEST | REQUIRES REVIEW |
| 5 | 2201430100001 | Alice | STUDENT | No | 0 | 1 | 0 | 0 | C. LIKELY TEST | REQUIRES REVIEW |
| 6 | 2401230100001 | Test User | STUDENT | No | 0 | 1 | 0 | 0 | C. LIKELY TEST | REQUIRES REVIEW |
| 7 | 9000000000002 | Recovery Test Student | STUDENT | No | 0 | 2 | 0 | 0 | C. LIKELY TEST | REQUIRES REVIEW |
| 8 | 1234567890123 | Audit Tester | STUDENT | No | 0 | 0 | 0 | 0 | C. LIKELY TEST | SAFE TO DELETE |
| 9 | 1784234793950 | Test Student | STUDENT | No | 0 | 0 | 0 | 0 | C. LIKELY TEST | SAFE TO DELETE |
| 10 | 1784234889724 | Test Student | STUDENT | No | 0 | 0 | 0 | 0 | C. LIKELY TEST | SAFE TO DELETE |
| 11 | 1784234967035 | Test Student | STUDENT | No | 0 | 0 | 0 | 0 | C. LIKELY TEST | SAFE TO DELETE |
| 12 | 1784235000888 | Test Student | STUDENT | No | 0 | 0 | 0 | 0 | C. LIKELY TEST | SAFE TO DELETE |
| 13 | 1784235054777 | Test Student | STUDENT | No | 0 | 0 | 0 | 0 | C. LIKELY TEST | SAFE TO DELETE |
| 14 | 1784235095186 | Test Student | STUDENT | No | 0 | 0 | 0 | 0 | C. LIKELY TEST | SAFE TO DELETE |
| 15 | 1784238752480 | Test Student | STUDENT | No | 0 | 0 | 0 | 0 | C. LIKELY TEST | SAFE TO DELETE |
| 16 | 1784238795616 | Test Student | STUDENT | No | 0 | 0 | 0 | 0 | C. LIKELY TEST | SAFE TO DELETE |
| 17 | 1785692857932 | Test Student | STUDENT | No | 0 | 0 | 0 | 0 | C. LIKELY TEST | SAFE TO DELETE |
| 18 | 1785692895734 | Test Student | STUDENT | No | 0 | 0 | 0 | 0 | C. LIKELY TEST | SAFE TO DELETE |
| 19 | 2022000000001 | 2022000000001 | STUDENT | No | 0 | 0 | 0 | 0 | C. LIKELY TEST | SAFE TO DELETE |
| 20 | 2026080400001 | Test Student | STUDENT | No | 0 | 0 | 0 | 0 | C. LIKELY TEST | SAFE TO DELETE |
| 21 | 2301031023000 | Test User | STUDENT | No | 0 | 0 | 0 | 0 | C. LIKELY TEST | SAFE TO DELETE |
| 22 | 2301031023009 | Test User | STUDENT | No | 0 | 0 | 0 | 0 | C. LIKELY TEST | SAFE TO DELETE |
| 23 | 2401220100028 | Test User 2 | STUDENT | No | 0 | 0 | 0 | 0 | C. LIKELY TEST | SAFE TO DELETE |
| 24 | 9000000000001 | 9000000000001 | STUDENT | No | 0 | 0 | 0 | 0 | C. LIKELY TEST | SAFE TO DELETE |
| 25 | 9786270316628 | Deep Probe Student | STUDENT | No | 0 | 0 | 0 | 0 | C. LIKELY TEST | SAFE TO DELETE |
| 26 | 9786270789131 | Race Test Student | STUDENT | No | 0 | 0 | 0 | 0 | C. LIKELY TEST | SAFE TO DELETE |
| 27 | 9786270797603 | Race Test Student | STUDENT | No | 0 | 0 | 0 | 0 | C. LIKELY TEST | SAFE TO DELETE |
| 28 | 9786270805688 | Race Test Student | STUDENT | No | 0 | 0 | 0 | 0 | C. LIKELY TEST | SAFE TO DELETE |
| 29 | 9786271446929 | Race Test Student | STUDENT | No | 0 | 0 | 0 | 0 | C. LIKELY TEST | SAFE TO DELETE |
| 30 | 9786271455591 | Race Test Student | STUDENT | No | 0 | 0 | 0 | 0 | C. LIKELY TEST | SAFE TO DELETE |
| 31 | 9786271464258 | Race Test Student | STUDENT | No | 0 | 0 | 0 | 0 | C. LIKELY TEST | SAFE TO DELETE |

**Notes:**
- 28 of 31 accounts have `hashed_password IS NULL` — they **cannot log in**
  (Firebase-era legacy accounts from Phase 4.5 migration; Firebase Auth retired
  in Phase 14). Only 3 accounts are login-capable (1 ADMIN + 2 STUDENT).
- "Audit Tester" (1234567890123) was created 2026-08-12 with a name matching
  the Phase 4.5 audit harness — likely test residue.
- Feedback count is 0 for all accounts (no feedback records exist).

## 5. Owner Account (verified)

| Field | Value |
|---|---|
| Login ID | **2401220100027** |
| Name | Aditya Tiwari |
| Role | **ADMIN** |
| Has password | Yes (login-capable) |
| Section | assigned |
| Enrollments | 9 |
| Attendance records | 159 |
| Notifications | 39 |
| Preferences | 1 |
| Feedback | 0 |
| Status | **PROTECTED** — matches documented owner candidate exactly |

## 6. Dependent Data (deletion impact)

- **All FKs from user-owned tables use `ON DELETE NO ACTION`** — deleting a
  user with any dependent row (enrollment, attendance, notification,
  preference, feedback, lab record) **fails** unless dependents are removed
  first. There is **no cascade** and **no application-level delete
  implementation** (verified: no delete endpoint/code exists).
- 24 accounts have **zero** dependent rows (SAFE TO DELETE).
- 7 accounts have dependent rows (REQUIRES REVIEW): owner + 6 test-ish users.

## 7. QA-Window Data Association (Phase 20 deltas)

| Data | Count | Associated user | Provenance |
|---|---|---|---|
| Attendance records (2026-08-24) | 5 | 2401220100027 (owner/ADMIN) | Created in QA window; uncertain (dev server running); **left intact** |
| Notifications (2026-08-23 17:00+ UTC) | 45 | 9999999999999 (17), 2401220100027 (28) | Read-model materialization side effects; regenerable; left intact |
| Notifications (2026-08-24) | 17 | 1234567890124 | Read-model materialization side effects; left intact |

These records were **not** associated with any test-only account that would be
candidate for deletion; the owner account carries the attendance delta.

## 8. Feedback Association

**0 feedback records exist.** No account has feedback. (Phase 21B will build
the admin feedback review surface — currently nothing to review.)

## 9. Authentication Model (relevant to cleanup)

- **Login identifier**: `roll_number` (unique).
- **User lookup**: `select(User).filter_by(roll_number=...)`.
- **Password**: PBKDF2-SHA256 via `hash_password`/`verify_password`; NULL
  password ⇒ login always fails (401).
- **JWT**: HS256, `sub`=user UUID, 8h expiry, `type=access` enforced.
- **Role**: DB enum column (`STUDENT`/`ADMIN`), resolved per request; no
  self-promotion path.
- **Logout**: frontend removes token locally; no server session.
- **Account deletion**: **NOT implemented** in application code. Deleting a
  user would require removing dependent rows first (FK NO ACTION) — this is
  Phase 21B+ work, gated on user approval.

## 10. Classification (evidence-based)

- **A. PROTECTED OWNER (1)**: 2401220100027 (verified ADMIN + owner).
- **C. LIKELY TEST/DEVELOPMENT (29)**: names (Test Student/User/Race/Probe/
  Recovery/Audit/Registration Verification), roll-number patterns, zero or
  trivial data, no passwords (28) — consistent with the Phase 4.5/6/10
  verification-harness conventions documented in walkthroughs.
- **D. LIKELY REAL USER (1)**: 1234567890124 "Aditya Tripathi" — login-capable,
  9 enrollments, real-looking name; cannot be assumed disposable. **UNKNOWN
  whether real** → user review required.

## 11. Proposed Cleanup

```
KEEP:
- 2401220100027 (owner, ADMIN, PROTECTED)

DELETE AFTER USER APPROVAL (24 accounts — zero dependent data, no password):
- 1234567890123, 1784234793950, 1784234889724, 1784234967035, 1784235000888,
  1784235054777, 1784235095186, 1784238752480, 1784238795616, 1785692857932,
  1785692895734, 2022000000001, 2026080400001, 2301031023000, 2301031023009,
  2401220100028, 9000000000001, 9786270316628, 9786270789131, 9786270797603,
  9786270805688, 9786271446929, 9786271455591, 9786271464258

REQUIRES USER REVIEW (6 — have dependent data and/or login capability):
- 1234567890124 (login-capable, 9 enrollments, 17 notif, 1 pref)
- 9999999999999 (login-capable, 9 enrollments, 17 notif, 1 pref)
- 2200000000054 (1 attendance)
- 2201430100001 "Alice" (1 attendance)
- 2401230100001 (1 attendance)
- 9000000000002 (2 attendance)

DO NOT DELETE:
- 2401220100027 (owner)
- any account until the user explicitly approves the deletion set
```

**IMPORTANT:** This is a proposal only. No deletion occurs in Phase 21A.

## 12. Safety Analysis

- **SAFE TO DELETE (24)**: zero dependent rows, no password, FK NO ACTION
  means plain `DELETE FROM users WHERE id=...` succeeds. No history impact.
- **REQUIRES REVIEW (6)**: deletion would require removing enrollments/
  attendance/notifications/preferences first — attendance history impact must
  be explicitly approved (especially the QA-window 5 records under the owner
  — those are on the owner account and are NOT in the deletion set).
- **DO NOT DELETE**: owner; also anything not explicitly approved.

## 13. Verification

| Check | Result |
|---|---|
| Read-only queries only (SELECT) | ✅ |
| `git diff --check` | ✅ PASS |
| No mutation commands executed | ✅ |
| Alembic head unchanged | ✅ `e1f2a3b4c5d6` |
| User count before/after | 31 / 31 |

## 14. Database Mutation Status

INSERT = 0 · UPDATE = 0 · DELETE = 0 · ALTER = 0 · DROP = 0

## 15. Remaining User Decisions

1. Confirm classification of 1234567890124 ("Aditya Tripathi") — real user or test?
2. Disposition of the 6 REQUIRES REVIEW accounts (including whether their
   attendance rows are disposable).
3. Approve or reject the 24-account deletion set (only then may deletion occur).
4. Confirm QA-window deltas remain untouched (default: yes).

## 16. Next Authorized Step

**PHASE 21B — Feedback Admin System** (per roadmap); account deletion remains
**NOT AUTHORIZED / PENDING USER APPROVAL** of the deletion set above.
