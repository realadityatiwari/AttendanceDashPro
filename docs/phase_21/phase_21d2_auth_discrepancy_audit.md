# AttendanceDash Pro — Production Authentication Discrepancy Audit

Status: **COMPLETE (read-only)** — root cause identified. No fix implemented,
no account/data/auth logic mutated, no production DB accessed.

## 1. Executive Summary

The same credentials authenticate on `localhost` but return
`401 Unauthorized — "Incorrect roll number or password"` on production
(`attendance-dash-pro.vercel.app` → `attendancedash-api.onrender.com`).

**Root cause (evidence-based): the production Supabase database contains
zero application user rows.** The 21D.2 initialization procedure creates the
schema via `alembic upgrade head` **without importing any development data**
("only schema + alembic_version rows created. No application data" — see the
provisioning runbook). The login endpoint's `SELECT ... WHERE roll_number = ...`
therefore returns **no user**, and the anti-enumeration code path (Phase 16)
responds with the identical 401 message used for both "user not found" and
"wrong password". Localhost works because the local PostgreSQL DB contains
the owner account (`2401220100027`, ADMIN, PBKDF2-SHA256 hash).

This is **not** a code defect — it is the expected behavior of an
empty-but-migrated production database.

## 2. Authentication Flow Map (traced from repository)

```
Frontend (Next.js) 
  └─ apiFetch() → POST https://attendancedash-api.onrender.com/api/v1/auth/login
       body: { "roll_number": "...", "password": "..." }
       └─ FastAPI auth.py login():
            rate_limit(10/15min)  ← Phase 16
            └─ SELECT User WHERE roll_number = :r      (auth.py:57)
                 ├─ user found, hashed_password present?
                 │    ├─ verify_password(plain, pbkdf2 hash)  (security.py:8)
                 │    │    ├─ True  → create_access_token → 200 {access_token}
                 │    │    └─ False → 401 "Incorrect roll number or password"  (log: "incorrect password")
                 │    └─ missing → dummy-hash verify → 401 same message  (log: "roll_number not found")
                 └─ user NOT found → dummy-hash verify → 401 same message  (log: "roll_number not found")
```

- **PBKDF2-SHA256, 100,000 iterations, per-user hex salt**, format
  `pbkdf2_sha256$<salt>$<hex>` (security.py:33-46).
- **Anti-enumeration (Phase 16):** both failure branches return the identical
  message "Incorrect roll number or password"; the server logs differ
  (auth.py:66 vs auth.py:73) — which branch fired is only visible in the
  Render logs, not the HTTP response.
- **JWT**: HS256, `sub` = user UUID, `type=access`, 8h expiry.

## 3. Data Provenance — localhost vs production

| | localhost | production (Render → Supabase) |
|---|---|---|
| DATABASE_URI | `backend/.env` → `postgresql+asyncpg://postgres:postgres@localhost:55432/attendancedash` (Docker `attendancedashpro_db`) | Render env var → Supabase Session Pooler `postgresql+asyncpg://postgres.<ref>:...@aws-0-ap-south-1.pooler.supabase.com:5432/postgres?ssl=require` |
| Origin of DB | Phase 4.5 Firebase→PostgreSQL migration + dev seeding | **Created fresh in 21D.2; schema only** |
| Users | **1** (owner `2401220100027`, ADMIN, PBKDF2 hash) | **0** (by design) |
| Academic baseline | seeded via `seed_academic_baseline.py` / `expand_baseline.py` from `timetable.json` | not seeded (runbook: schema only) |

Confirmed read-only (dev DB): users = 1; `2401220100027 Aditya Tiwari`,
role ADMIN, `hashed_password` present and in `pbkdf2_sha256$` format;
alembic head `e1f2a3b4c5d6`.

## 4. Migration Path & Technical Viability

### Firebase → PostgreSQL (Phase 4.5, historical)

- `backend/scripts/migrate_extract.py` / `migrate_execute.py` — one-shot
  Firebase tools (require `firebase_admin`; blocked if absent). They upsert
  `User(firebase_uid, roll_number, name)` and attendance, **but never write
  `hashed_password`** — Firebase Auth does not expose password hashes, so
  legacy accounts migrated **passwordless** (NULL hash → cannot log in; 28
  such accounts were deleted in Phase 21A.1).
- The owner's password was set **locally** later via
  `backend/scripts/set_initial_password.py` (PBKDF2). It exists **only in the
  local dev DB**.

### PostgreSQL → Supabase (Phase 21D.2)

- Schema migrated via `alembic upgrade head` to head `e1f2a3b4c5d6`.
- **No migration or script copies user data to Supabase.** The provisioning
  runbook explicitly forbids importing development data, and the Alembic chain
  contains no user-seeding (verified: no `INSERT INTO users` in any migration
  file).
- `provision_admin.py` (the only sanctioned role-grant path) requires the user
  row to already exist in the target DB — it cannot create the account.
- Therefore **the production database has no user row for `2401220100027`** —
  nothing to authenticate against.

## 5. Evidence: Does the Account Exist in Production?

| Evidence | Finding |
|---|---|
| 401 (not 500) from login | `users` table exists; SELECT executed successfully |
| Alembic migrations seed users? | **No** — zero `INSERT INTO users` in `backend/alembic/versions/*.py` |
| Any script copies dev users to Supabase? | **No** — runbook forbids it; no such script exists |
| Registration performed against production? | No evidence in repo/runbook; production has no academic baseline (no active AcademicSession → register would 503) |
| Render logs (would show "roll_number not found") | Not accessible from repo — owner must confirm, but consistent with all other evidence |

**Determination: the existing account does not exist in the production
database.** Localhost succeeds only because the account exists in the dev DB.

## 6. Is Password Preservation Technically Supported?

**Yes — but only for data that exists in the target DB.**

- The PBKDF2 hash format (`pbkdf2_sha256$salt$hex`, 100k iterations) is fully
  compatible with `verify_password` — no format mismatch is possible for the
  owner's hash (verified format in dev DB).
- Firebase-era hashes are **not** extractable (Firebase Auth never exposes
  them) — this is irrelevant to the owner account, whose password was set
  locally in PostgreSQL.
- The constraint "preserve the existing account and attendance data" means:
  the data lives in the **dev DB** and must not be destroyed. The production
  DB was intentionally created empty; preservation is about not overwriting
  the dev source and about provisioning production without touching dev.

## 7. Root Cause (narrow, evidence-based)

**The production Supabase database has no user rows.** The 21D.2 schema-only
initialization created the tables but never provisioned the owner account
(or any account). Login's user lookup returns nothing; the Phase 16
anti-enumeration path returns the generic 401. Localhost authenticates because
the dev DB holds the account. This is an **operational/data-state gap**, not
an application defect — the auth code is identical in both environments
(confirmed: same `auth.py`, `security.py`, models; no env-conditional
authentication logic).

## 8. Minimal Safe Fix Plan (preserve all existing data — NOT implemented)

> All steps run against the **production Supabase DB only**; the local dev DB
> is untouched. No existing production rows exist, so nothing is overwritten.

1. **Confirm scope (owner action)**: check Render logs for the login branch —
   `Login failed: roll_number not found or no password set` confirms the
   diagnosis before proceeding.
2. **Seed the production academic baseline (idempotent, from `timetable.json`)**:
   `seed_academic_baseline.py` → `expand_baseline.py` →
   `seed_academic_events.py` against Supabase. This creates the active
   AcademicSession/Semester/Section/Subjects needed by register (otherwise
   register returns 503). These are structural/config rows, not user data.
3. **Create the owner account via the canonical registration contract**:
   `POST /api/v1/auth/register` with `2401220100027` + the owner-chosen
   password. This writes a fresh PBKDF2 hash; identity (roll number, name) is
   preserved by the existing register flow (server-side, JWT-derived).
   - Alternative: one-time operator script using `hash_password()` +
     `User(...)` insert into Supabase — but register is preferred (uses the
     existing sanctioned path and provisions enrollments).
4. **Grant ADMIN** via the sanctioned `backend/scripts/provision_admin.py
   2401220100027` against Supabase (role is DB-backed; no self-promotion path).
5. **Verify**: login against production returns 200; `/student/me` returns the
   profile; attendance history will be empty until the semester's attendance
   is generated (or, if the owner wants historical attendance restored, that
   is a separate data-import decision requiring explicit authorization).
6. **Data preservation guarantee**: no dev DB rows are modified/deleted; no
   production rows are overwritten (production is empty); no password is
   reset on the dev account.

## 9. Files Inspected

- `backend/app/api/v1/endpoints/auth.py` (login/register)
- `backend/app/core/security.py` (PBKDF2, JWT)
- `backend/app/api/dependencies/deps.py` (auth dependencies)
- `backend/app/models/user.py` (User model)
- `backend/app/core/config.py` (DATABASE_URI / env handling)
- `backend/scripts/migrate_extract.py`, `migrate_execute.py` (historical Firebase migration)
- `backend/scripts/provision_admin.py`, `set_initial_password.py`
- `backend/scripts/seed_academic_baseline.py`, `expand_baseline.py`, `seed_academic_events.py`
- `backend/alembic/versions/*.py` (migration chain — no user seeding)
- `docs/phase_21/phase_21d2_provisioning_runbook.md` (production init procedure)
- `docs/phase_21/phase_21d2_database_connection_audit.md` (connection contract)
- `render.yaml`, `backend/.env.example` (env contract)

## 10. Changes Made

- Governance docs only: `MASTER_ROADMAP.md`, `implementation_plan.md`,
  `task.md`, `walkthrough.md` — this audit's findings and planned steps.
- No application code changed. No database mutated. No account created,
  deleted, or reset.

## 11. Explicit Confirmation

- **No account, data, or authentication logic was mutated.**
- **No production database was accessed** (no credentials in repo; read-only
  audit of dev DB only via SELECT).
- **No fix implemented.** HARD STOP — awaiting explicit authorization for the
  fix plan (Section 8).
