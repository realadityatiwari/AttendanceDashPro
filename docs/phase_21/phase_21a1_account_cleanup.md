# AttendanceDash Pro — Phase 21A.1: Approved Account Cleanup

Status: **COMPLETE & FROZEN** — authorized destructive cleanup executed,
verified, and committed. No commit/push made to Git.

## 1. User Authorization

The user explicitly reviewed the Phase 21A account audit and authorized
deletion of **all accounts except**:

- `2401220100027` — Aditya Tiwari — ADMIN

This supersedes the prior "REQUIRES REVIEW" classifications. Total: 31 →
1. No credentials are documented here.

## 2. Database Inspected

| Item | Value |
|---|---|
| Database | `attendancedash` (PostgreSQL 16) |
| Environment | Local development (Docker container `attendancedashpro_db`) |
| Production touched | **NO** |
| Alembic head | `e1f2a3b4c5d6` (unchanged) |

## 3. Pre-Delete User Count

**31** (1 ADMIN + 30 STUDENT).

## 4. Protected Admin Account

- Login ID: `2401220100027`
- Name: Aditya Tiwari
- Role: ADMIN
- Hashed password: present (login-capable; value never exposed)

## 5. Exact Deletion Set (30 accounts)

1234567890123 · 1234567890124 · 1784234793950 · 1784234889724 · 1784234967035 ·
1784235000888 · 1784235054777 · 1784235095186 · 1784238752480 · 1784238795616 ·
1785692857932 · 1785692895734 · 2022000000001 · 2026080400001 · 2200000000054 ·
2201430100001 · 2301031023000 · 2301031023009 · 2401220100028 · 2401230100001 ·
9000000000001 · 9000000000002 · 9786270316628 · 9786270789131 · 9786270797603 ·
9786270805688 · 9786271446929 · 9786271455591 · 9786271464258 · 9999999999999

## 6. Dependency Graph (FK references to users)

All user FKs use `ON DELETE NO ACTION` — children must be deleted first:

```
attendance_records.user_id
feedback.user_id
laboratory_records.user_id / created_by / updated_by / signed_by
notifications.user_id
student_enrollments.user_id
userpreferences.user_id
```

Deletion order executed: attendance → notifications → feedback → preferences →
enrollments → laboratory_records (all user-owned columns) → users.

## 7. Dependent Rows Deleted by Category

| Table | Rows Deleted |
|---|---|
| attendance_records | 5 |
| notifications | 34 |
| student_enrollments | 18 |
| userpreferences | 2 |
| feedback | 0 |
| laboratory_records | 0 |

**Total dependent rows deleted: 59** (all owned by the 30 deleted users).

## 8. Transaction Strategy

Single transaction: reconfirm owner → reconfirm deletion set → delete
dependents → delete 30 users → verify (1 user, ADMIN, admin invariants,
0 orphans) → **COMMIT**. Any failure → ROLLBACK. (A first run rolled back
cleanly on a harness bug before COMMIT; the committed run passed every
in-transaction assertion.)

## 9. Post-Delete Verification

| Check | Result |
|---|---|
| Users remaining | 1 |
| Remaining user | 2401220100027 — Aditya Tiwari — ADMIN |
| Admin hashed_password | present |
| Orphan rows (all 9 FK columns) | 0 |
| Academic/system data | untouched (subjects 9, sessions 720, quiz 18, events 60, cycles 3, policies 3, timetable 28, sections 1, semesters 1, sessions 1) |
| Alembic head | e1f2a3b4c5d6 |
| QA-window attendance (owner) | 5 preserved |

## 10. Admin Before/After Invariants

| Data | Before | After | Status |
|---|---|---|---|
| Enrollments | 9 | 9 | ✅ preserved |
| Attendance | 159 | 159 | ✅ preserved |
| Notifications | 39 | 39 | ✅ preserved |
| Preferences | 1 | 1 | ✅ preserved |
| Feedback | 0 | 0 | ✅ preserved |
| Laboratory records | 0 | 0 | ✅ preserved |

## 11. Orphan Verification

**0 orphan rows** across all 9 user-referencing FK columns (attendance,
feedback, notifications, enrollments, preferences, laboratory user/created/
updated/signed).

## 12. Authentication Verification

- Backend imports OK (`app.main`).
- ORM user lookup OK (ADMIN).
- JWT mint + `get_current_user` → 2401220100027 ADMIN.
- `require_admin` → ADMIN.
- Login with wrong password → 401 (auth path functional).
- Admin password/hash/role unchanged; no new accounts created.

## 13. Database Mutation Counts

INSERT = 0 · UPDATE = 0 · **DELETE = 90** (30 users + 59 dependent rows;
explicitly authorized) · ALTER = 0 · DROP = 0

## 14. Cleanup Result

**31 → 1.** Only `2401220100027` (Aditya Tiwari, ADMIN) remains. Owner's data
fully intact.

## 15. Remaining Risks

- The owner account is now the only account; no additional admin exists for
  redundancy (accepted — single-owner design).
- No student accounts remain in the dev DB — signup is the only way to create
  new students; any verifier requiring pre-existing students must mint
  accounts via the registration contract.
- Phase 20 QA-window notification deltas for deleted users were removed with
  their owners (34 of 62); the owner's 28 remain.
- No production impact: production does not exist.

## 16. Next Authorized Phase

**PHASE 21B — FEEDBACK ADMIN SYSTEM** (NOT STARTED; awaiting authorization).
