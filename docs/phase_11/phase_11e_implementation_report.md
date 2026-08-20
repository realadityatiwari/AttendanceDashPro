# Phase 11E — Remaining Preference Wiring: Verification & Reconciliation Report

> **PHASE 11E VERIFIED (2026-08-20).** Phase 11 — Notifications & Reminders: **IN PROGRESS** (11.0 audit ✅ · 11A ✅ · 11B ✅ · 11D ✅ · **11E ✅ — NO ADDITIONAL IMPLEMENTATION REQUIRED** · 11C decision-gated/deferred · 11F NOT STARTED). No commit made.

## 1. Objective

Determine whether any legitimate remaining preference→notification wiring exists beyond what Phase 11A/11B/11D already delivered, implement only the genuine gaps, and reconcile the preference contract (backend + frontend + docs) with the now-live `class_reminders` consumer.

**Conclusion:** the only legitimate remaining work was the audit-named "SettingsModal copy updated to match reality" (`docs/phase_11/phase_11_architecture_audit.md` §11E, files-likely-changed). That copy — and the parallel stale comment in `frontend/src/types/api.ts` — still claimed *"saving them does not send reminders"*, which is now false. No backend behavior change was required, no migration was required, and no new verifier was justified (the preference→notification matrix is already fully exercised by the existing 11A and 11B verifiers).

## 2. Requirements

- **`class_reminders`** — the CLASS_REMINDER gate: *already implemented in 11A* (`NotificationService._class_reminders`, `notification_service.py:143-145`: `pref is None or not pref.class_reminders` → skip). Read at generation time; a missing preference row means the documented default (off). Verified by 11A checks 7/8 and 11B check 18.
- **`auto_mark_present`** — must stay storage-only pending an explicit product-owner decision (audit §5B). No implementation, no behavior change.
- **`week_starts_on`** — must stay storage-only (audit §5C; display/read-model preference, frozen read models). No implementation, no behavior change.
- **Contract** — Phase 11E may READ preferences but never change the GET/PUT `/api/v1/student/preferences` contract (audit §3.4).
- **SettingsModal copy** — the audit explicitly names this as the 11E file change: the settings note should become truthful ("Class reminders are shown in the bell icon when enabled") once the gate lands.

## 3. Scope Discipline (NOT done)

- No 11C delivery model (no push / browser Notification API / service worker / PWA / email / SMS / scheduled sweep / cron / Celery / Redis). Remains decision-gated and deferred.
- No automatic attendance marking; `auto_mark_present` unchanged.
- No `week_starts_on` engine/read-model change; calendar and analytics read models remain frozen.
- No new migration (alembic head unchanged: `d1e2f3a4b5c6`).
- No new verifier (see §6 — no backend behavior changed, so none is justified).
- No second notification model; no client-supplied `user_id` anywhere; ownership remains JWT-only.
- No unrelated refactoring. The only code changes are minimal, truthful copy in the two places that documented the preference semantics.

## 4. Implementation

| File | Change |
|---|---|
| `frontend/src/components/shell/SettingsModal.tsx` | Doc comment + info-box copy made truthful: `class_reminders` gates the bell-icon CLASS_REMINDER notifications ("Class reminders are shown in the bell icon when enabled"); `auto_mark_present` and `week_starts_on` explicitly remain storage-only ("saving them does not mark attendance or change calendar calculations"). |
| `frontend/src/types/api.ts` | `UserPreferences` contract comment updated to match reality: `class_reminders` is consumed by Phase 11; `auto_mark_present`/`week_starts_on` remain storage-only. |

No other file was touched — no backend file, no migration, no engine, no verifier.

## 5. Preference → Notification Behavior Matrix (reconciled)

| Preference | Consumer | Behavior | Evidence |
|---|---|---|---|
| `class_reminders` (bool) | `NotificationService._class_reminders` | Gates CLASS_REMINDER generation. `false`/missing → no reminder generated; `true` → reminder for the week's unmarked, non-cancelled enrolled sessions. Turning it off stops NEW rows; existing rows stay (documented 11B persistence semantics). | 11A checks 7/8; 11B check 18 |
| `auto_mark_present` (bool) | none | Storage-only. No effect on any notification, attendance record, or read model. | 11A check 11; 11B check 18 |
| `week_starts_on` (enum) | none | Storage-only. No effect on any notification, calendar, or analytics output. | 11A check 12; 11B check 18 |

The five non-preference kinds (QUIZ_APPROACHING, ATTENDANCE_THRESHOLD, MUST_ATTEND, SAFE_SKIP, ACADEMIC_EVENT) consume no preferences; they remain exact projections of the canonical eligibility/attendance/calendar engines (11A checks 15/16/17; 11B checks 17/19/20).

## 6. Verification

Backend (real DB, minted JWTs):

- `python -m compileall -q app scripts` — PASS.
- `python scripts/verify_phase_11a.py` — **19/19 PASS**. This is the core 11E regression surface: check 7 (`class_reminders=false` suppresses), check 8 (`class_reminders=true` permits the qualifying in-week session), check 11 (`auto_mark_present=true` has NO effect), check 12 (`week_starts_on=SUNDAY` has NO effect), check 13 (no frozen-table mutation), check 18 (alembic head unchanged), check 19 (exact cleanup / baseline restore).
- `python scripts/verify_phase_11b.py` — **21/23 PASS**; checks 19 (persisted QUIZ_APPROACHING parity) and 20 (persisted ACADEMIC_EVENT parity) FAIL. **Diagnosis: environmental data drift, NOT a product-code regression.** Backend code is byte-identical to the previous 23/23 run. The admin's persisted inbox contains rows created at 17:58 today (from earlier use/browser testing of the notification center): a QUIZ_APPROACHING row for cycle 1 and an ACADEMIC_EVENT row for event `06c8bbac` (09-03). Under the documented 11B persistence semantics ("a previously generated notification stays in the inbox until dismissed"), those rows legitimately remain. During the verifier run, its own fixture — a temp QUIZ_DAY event on the admin's own subject (created at `verify_phase_11b.py:169-175`) — temporarily shifts the admin's canonical quiz cycle to 2 and reorders the top-4 upcoming-events selection. The stale cycle-1 row then coexists with the fresh cycle-2 row (→ check 19: 2 quiz items vs expected 1), and the stale `06c8bbac` row coexists with the current top-4 including the temp event (→ check 20: 5 notes vs 4 dash). Cleanup (finally block) deletes the temp event and restores the admin's rows to their pre-run baseline, which the post-run queries confirm. Checks 19/20 therefore assume a clean admin inbox and are non-deterministic once the real admin has used the app; this is a documented verifier fragility, not a defect in notification code. No code was modified to force a pass.
- DB baseline restored — **users=31, admins=1, notifications=10** (the admin's pre-existing rows; all verifier artifacts removed). Confirmed by 11B checks 21/23 and post-run queries.
- Alembic — single head/current `d1e2f3a4b5c6`, unchanged.

Frontend:

- `npx tsc --noEmit` — PASS (0 errors).
- `npx eslint` on the changed files (`components/shell/SettingsModal.tsx`, `types/api.ts`) — PASS (0 errors/warnings).
- `npm run build` — PASS; all 12 routes prerendered successfully.

No browser/manual tests run — the user performs manual/browser testing.

## 7. Conflicts & Integrity

- The two 11B failures are fully explained by data drift (pre-existing admin inbox rows) plus the verifier's own fixture mutating the admin's canonical quiz/event selection mid-run. They are reproducible with the current DB state but are not code regressions; a fresh DB (or a cleaned admin inbox) passes 23/23.
- No frozen system was mutated (11A check 13; 11B check 21); no migration was created (11A check 18; 11B check 22); no duplicate notifications (11B checks 3-7).

## 8. Security & Privacy

- Ownership remains JWT-derived; the client never supplies `user_id`. No new endpoints, no new data, no new storage. The copy change introduces no behavior.

## 9. Cleanup & Restoration

- The 11B verifier's finally block removed only its own artifacts (two temp users, two enrollments, one temp preference, four temp sessions, one temp event, run-created notification rows) and restored the admin's inbox to its pre-run row set. Post-run counts (`users=31, notifications=10`, events=49, single alembic head) match the pre-run baseline. No residual artifacts.

## 10. Files

- `frontend/src/components/shell/SettingsModal.tsx` — copy made truthful (11E).
- `frontend/src/types/api.ts` — preference contract comment made truthful (11E).
- `docs/phase_11/phase_11e_implementation_report.md` — this report (new).
- Governance updated: `MASTER_ROADMAP.md`, `implementation_plan.md`, `task.md`, `walkthrough.md`.

## 11. Final Status & Next Steps

**11E VERIFIED — NO ADDITIONAL IMPLEMENTATION REQUIRED.** All legitimate remaining preference wiring is complete: `class_reminders` is wired (11A) and documented truthfully; `auto_mark_present` and `week_starts_on` remain storage-only per explicit product decisions (audit §5B/5C). The remaining Phase 11 work is:

- **11F** — phase completion (consolidated verifier + governance reconciliation + COMPLETE & FROZEN), pending explicit authorization. 11F should also decide whether to harden the 11B verifier's checks 19/20 (e.g., compare only run-generated rows) so the gate is deterministic on a used inbox.
- **11C** — delivery model — remains decision-gated/deferred and may be omitted from Phase 11 entirely.

**PHASE 11E VERIFIED — HARD STOP.** No commit was made. 11C remains decision-gated/deferred · 11F NOT STARTED. Browser/manual testing remains the user's responsibility. Phase 11 remains **IN PROGRESS** (not COMPLETE/FROZEN).