# Phase 10D — Settings / User Preferences (Implementation Report)

Status: **IMPLEMENTED 2026-08-19** — verifier 18/18, `tsc`/`eslint`/`next build`
green, migration applied + reversibility proven, DB residue verified clean.
Not committed.

## 1. Objective

Implement the Settings / user-preferences layer of Phase 10: a real
`userpreferences` table plus `GET/PUT /api/v1/student/preferences` endpoints,
and an API-backed Settings modal in the frontend. The three controls
(class reminders, auto-mark present, week starts on) are **STORAGE /
PREFERENCE DATA ONLY**: saving them sends no reminders, marks no attendance,
and changes no calendar/analytics calculation. Phase 11 consumes the stored
values; that wiring is explicitly out of scope.

## 2. Phase 10A decisions (applied)

A Phase 10A discovery report does not exist in `docs/` (glob confirmed), so
the decisions from the task prompt were applied:

| Decision | Implemented as |
|---|---|
| Server-side DB defaults | `class_reminders boolean NOT NULL DEFAULT false`, `auto_mark_present boolean NOT NULL DEFAULT false`, `week_starts_on weekstartson NOT NULL DEFAULT 'MONDAY'` — verified by raw-SQL insert (verifier check 13) |
| Lazy-create on first GET | `GET` materializes the defaults row for a user with no row; repeated GET is idempotent (check 1, 3) |
| No backfill migration | No rows written for existing users; verified (check 2) |
| Defaults matching Phase 2 foundations | false / false / MONDAY |

## 3. Implementation approach

- **Table name**: `userpreferences`. Model class `UserPreference`
  (auto-naming would produce the same). `user_id` is the **sole primary key**
  — the Base mixin's surrogate `id` is removed via `id = None` (empirically
  verified: table ends up with only `user_id` PK + timestamps).
- **Lazy-create race handling**: `get_or_create` commits the default row and
  on `IntegrityError` (concurrent first GET) rolls back and re-reads.
- **PUT = full-object replacement**: all three fields are required in the
  schema; a partial PUT → 422 (check 10). No `user_id` input field; identity
  comes from the bearer token only (check 12). No DELETE/PATCH/list endpoints.
- **Transaction ownership**: the service owns commit/rollback (the dominant
  repo convention in this codebase; `preference_repo` does not commit).
- **Frontend**: SWR key gated on modal-open (`usePreferences(open)`); draft
  state seeded from the fetched object; honest loading / saving / saved /
  error-with-retry states; Discard button; SUNDAY/MONDAY select; a
  "preferences only" disclaimer. Reset-on-close follows the codebase's
  "adjust state during render" pattern (EventFormDialog) to satisfy
  `react-hooks/set-state-in-effect`.
- **Verifier**: `scripts/verify_phase_10d.py`, 18 checks, in-process
  ASGITransport + minted JWTs, temporary users (roll_number `PH10D_A/B`),
  baseline snapshot/restore for every frozen table, cleanup in `finally`.

## 4. Files

**Created**

| File | Purpose |
|---|---|
| `backend/alembic/versions/c1d2e3f4a5b6_add_user_preferences.py` | Additive migration: `userpreferences` table + `weekstartson` enum |
| `backend/app/models/preference.py` | `UserPreference` model |
| `backend/app/schemas/preference.py` | `PreferenceUpdate`, `PreferenceResponse` |
| `backend/app/repositories/preference_repo.py` | `get` / `create_default` / `replace` (no commits) |
| `backend/app/services/preference_service.py` | `get_or_create` (lazy-create + race handling), `replace` (commit + refresh) |
| `backend/app/api/v1/endpoints/preferences.py` | `GET/PUT /preferences` under `/student`, `Depends(get_current_user)` |
| `backend/scripts/verify_phase_10d.py` | 18-check Phase 10D verifier |

**Modified**

| File | Change |
|---|---|
| `backend/app/models/enums.py` | Added `WeekStartsOn(str, Enum)` (SUNDAY/MONDAY) |
| `backend/app/models/__init__.py` | Registers `UserPreference` for Base.metadata |
| `backend/app/api/api.py` | Includes preferences router under `/student` |
| `frontend/src/types/api.ts` | `WeekStart`, `UserPreferences`, `UserPreferencesUpdate` |
| `frontend/src/hooks/useApi.ts` | `usePreferences(enabled)`, `usePreferenceMutation` |
| `frontend/src/components/shell/SettingsModal.tsx` | Rewritten — real, API-backed preferences |

## 5. API contract

```
GET /api/v1/student/preferences   (Bearer JWT)
  → 200 {class_reminders, auto_mark_present, week_starts_on, created_at, updated_at}
     (lazily creates the default row on first access)
  → 401 no/invalid token (HTTPBearer, same as existing endpoints)

PUT /api/v1/student/preferences   (Bearer JWT)
  body: {class_reminders: bool, auto_mark_present: bool, week_starts_on: "SUNDAY"|"MONDAY"}
  → 200 complete object (full-object replacement; row lazily created if absent)
  → 401 unauthenticated; 422 invalid enum value or partial body
```

- `user_id` is never exposed in responses or accepted in payloads.
- Admin behavior is identical to student (no role gate on preferences).

## 6. Data model & migration

```
userpreferences
  user_id            uuid        NOT NULL  PK  → users.id
  class_reminders    boolean     NOT NULL  DEFAULT false
  auto_mark_present  boolean     NOT NULL  DEFAULT false
  week_starts_on     weekstartson NOT NULL  DEFAULT 'MONDAY'::weekstartson
  created_at         timestamptz NOT NULL
  updated_at         timestamptz NOT NULL
```

- Revision `c1d2e3f4a5b6`, `down_revision b1c2d3e4f5a7` (feedback head).
  `alembic current`/`heads` confirm `c1d2e3f4a5b6 (head)`.
- Enum type name is **`weekstartson`** — the ORM (`Enum(WeekStartsOn)`)
  auto-derives the native type name from the lowercased class name, matching
  the existing `userrole`/`feedbacktype` convention. The migration must use
  the same name (see §10 for the pitfall that was found and fixed).
- Reversibility proven: `alembic downgrade -1` → `b1c2d3e4f5a7` (table +
  enum dropped cleanly), `alembic upgrade head` → `c1d2e3f4a5b6`.

## 7. Verification performed

- **Verifier (18/18 PASS)**: lazy-create defaults via API; idempotent GET;
  complete response shape; PUT replace semantics (false/false/MONDAY,
  true/true/SUNDAY, true/false/MONDAY); PUT on a rowless user creates exactly
  one row; invalid enum → 422; partial PUT → 422; unauthenticated → 401;
  user isolation (body/query `user_id` tampering changes nothing); raw-SQL
  insert applies server defaults; duplicate `user_id` rejected (PK); unknown
  `user_id` rejected (FK); frozen-table baseline restored exactly; preference
  writes changed zero attendance/event/session/record rows.
- **compileall**: exit 0. **Alembic**: current/heads match, downgrade/upgrade
  round-trip clean.
- **Frontend**: `tsc --noEmit` exit 0; `eslint` 0 errors (targeted changed
  files); `next build` success (15/15 routes, Turbopack).
- **DB residue**: after all runs `users=31` (baseline), `userpreferences=0`,
  zero `PH10D%` rows — verifier cleanup fully restores state.

## 8. Results

All verification green. The live DB ends with the new table existing but
empty (no backfill, no verifier residue) — exactly the Phase 10A decision.

## 9. DB final state (2026-08-19)

Frozen-table counts unchanged from pre-work baseline (academic_events 47,
class_sessions 715, attendance_records 142, student_enrollments 27, subjects
9, quiz_schedules 18, users 31, sections 1, feedback 0, laboratory 0,
timetable_entries 28, quiz_cycles 3, eligibility_policies 3, academic_sessions
1, semesters 1). `userpreferences` = 0 rows.

## 10. Deviations, findings & fixes

- **Enum type-name mismatch**: the first migration created the type as
  `weekstarson`, but the ORM auto-generates `weekstartson` from the class
  name — the first DB statement touching the column failed. Fixed by renaming
  in the migration and re-applying via downgrade/upgrade (which also proved
  reversibility). Existing enums use the same convention.
- **DuplicateObjectError pitfall**: pre-creating the enum AND passing it into
  `create_table` in one migration raises "type already exists" — the enum must
  be declared inline in `create_table` only.
- **Missing `await`** on `repo.create_default` (service `get_or_create`) and
  on `repo.replace` (service `replace`) — both caught by the verifier
  (`AttributeError: 'coroutine' object ...`) and fixed.
- **Verifier**: expected PK/FK violations poison the session transaction;
  added `rollback()` after each caught violation before cleanup.
- **eslint**: `react-hooks/set-state-in-effect` on the close-reset effect —
  replaced with the codebase's existing "adjust state during render" pattern.
- The `CRITICAL: Firebase service account credentials not found` log line at
  app import is pre-existing and harmless (JWT auth verified working).

## 11. Risks / out of scope

- Preferences are inert today by design (no consumer). Phase 11 wiring is out
  of scope; the settings UI states this explicitly.
- No reminder scheduling, no auto-marking, no analytics/calendar changes, no
  PWA/push wiring — none were touched.
- No changes to frozen systems (attendance, calendar, quiz, lab, dashboard,
  track, history, auth) — `git status`/`git diff` show only the files in §4.

## 12. Frozen-system impact

None. Diff is confined to the new preferences slice; verifier check 16 and
the baseline-restore check (18) prove zero impact on frozen tables.

## 13. HARD STOP

Phase 10D is complete and verified. **No commit was made.** Phase 10E and
Phase 11 are **NOT** started.