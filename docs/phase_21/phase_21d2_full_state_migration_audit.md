# AttendanceDash Pro — Phase 21D.2: Full Localhost ADMIN State → Production Migration Audit

Status: **COMPLETE (read-only)** — migration plan only. No migration executed,
no database mutated, no account/data/auth logic changed.

## 1. Phase Status

**AUDIT COMPLETE — MIGRATION NOT EXECUTED.** This document is the complete
read-only audit and migration plan for reproducing the localhost ADMIN
environment in the Supabase production database. Awaiting explicit operator
authorization before any execution.

## 2. Localhost Database State (read-only, verified 2026-08-26)

**Database**: `attendancedash` (PostgreSQL 16, Docker `attendancedashpro_db`),
Alembic head `e1f2a3b4c5d6`.

### Row counts

| Table | Rows | User-owned | Academic baseline | Dashboard-relevant |
|---|---|---|---|---|
| users | 1 | owner | no | yes |
| sections | 1 | no | yes | yes |
| academic_sessions | 1 | no | yes | yes |
| semesters | 1 | no | yes | yes |
| subjects | 9 | no | yes | yes |
| student_enrollments | 9 | owner (9) | no (join) | yes |
| timetable_entries | 28 | no | yes | yes |
| class_sessions | 720 | no | yes | yes |
| attendance_records | 165 | owner (165) | no | yes |
| academic_events | 61 | no | yes | yes |
| quiz_cycles | 3 | no | yes | yes |
| eligibility_policies | 3 | no | yes | yes |
| quiz_schedules | 18 | no | yes | yes |
| laboratory_experiments | 0 | — | — | — |
| laboratory_records | 0 | — | — | — |
| notifications | 43 | owner (43) | no | yes |
| userpreferences | 1 | owner (1) | no | yes |
| feedback | 0 | — | — | — |

### Owner identity (values shown are non-secret)

- `2401220100027` — Aditya Tiwari — ADMIN
- id: `9b84e891-120a-4ec5-8801-79ab7bd66c90`
- section: `CSE-51` (id `6d4b2200-87ee-4d3b-8910-7541b1c1992a`), program CSE
- password hash: **present, PBKDF2-SHA256, 100,000 iterations** (format
  `pbkdf2_sha256$<salt>$<hex>`; hash value never printed)
- enrollments 9 · attendance 165 (108 ATTENDED / 57 MISSED) · notifications 43
  · preferences 1 · feedback 0 · lab 0

### Academic baseline details

- Active session: `2026-27` (id `de06197e-…`), `is_active = true`
- Semester: `V Semester` (id `e517951d-…`)
- Subjects: BCS-054, BCS-058, BCS-501, BCS-502, BCS-503, BCS-551, BCS-552,
  BCS-553, BNC-501
- class_sessions span 2026-07-15 → 2026-12-31 (720 rows)
- attendance span 2026-07-15 → 2026-08-25 (165 rows)
- quiz_cycles Quiz1/Quiz2/Quiz3; quiz_schedules 18 (SCHEDULED)
- events by type: EXTRA_LECTURE 18, EXTRA_TUTORIAL 1, CLASS_CANCELLED 8,
  SURPRISE_QUIZ 7, QUIZ_DAY 22, MID_SEM_PRACTICAL 3, LAB_CANCELLED 1, HOLIDAY 1
- timetable by weekday: 5/6/6/6/5

## 3. Production Database State

**NOT ROW-INSPECTED this phase.** The prior audit (Phase 21D.2 auth
discrepancy audit) established:
- Supabase `attendancedashpro-prod`, schema initialized at Alembic head
  `e1f2a3b4c5d6`
- **zero application user rows**
- 401 on login because no user row exists

Production row-level comparison was **not performed in this phase**: the
Supabase `DATABASE_URI` exists only in the Render dashboard (secrets not in
the repository, not obtained, not requested). Production inspection is
deferred to execution time (with operator-provided access).

## 4. Complete Relevant Table/Entity Inventory

### 4.1 Foreign keys (full dependency graph)

| Table | FK column(s) → target |
|---|---|
| semesters | session_id → academic_sessions(id) |
| sections | semester_id → semesters(id) |
| subjects | semester_id → semesters(id) |
| users | section_id → sections(id) |
| student_enrollments | user_id → users(id), subject_id → subjects(id) |
| timetable_entries | subject_id → subjects(id) |
| class_sessions | subject_id → subjects(id), timetable_entry_id → timetable_entries(id) |
| attendance_records | user_id → users(id), class_session_id → class_sessions(id) |
| academic_events | subject_id → subjects(id) |
| quiz_cycles | (root) |
| eligibility_policies | quiz_cycle_id → quiz_cycles(id) |
| quiz_schedules | subject_id → subjects(id), quiz_cycle_id → quiz_cycles(id) |
| laboratory_experiments | subject_id → subjects(id) |
| laboratory_records | user_id, created_by, updated_by, signed_by → users(id); class_session_id → class_sessions(id); experiment_id → laboratory_experiments(id) |
| notifications | user_id → users(id) |
| userpreferences | user_id → users(id) (PK = user_id) |
| feedback | user_id → users(id) |

### 4.2 Unique constraints

- attendance_records: UNIQUE (user_id, class_session_id)
- laboratory_experiments: UNIQUE (subject_id, experiment_number)
- laboratory_records: UNIQUE (user_id, experiment_id)
- notifications: UNIQUE (user_id, kind, occurrence_key)
- userpreferences: PK = user_id
- users: PK id; roll_number unique (index)
- all others: PK id (UUID)

## 5. What Must Migrate (REQUIRED PRODUCTION STATE)

| Priority | Table | Reason |
|---|---|---|
| 1 | academic_sessions | active session (register + all pages resolve it) |
| 1 | semesters | semester scoping |
| 1 | sections | user section + profile |
| 1 | subjects | subjects, labs, quiz, events |
| 2 | quiz_cycles | eligibility engine |
| 2 | eligibility_policies | quiz thresholds |
| 2 | timetable_entries | session materialization |
| 2 | quiz_schedules | quiz dates (authoritative; see Phase 7 audit) |
| 3 | class_sessions | attendance container |
| 3 | academic_events | calendar/events semantics (QUIZ_DAY, cancellations, etc.) |
| 4 | users | owner account (identity, role, hash) |
| 4 | student_enrollments | enrollment scoping |
| 4 | attendance_records | historical attendance (calculations must match localhost) |
| 4 | notifications | user-visible state |
| 4 | userpreferences | user settings |

Empty tables (laboratory_experiments, laboratory_records, feedback) migrate as
empty (no rows) — they are schema-only in production already.

## 6. What Must NOT Migrate

| Data | Why not |
|---|---|
| Test/verifier residue | none currently in users (only owner); verifier temp rows are cleaned up by design |
| Supabase service-role keys / provider metadata | secrets — never migrate |
| `alembic_version` beyond head | production already at head `e1f2a3b4c5d6` |
| Firebase-era NULL-password users | already deleted in Phase 21A.1 (localhost has only the owner) |
| Development-only config/credentials | never |

## 7. Dependency Graph / Migration Order

```text
Layer 1 (root, no FK deps):  academic_sessions, quiz_cycles
Layer 2:                     semesters → academic_sessions
Layer 3:                     sections → semesters
Layer 4:                     subjects → semesters
Layer 5:                     users → sections
Layer 6:                     timetable_entries → subjects
Layer 7:                     class_sessions → subjects, timetable_entries
Layer 8:                     student_enrollments → users, subjects
Layer 9:                     academic_events → subjects
Layer 10:                    quiz_schedules → subjects, quiz_cycles
Layer 11:                    eligibility_policies → quiz_cycles
Layer 12:                    attendance_records → users, class_sessions
Layer 13:                    notifications → users
Layer 14:                    userpreferences → users
Layer 15:                    (laboratory_* → users, class_sessions, subjects; feedback → users) — empty locally, migrate as empty
```

## 8. UUID / Primary Key Preservation — YES, SAFE

- **Production is empty** (zero application rows), so **no conflicts exist**.
- All PKs are UUIDs generated by the app; SQLAlchemy models assume UUID PKs.
- Preserving localhost UUIDs keeps **all FK relationships intact by
  construction** (no remapping), preserves `userpreferences` PK (=
  `user_id`), preserves `notifications` UNIQUE (user_id, kind,
  occurrence_key), and keeps attendance/quiz/event relationships exact.
- **Recommendation: preserve all UUIDs as-is.** Rationale: simplest, safest,
  zero remapping risk, and production has no conflicting rows. The only
  alternative (regenerate) would require a full ID-remap table and adds risk
  for no benefit.
- Timestamps: preserve (created_at/updated_at) to keep dashboard/audit
  behavior consistent with localhost.

## 9. Password Hash Preservation — YES, SAFE (Approach A recommended)

**The PBKDF2-SHA256 hash can be copied to production directly.**

Evidence:
- `verify_password()` (security.py:8-31) accepts exactly the stored format
  `pbkdf2_sha256$<salt>$<hex>` with 100,000 iterations — no dependency on a
  local salt registry or external KMS.
- The owner's hash is in this exact format (verified read-only: `is_pbkdf2=True`).
- The hash is portable: it contains its own salt; verification works on any
  host running the same code.

### Comparison: Approach A vs Approach B

| | A: Preserve identity + hash + IDs | B: Recreate via registration + migrate data |
|---|---|---|
| Password validity | ✅ exact same hash → same password works | ⚠️ new password required (user must choose/change) |
| Identity (roll, name) | ✅ preserved | ✅ preserved (if same roll) |
| UUIDs | ✅ preserved | ❌ new user UUID → all FKs need remap |
| Admin role | ✅ copied (role column) | ⚠️ register creates STUDENT → must provision_admin afterward |
| Enrollments/attendance/notifications | ✅ direct copy, FK-consistent | ❌ must remap user_id everywhere |
| userpreferences (PK=user_id) | ✅ direct | ❌ remap required |
| Simplicity / risk | ✅ lowest risk, direct insert | ❌ highest risk, full remap |
| Data integrity | ✅ byte-identical | ⚠️ derived data (attendance percentages) preserved only if remap is exact |

**Recommendation: Approach A** — copy the User row (including `hashed_password`)
verbatim with the same UUID. This is the only way to make production
authenticate with the exact localhost password while preserving every
user-owned relationship without remapping.

**Safeguard**: the hash is never printed; the migration tool reads it directly
from the source DB into the target DB. No one needs to see or retype it.

## 10. Existing Migration/Seed Tooling Assessment

| Tool | Reusable for this migration? |
|---|---|
| `migrate_execute.py` / `migrate_extract.py` | ❌ Firebase→PostgreSQL one-shot (Phase 4.5). Reads Firestore/Firebase Auth, not localhost PostgreSQL. Not applicable. |
| `seed_academic_baseline.py` | ⚠️ Partially — it **recreates** the academic baseline deterministically from `timetable.json` (idempotent, skip-existing). Could seed production baseline **instead of** copying rows — but row-for-row copy is safer for exact equivalence (timestamps, active flags). |
| `expand_baseline.py` | ⚠️ Same — generates class_sessions from timetable; **not** a row-copy. |
| `seed_academic_events.py` | ⚠️ Same — regenerates events from quiz_schedules; **not** a row-copy. |
| `provision_admin.py` | ⚠️ Reusable only in Approach B (grants ADMIN to an existing user). Not needed in Approach A (role copied). |
| `set_initial_password.py` | ❌ Not needed in Approach A (hash copied). Only for Approach B password setup. |
| `backup_database.ps1` | ✅ Reusable as the source-extraction mechanism (pg_dump -Fc of localhost). |

**Conclusion**: no existing script performs a **row-for-row localhost→Supabase
copy**; the seeders regenerate from source data. For exact equivalence, a new
dedicated copy tool is recommended (Section 13).

## 11. Recommended Migration Strategy

**Approach A — direct row-for-row copy with UUID/hash preservation**, in
dependency order (Section 7), executed by a purpose-built idempotent tool.

```text
LOCALHOST (read-only source)
   ↓ pg_dump -Fc (backup_database.ps1) → staging file (not production)
   ↓ controlled extraction (new tool) → ordered INSERT statements
   ↓ SUPABASE PRODUCTION (Alembic head e1f2a3b4c5d6)
```

- All 18 tables copied (14 populated + 4 empty) in FK-safe order.
- UUIDs, hashed_password, timestamps preserved verbatim.
- No registration, no password reset, no remap.
- Production baseline: because production is empty, `INSERT` cannot conflict.
- After load, run the validation plan (Section 15).

## 12. Reuse vs New Tooling

**Reuse**: `backup_database.ps1` (localhost pg_dump), Alembic head check,
existing seed scripts as reference for expected row shapes.

**New tool required**: a single-purpose `scripts/migrate_localhost_to_supabase.py`
(execute-only after authorization) that:
1. Connects to localhost (read-only) and Supabase (write) via `DATABASE_URI`
   env vars (never hardcoded; never printed).
2. Reads rows in dependency order.
3. Inserts with `ON CONFLICT DO NOTHING` (idempotent).
4. Verifies counts after each layer.
5. Is **read-only on localhost**; writes only to Supabase.

No application code, models, or migrations change.

## 13. Idempotency Strategy

- Every table load uses `ON CONFLICT DO NOTHING` keyed on PK (UUID) — safe
  because UUIDs are preserved.
- Secondary natural keys (roll_number unique index, notification
  (user_id, kind, occurrence_key), enrollment (user_id, subject_id),
  attendance (user_id, class_session_id)) are inherently satisfied by copying
  the same source rows — no duplicates can arise from a source that already
  satisfies them.
- Re-running the tool after partial success simply skips already-inserted
  rows.
- Precondition: confirm production has zero rows for the target tables
  (execution-time SELECT count). If any exist, STOP and report (do not merge).

## 14. Validation Plan (post-migration, read-only)

| Check | Localhost source | Production target | Method |
|---|---|---|---|
| user count | 1 | 1 | `SELECT count(*) FROM users` |
| owner identity | 2401220100027 | 2401220100027 | SELECT roll_number/name/role |
| role | ADMIN | ADMIN | SELECT role |
| password login | 200 | 200 | `POST /api/v1/auth/login` (owner password) — user-verified |
| academic session | 2026-27 active | 2026-27 active | SELECT is_active |
| semester / section | V / CSE-51 | V / CSE-51 | SELECT |
| subject count | 9 | 9 | SELECT count(*) |
| enrollment count | 9 | 9 | SELECT count(*) WHERE user_id = owner |
| attendance count | 165 | 165 | SELECT count(*) WHERE user_id = owner |
| attendance breakdown | 108 ATTENDED / 57 MISSED | same | GROUP BY status |
| attendance span | 07-15 → 08-25 | same | MIN/MAX join class_sessions |
| attendance pct | identical | identical | attendance summary endpoint (user-verified) |
| quiz cycles/schedules | 3 / 18 | 3 / 18 | SELECT count(*) |
| events count | 61 | 61 | SELECT count(*) |
| notifications | 43 | 43 | SELECT count(*) WHERE user_id = owner |
| preferences | 1 | 1 | SELECT count(*) |
| lab/feedback | 0 | 0 | SELECT count(*) |
| class_sessions | 720 | 720 | SELECT count(*) |
| timetable_entries | 28 | 28 | SELECT count(*) |
| dashboard-visible | matches | matches | user browser test (not automated) |

All checks are read-only SQL or the existing endpoints. No secrets exposed.

## 15. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Production row conflicts (if anything exists) | High | Pre-execution `count=0` guard; STOP if nonzero |
| Wrong target DB | High | `DATABASE_URI` verified against Supabase host before any write |
| Idempotency violation (duplicate notifications etc.) | Med | `ON CONFLICT DO NOTHING` + preserved UUIDs |
| Password hash incompatible | Low | Same PBKDF2 format verified (`is_pbkdf2=True`) |
| Attendance engine divergence | Low | Exact row copy → same inputs → same outputs |
| Supabase constraints not in localhost (e.g. RLS) | Med | Verify Supabase RLS is disabled/bypassed for the migration role |
| Timezone/datetime drift | Low | Copy timestamptz verbatim |
| Partial failure | Med | Per-layer verification; rerun idempotently |

## 16. Rollback Strategy

Because production is currently empty, rollback = **truncate the migrated
tables** (or drop/recreate the database). Precedence:
1. If production has zero pre-existing rows: `TRUNCATE` the 18 tables
   (FK-safe: disable triggers or truncate in reverse dependency order) →
   production returns to schema-only state.
2. Localhost is never touched, so the source of truth always remains intact.
3. Document the exact truncate sequence in the execution plan (reverse of
   Section 7).

## 17. Exact Commands/Scripts (would be executed after authorization)

```text
# 0. Preflight (execution time, operator-provided env)
DATABASE_URI=<supabase> python - <<SQL
  SELECT count(*) FROM users;  -- expect 0
SQL

# 1. Source snapshot (localhost, read-only)
.\backend\scripts\backup_database.ps1 -OutputDir <staging>

# 2. Controlled migration (NEW tool; read-only on localhost, writes Supabase)
DATABASE_URI_SOURCE=...  DATABASE_URI_TARGET=...  \
  python backend/scripts/migrate_localhost_to_supabase.py --verify-only   # dry run
DATABASE_URI_SOURCE=...  DATABASE_URI_TARGET=...  \
  python backend/scripts/migrate_localhost_to_supabase.py                 # execute

# 3. Validation (read-only)
# run the Section 14 checks via SQL + login test
```

## 18. Files Inspected

- `backend/app/models/*.py` (all 12 model modules)
- `backend/app/api/v1/endpoints/auth.py`, `student.py`
- `backend/app/core/security.py`, `config.py`
- `backend/app/db/session.py`
- `backend/scripts/`: migrate_execute.py, migrate_extract.py,
  seed_academic_baseline.py, expand_baseline.py, seed_academic_events.py,
  provision_admin.py, set_initial_password.py, backup_database.ps1
- `backend/alembic/versions/*.py` (chain, head e1f2a3b4c5d6)
- `docs/phase_21/phase_21d2_provisioning_runbook.md`
- `docs/phase_21/phase_21d2_auth_discrepancy_audit.md`
- `docs/phase_21/phase_21d2_database_connection_audit.md`
- `render.yaml`, `backend/.env.example`

## 19. Files Changed

- `docs/phase_21/phase_21d2_full_state_migration_audit.md` — NEW (this document)
- Governance: `MASTER_ROADMAP.md`, `implementation_plan.md`, `task.md`,
  `walkthrough.md` — audit findings + planned steps only

**No application code, models, migrations, scripts, or API contracts changed.**

## 20. Database Mutation Counts

- Localhost: **INSERT = 0 · UPDATE = 0 · DELETE = 0 · ALTER = 0 · DROP = 0**
  (read-only SELECT only)
- Production: **NOT ACCESSED · NOT MIGRATED · NOT MUTATED**

## 21. Confirmation

- **No database was mutated.**
- **No account was created, deleted, or reset.**
- **No password was changed or exposed.**
- **No application logic was changed.**
- **No production data was accessed.**
- **No commit/push performed.**

## 22. Explicit Confirmation of Mutation Status

```
LOCALHOST DB: zero mutations
PRODUCTION DB: not accessed, not migrated, not mutated
AUTH LOGIC: unchanged
MIGRATION: NOT EXECUTED (plan only)
```

## 23. Next Authorized Action

The next phase will execute the migration ONLY after the operator reviews this
plan and explicitly authorizes it: create
`migrate_localhost_to_supabase.py`, run preflight count check, execute the
ordered copy, run the validation plan, and document results.
