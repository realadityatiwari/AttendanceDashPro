# AttendanceDash Pro — Phase 14.0 Firebase Retirement Architecture Audit

Date: 2026-08-23 · Scope: READ-ONLY repository-wide audit · Status: **COMPLETE**

> This audit was conducted read-only: no code changed, no database mutated, no
> migration run, no commit made. Its purpose was to determine exactly what remains
> dependent on Firebase and what Phase 14 must remove.

---

## 1. Executive Verdict

**Phase 14 is ready to proceed.** The runtime architecture is already fully migrated
to JWT + PostgreSQL. Firebase exists only as:

- **Inert frontend SDK initialization** (dead import chain, side-effect only)
- **Inert backend Admin SDK initialization** (no-op without credentials; no verification calls)
- **Legacy deployment/config files** (`firebase.json`, `.firebaserc`, `firestore.rules`, `firestore.indexes.json`)
- **Legacy root app** (`index.html`, `js/firebase.js`, `js/auth.js`, `js/storage.js` — a separate pre-migration codebase)
- **Historical documentation** (stale tech-stack, architecture, and migration docs)
- **Historical migration scripts** (`migrate_extract.py`, `migrate_execute.py`, `diagnose_failures.py`)
- **Database column `firebase_uid`** (nullable, data-migration legacy, no current runtime reads)

**No Firebase authentication path is reachable at runtime.** The frontend login/signup
uses `POST /api/v1/auth/login` and `/register` (JWT in/out). The backend `deps.py`
decodes PyJWT with `settings.JWT_SECRET_KEY` and loads the user from PostgreSQL. Zero
Firebase Auth calls are made. No Firestore reads or writes occur from the Next.js
application code.

---

## 2. Current Authentication Architecture

**Frontend (Next.js):**
- Login → `POST /api/v1/auth/login` (roll_number + password) → `access_token` → `localStorage`
- Signup → `POST /api/v1/auth/register` (name + roll_number + password) → `access_token` → `localStorage`
- `AuthContext` → reads `access_token` from `localStorage` → hydrates via `GET /api/v1/student/me`
- `apiFetch()` → reads `access_token` from `localStorage` → attaches `Bearer <token>`
- `logout` → removes `access_token` → redirects to `/login`
- Firebase SDK loaded but **never used** for authentication; no `onAuthStateChanged`,
  `signInWithEmailAndPassword`, `createUserWithEmailAndPassword`, or `getAuth` calls
  in any Next.js page/component

**Backend (FastAPI):**
- `POST /api/v1/auth/login` → query `users` by `roll_number` → verify `pbkdf2_sha256`
  `hashed_password` → issue PyJWT via `create_access_token(subject=user.id, ...)`
- `POST /api/v1/auth/register` → validate → create `User` with `firebase_uid=None` → enroll → issue PyJWT
- `get_current_user()` (deps.py) → decode PyJWT with `settings.JWT_SECRET_KEY` → extract
  `sub` as UUID → query PostgreSQL `User` by `id` → return user
- `require_admin()` → verify `current_user.role == UserRole.ADMIN`
- No Firebase Admin verification (`auth.verify_id_token()`) is ever invoked; no
  `firestore.client()` is ever called at runtime

**Result: JWT + PostgreSQL is the sole authoritative auth path. Firebase Auth is not reachable.**

---

## 3. Firebase Runtime Dependency Audit

### Frontend (Next.js) — Live but Inert

| File | Class | Detail |
|---|---|---|
| `frontend/src/lib/firebase.ts` | A — LIVE (inert) | Module-level `initializeApp` + `getAuth` when `NEXT_PUBLIC_FIREBASE_API_KEY` set; no Firebase API ever called after init |
| `frontend/src/lib/api.ts` (line 1) | B — DEAD IMPORT | `import { auth } from "./firebase"` — `auth` never referenced in body; import triggers the init side-effect |
| `frontend/.env.local` | A — LIVE CONFIG | Real Firebase project credentials consumed by `firebase.ts` |
| `frontend/.env.example` | F — CONFIG | Firebase env var placeholders |
| `frontend/package.json` | A — LIVE DEPENDENCY | `"firebase": "^12.17.1"` — installed, whole SDK bundled |

### Backend — Live but Inert

| File | Class | Detail |
|---|---|---|
| `backend/app/core/firebase.py` | A — LIVE (inert) | Imports `firebase_admin`; initializes Admin SDK only if `FIREBASE_SERVICE_ACCOUNT_PATH`/`GOOGLE_APPLICATION_CREDENTIALS` set; no verification/Firestore calls |
| `backend/app/main.py` | A — LIVE (inert) | `from app.core.firebase import initialize_firebase` (hard import); call result discarded |
| `backend/requirements.txt` | A — LIVE DEPENDENCY | `firebase-admin>=6.5.0` — installed in `.venv` (v7.5.0); removing the import without removing the package entry breaks startup |
| `backend/.env` | N/A | No Firebase env vars present |

### Runtime impact

Removing both would change **no runtime behavior** — JWT auth works identically.
Frontend gains a smaller bundle; backend loses the startup CRITICAL log line when
credentials are absent.

---

## 4. Frontend Firebase References

### Next.js application (`frontend/src/`)

| File | Lines | Class | Detail |
|---|---|---|---|
| `frontend/src/lib/firebase.ts` | 1–26 | A — LIVE (inert) | SDK initialization |
| `frontend/src/lib/api.ts` | 1 | B — DEAD | `import { auth } from "./firebase"` — unused |
| `frontend/src/types/api.ts` | 3 | C — DATA LEGACY | `firebase_uid: string \| null` |
| `frontend/src/contexts/AuthContext.tsx` | 10 | C — DATA LEGACY | `firebase_uid: string \| null` |
| `frontend/src/app/(authenticated)/profile/page.tsx` | 41, 129 | C — DATA LEGACY | Stale error message; displays `firebase_uid` |
| `frontend/.env.local` | 2–7 | A — LIVE CONFIG | Real Firebase credentials |
| `frontend/.env.example` | 2–7 | F — CONFIG | Placeholders |

### Legacy root application (not Next.js)

`index.html` (Firebase compat CDN scripts), `js/firebase.js`, `js/auth.js`,
`js/storage.js`, `js/app.js` (`onAuthStateChanged`), `js/feedback.js`,
`js/events-controller.js`, root `service-worker.js` (bypasses Firebase hosts, caches
`js/firebase.js`), root `manifest.json`, `offline.html` — all **D — LEGACY**. A separate
pre-migration codebase, not part of the current runtime.

---

## 5. Backend Firebase References

### Runtime application (`backend/app/`)

| File | Lines | Class | Detail |
|---|---|---|---|
| `backend/app/core/firebase.py` | 1–31 | A — LIVE (inert) | Admin SDK init; no verification/Firestore |
| `backend/app/main.py` | 5, 7–8 | A — LIVE (inert) | Import + call at startup |
| `backend/app/models/user.py` | 23–25 | C — DATA LEGACY | `firebase_uid` nullable, unique index |
| `backend/app/schemas/student.py` | 12–14, 19 | C — DATA LEGACY | `firebase_uid` in `StudentProfile` |
| `backend/app/api/v1/endpoints/student.py` | 19, 36, 58 | C — DATA LEGACY | Returns `firebase_uid` in `/sync`, `/me` |
| `backend/app/api/v1/endpoints/auth.py` | 111 | C — DATA LEGACY | `firebase_uid=None` on register |
| `backend/app/repositories/user_repo.py` | 17–22 | B — DEAD CODE | `get_by_firebase_uid()` — never called by runtime code |

### Legacy scripts (`backend/scripts/`)

`migrate_extract.py` (E — migration tool, reads Firestore), `migrate_execute.py`
(E — writes `firebase_uid=uid` for legacy users), `diagnose_failures.py` (E — legacy
diagnostic), `set_initial_password.py` (E — queries by hardcoded `firebase_uid`),
`setup_single_user.py` (E — queries by hardcoded `firebase_uid`).

### Alembic

`7117a007a0da_initial_schema.py` (creates `firebase_uid` NOT NULL + unique index),
`c3d4e5f6a7b8_make_firebase_uid_nullable.py` (nullable; Phase 14 owns eventual removal).

---

## 6. Database / firebase_uid Audit

- **Schema**: `users.firebase_uid` VARCHAR nullable, unique index `ix_users_firebase_uid`
- **FK references**: none
- **Runtime reads**: none (only legacy scripts `set_initial_password.py`,
  `setup_single_user.py`; `user_repo.get_by_firebase_uid` is uncalled dead code)
- **Runtime writes**: `auth.py` register writes `firebase_uid=None`
- **API exposure**: returned in `/student/sync` and `/student/me`; mirrored in frontend
  `types/api.ts`, `AuthContext.tsx`, and displayed on the profile page
- **Required for JWT?** **NO** — JWT `sub` is `user.id` (UUID)
- **Verdict**: **SAFE TO REMOVE** with migration (Phase 14D) after legacy scripts are
  switched to `roll_number` lookups. Proposed migration: drop column + unique index;
  remove from model, schema, endpoints, frontend types, and profile page.

---

## 7. Firestore / Data Dependency Audit

**No application data is read from or written to Firestore by the current runtime.**
All domains (attendance, users, profile, preferences, feedback, events, timetable,
quiz schedules, notifications, laboratory, history, analytics) are PostgreSQL-only.
The only Firestore client code lives in `backend/scripts/` (migration/diagnostic tools)
and `js/` (legacy root app).

---

## 8. Dependency Manifest Audit

- **Frontend** (`frontend/package.json`): `firebase@^12.17.1` — imported only via
  the dead `api.ts` import; **SAFE TO REMOVE** (14A)
- **Backend** (`backend/requirements.txt`): `firebase-admin>=6.5.0` — imported by
  `app/core/firebase.py` from `main.py`; **SAFE TO REMOVE** after removing that module (14B)

---

## 9. Deployment / Configuration Audit

| Artifact | Status |
|---|---|
| `firebase.json` | Obsolete — SAFE TO REMOVE |
| `.firebaserc` | Obsolete — SAFE TO REMOVE |
| `firestore.rules` | Obsolete — SAFE TO REMOVE |
| `firestore.indexes.json` | Obsolete — SAFE TO REMOVE |
| `.gitignore` Firebase entries | Obsolete — SAFE TO REMOVE |
| Firebase prompts (`prompts/14_*`, `19_*`, `11_RELEASE_CHECKLIST.md`) | Obsolete — SAFE TO REMOVE/archive |
| CI/CD | None exists |

---

## 10. Test / Verifier Audit

No `verify_phase_*.py` script references Firebase. Firebase test references are limited
to legacy/scratch files for the legacy root app (`js/test-persistence-sync.js`,
`test-e2e.js`, `scratch_pwa_*`). `backend/tests/test_attendance_engine.py` has no
Firebase reference.

---

## 11. Documentation Audit

Stale Firebase claims requiring Phase 14F reconciliation: `docs/02_TECH_STACK.md`,
`docs/03_FOLDER_STRUCTURE.md`, `docs/04_ARCHITECTURE.md`, `docs/10_STORAGE_AND_SYNC.md`,
`docs/12_PWA_AND_DEPLOYMENT.md`, `docs/13_CODING_STANDARDS.md` (line 158),
`docs/14_TESTING_AND_QA.md`, `docs/18_ARCHITECTURE_DECISION_RECORDS.md`,
`docs/19_DEPENDENCY_GRAPH.md`, `docs/20_DATA_DICTIONARY.md`, `docs/21_CHANGELOG.md` (line 160),
`docs/README.md`, `docs/phase_12/phase_12_architecture_audit.md` (line 271),
`docs/phase_11/phase_11_architecture_audit.md` (line 362),
`docs/phase_4_5_data_audit.md` (line 138 — "no Firebase JS SDK" now outdated),
`backend/API_DESIGN.md` (claims 501 Firebase verification), `backend/DATABASE_DESIGN.md`,
`backend/MIGRATION_NOTES.md`, root `README.md`.

Historical reports (`docs/phase_4_5_data_audit.md`, `docs/phase_10_completion_audit_report.md`,
migration reports) must **not** be rewritten to look current.

---

## 12. Firebase Removal Dependency Graph

```
14A — Frontend: api.ts dead import → delete firebase.ts → package.json → lockfile → env vars
14B — Backend: delete firebase.py → main.py import → requirements.txt → uninstall
14C — Deployment/config: firebase.json, .firebaserc, firestore.rules/indexes, .gitignore, prompts
14D — firebase_uid: legacy script updates → Alembic drop → model/schema/API/frontend types
14E — Regression: auth/data-path verification
14F — Freeze + governance/doc reconciliation
```

---

## 13. Proposed Phase 14 Sub-Phases

| Sub-phase | Scope | Risk |
|---|---|---|
| 14A | Frontend Firebase removal | Low |
| 14B | Backend Firebase removal | Low |
| 14C | Deployment/configuration cleanup | Very low |
| 14D | `firebase_uid` column removal + API/model cleanup | Medium (script updates first) |
| 14E | Full regression verification | None |
| 14F | Freeze + governance reconciliation | Very low |

Recommended order: 14A → 14B → 14C → 14D → 14E → 14F. 14A–14C parallelizable; 14D
depends on the earlier slices.

---

## 14. Risks / Migration Hazards

- Frontend build breaks if `firebase` removed before `api.ts` import cleaned (Low — fixed by ordering)
- Backend startup fails if `firebase-admin` removed before `main.py` import cleaned (Low — fixed by ordering)
- `firebase_uid` drop breaks legacy scripts (Medium — update scripts to `roll_number` first)
- Migration `c3d4e5f6a7b8` downgrade would fail after a drop (Low — document irreversibility)
- Legacy root app is a separate codebase; Phase 14 may optionally archive it (None)

---

## 15. Frozen Systems

Not impacted by Phase 14: attendance engine/calculations, eligibility engine, calendar
engine, event/session synchronization, cancellation lifecycle, quiz-day protection,
laboratory semantics, dashboard calculations, analytics, history, notification
contracts, Phase 11 behavior, Phase 12 responsive/mobile behavior, Phase 13 PWA behavior.

---

## 16. Recommended Smallest Safe Implementation Slice

**Phase 14A** — frontend Firebase dependency removal (4 tracked files + 2 gitignored env
files): remove dead import in `api.ts`, delete `firebase.ts`, uninstall `firebase` npm
package, remove `NEXT_PUBLIC_FIREBASE_*` env vars. Verify with `tsc`, `build`,
`git diff --check`, and a Firebase source search.

---

## 17. Verification Requirements

Per sub-phase: `npx tsc --noEmit` PASS, `npm run build` PASS, `python -m compileall`
PASS, single linear Alembic head, all `verify_phase_*` scripts PASS, login/register/
profile flows PASS. After 14D additionally: JWT `sub` is `user.id` (never
`firebase_uid`), API responses free of `firebase_uid`, legacy scripts use
`roll_number`.

---

## 18. Final Readiness Verdict

**Phase 14 ready to proceed.** The entire Firebase removal can be executed without
touching any frozen system. Frontend and backend Firebase dependencies are inert;
`firebase_uid` is safe to remove (14D) after script updates; deployment/config files
and documentation are stale but non-functional.

**Phase 14.0 = COMPLETE. Phase 14A+ = NOT STARTED (at audit time).**
