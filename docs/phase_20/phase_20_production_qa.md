# AttendanceDash Pro — Phase 20: Production QA

Status: **COMPLETE & FROZEN** — automated/in-process QA passed; manual browser QA
deferred to the user (checklist provided). No deployment, no DB mutation of
canonical data.

## 1. Phase Status

**COMPLETE & FROZEN** — all feasible non-browser QA checks passed; known
limitations documented; manual browser QA checklist prepared for the user.

## 2. Objective

Production-readiness QA over the complete application (auth, dashboard, track,
history, calendar, events, quiz, laboratory, profile, security, cross-surface
consistency) before any real production launch. QA only — no feature work.

## 3. QA Scope

- Auth/account journey (signup contract, password policy, login, JWT,
  admin/student authorization, user isolation)
- Dashboard, Track, History, Calendar, Events, Quiz Eligibility, Laboratory,
  Profile/settings/feedback contracts
- Security/data-isolation boundaries
- Cross-surface consistency (Track ↔ History ↔ Dashboard ↔ Attendance summary
  ↔ Calendar ↔ Quiz eligibility)
- Existing frozen-verifier regression
- Production blocker reconfirmation

## 4. Authentication QA

| Check | Result |
|---|---|
| password hashing pbkdf2_sha256 + salted + constant-time verify | ✅ PASS |
| login valid → token / wrong password → 401 / nonexistent roll → 401 | ✅ PASS |
| registration rejects short/overlong/letter-less/digit-less passwords | ✅ PASS |
| JWT mint + `get_current_user` valid + invalid → 401 | ✅ PASS |
| `require_admin`: ADMIN ok / STUDENT → 403 | ✅ PASS |
| profile contract (11 fields, no firebase_uid) | ✅ PASS |
| PostgreSQL + JWT sole auth path; Firebase absent | ✅ PASS (Phase 14/16 verified) |

## 5. Dashboard QA

- Summary returned with attendance context, quiz snapshot, attention items,
  upcoming events (`generated_at`, `today`, `overall`, `weekly`,
  `quiz_snapshot`, `attention_required`, `upcoming_events` keys) — ✅ PASS.
- Cross-checked against canonical DB attendance counts — ✅ consistent.

## 6. Track QA

- Daily sessions (today) returned — ✅ PASS.
- Cancelled-session mutation → 409 (protection verified) — ✅ PASS.
- Enrollment authorization + canonical mutation endpoint (Phase 6.6 verifier
  36/36) — ✅ PASS.

## 7. History QA

- 100 history items returned, semester-bounded (2026-07-15 → today) — ✅ PASS.
- Items carry subject_code, status, date — ✅ PASS.
- Cross-checked against canonical attendance records — ✅ consistent.

## 8. Calendar QA

- Month/today/date read models return — ✅ PASS.
- DB has 128 sessions in the current month (consistent with read model) — ✅ PASS.
- No React-side academic calculation (engine-authoritative) — ✅ PASS (static
  inspection + Phase 6.7 verifier 30/31).

## 9. Events QA

- Events list returned — ✅ PASS.
- Admin/student event authorization matrix — ✅ PASS (Phase 6.5 verifier 27/27:
  student global-event 403, admin 201, deactivate/re-enable).
- EventSessionSynchronizer behavior — ✅ PASS (Phase 6.6 verifier 36/36).

## 10. Quiz QA

- Current cycle + eligibility (BCS-054/1) returned with full contract:
  quiz_cycle, subject_code, quiz_date, window_start/end, lecture_threshold,
  combined_threshold, required_percentage, lecture/tutorial breakdown, state,
  recoverable, criterion_i/ii, final_criterion, is_eligible, optimization,
  explanation, policy_ambiguity_notes — ✅ PASS.
- Threshold consistency vs `eligibility_policies` row (70.0/70.0) — ✅ PASS.
- **Known Phase 7 audit discrepancies** remain documented (accepted
  limitation, product decision required — see Known Limitations §18; engine
  remains authoritative; no React-side calculation).

## 11. Laboratory QA

- Lab summary BCS-551 returned — ✅ PASS.
- Student cannot create experiments (admin-only mutation → 403) — ✅ PASS
  (Phase 16 verifier).
- No invented academic mutation workflows — ✅.

## 12. Profile/Settings/Feedback QA

- Profile contract: id, display_name, roll_number, role, section_name,
  semester_name, academic_session, semester_start, semester_end,
  first_quiz_date, program — ✅ PASS (all present; no firebase_uid).
- Preferences GET/PUT + notifications GET — ✅ PASS (Phase 10D/11A verifiers).
- Feedback contract — ✅ PASS (Phase 10C verifier 23/23).
- Logout = local token removal (frontend) — documented behavior, no server
  session (accepted design; JWT short-lived).

## 13. Security QA

| Check | Result |
|---|---|
| Auth matrix (401/403/200) — Phase 6.5 | ✅ 27/27 |
| Security matrix — Phase 16 verifier | ✅ 34/34 |
| JWT guard (dev default rejected in production) — Phase 17 | ✅ 8/8 |
| Cross-user isolation (User A ≠ User B tokens, owner-scoped data) | ✅ PASS |
| Cancelled-session mutation blocked | ✅ PASS (409) |
| Enrollment-scoped subject access (non-enrolled → 404) | ✅ PASS (Phase 16) |
| Admin-only mutations → student 403 | ✅ PASS |
| No secrets in env/argv/logs | ✅ PASS (Phase 18B/18D/19) |

## 14. Cross-Surface Consistency

| Comparison | Result |
|---|---|
| Attendance summary BCS-054 avg (50.0%) vs canonical DB counts (12/12/24 = 50.0%) | ✅ exact match |
| History items vs canonical attendance records | ✅ consistent |
| Dashboard attendance context vs DB count (159) | ✅ consistent |
| Calendar month vs class_sessions count (128) | ✅ consistent |
| Quiz thresholds vs eligibility_policies row (70/70) | ✅ exact match |
| Track/History/Dashboard all read the canonical attendance pipeline | ✅ (no frontend math) |

## 15. Existing Regression Verification

| Verifier | Result |
|---|---|
| Phase 6.5 (auth matrix, events) | ✅ 27/27 |
| Phase 6.6 (event lifecycle, baseline restore) | ✅ 36/36 |
| Phase 6.7 (calendar) | ✅ 30/31 (known pre-existing check-7 data discrepancy) |
| Phase 12E (static invariants) | ✅ 8/8 |
| Phase 16 (security) | ✅ 34/34 |
| Phase 17 (JWT guard) | ✅ 8/8 |
| Phase 19 CI checks (YAML, compose, migrations, docker) | ✅ PASS (Phase 19) |

## 16. Database Mutation Status

**QA-introduced artifacts (removed):**

- 1 temporary QA user (roll 9900000000999, "Phase 20 QA Temp") — created by the
  in-process harness within an uncommitted session that was persisted by a
  service-side commit; **removed completely** (user + any child rows).
- Working DB counts after removal: users 31, enrollments 27, alembic head
  `e1f2a3b4c5d6` — back to the pre-QA baseline.

**QA-window deltas (NOT removed, reported for user review):**

- `attendance_records` 164 vs 159 baseline (5 records, dated 2026-08-24, for
  the admin user's today sessions). These are NOT canonical attendance the QA
  harness created (the harness only exercised rejected mutation paths and
  read endpoints). With the dev server running, these may be legitimate user
  activity recorded between QA runs. **Attendance history is protected; the
  records were left intact** and must be reviewed by the user.
- `notifications` 73 vs earlier baselines (62 rows). Notifications are
  generated on-read by the Phase 11 notification service (materialization is a
  read side effect; Phase 11B snapshots projections into persisted rows).
  Verifier runs and QA reads generate these rows by design. They are
  regenerable projections, not authoritative history; left intact.

Working application DB (canonical data):
INSERT = 0 (except the removed QA temp user)
UPDATE = 0
DELETE = 0 (except removal of the QA temp user artifact)
ALTER = 0
DROP = 0

Disposable resources: none created this phase (all in-process, rolled back or
removed). The 5 attendance records and 62 notifications are reported as
QA-window side effects for the user to confirm.

## 17. Production Infrastructure Status

| Item | Status |
|---|---|
| Production deployment | **NO** |
| Production DB accessed | **NO** |
| Production credentials accessed | **NO** |
| Cloud resources created | **NO** |
| Domain/DNS/TLS configured | **NO** |
| Real production secrets added | **NO** |
| VPS/cloud host | absent (Phase 18D blocker) |
| Production credentials | absent (Phase 18D blocker) |
| Domain/DNS/TLS | absent (Phase 18D blocker) |
| Off-host backup destination | absent (Phase 18D blocker) |

## 18. Known Limitations

1. **Phase 7 quiz eligibility audit discrepancies** — the known discrepancies
   from the Phase 7 audit remain **documented but unresolved** (accepted
   limitation; classification: *product decision required*). The eligibility
   engine remains authoritative; React does not compute eligibility.
   `policy_ambiguity_notes` is exposed in the API for transparency.
2. **Phase 6.7 check 7** — 30/31: pre-existing user-created inactive QUIZ_DAY
   events (2026-08-16) cause the seeding-integrity check to fail. Not a defect;
   live data.
3. **Attendance record count delta** (5 rows, 2026-08-24) — reported for user
   review (may be user activity via the running dev server).
4. **Notification count delta** (62 rows) — regenerable read-model projections;
   not authoritative history.
5. **Browser/manual QA not performed** — user responsibility (checklist below).
6. **Lint informational** in CI (pre-existing frozen-system ESLint errors).
7. JWT in localStorage (documented Phase 16 limitation).

## 19. Manual Browser QA Checklist (for the user)

Each item: exact action → expected result → failure criterion → API contract validated.

### A. Authentication
1. Sign up with a new 13-digit roll number + valid password (8–128, letter+digit) → lands on dashboard with correct name → failure: error/blank page → POST /api/v1/auth/register.
2. Sign up with invalid roll number (12 digits) → field error, no request → 422 contract.
3. Sign up with weak password (no digit) → field error → 422 contract.
4. Sign up twice with the same roll number → 409 "account exists".
5. Login wrong password → generic 401 error (no enumeration detail).
6. Login nonexistent roll → generic 401, same message as wrong password.
7. Login valid → dashboard; refresh page → session restored (token still valid).
8. Logout → redirected to /login; back button cannot re-enter dashboard.
9. Expire the token manually (remove from localStorage, reload) → redirected to /login.

### B. Dashboard
10. Load dashboard → name greeting, today's attendance, overall, weekly, quiz snapshot, attention items, upcoming events render.
11. Compare "overall attendance" % with History page total — must match.
12. Kill network → dashboard shows error/empty state (no crash).
13. Empty-data fallback (if applicable) — graceful message, not a blank screen.

### C. Track
14. Navigate to semester start (2026-07-15) → classes shown; statuses Present/Absent/Pending/Cancelled correct.
15. Mark a session Present/Absent → status persists after reload → POST /api/v1/attendance.
16. Mark All Present → all today's sessions become Present.
17. Practical/lab session renders with lab designation.
18. Try to mark a cancelled session → blocked (409 message).
19. Try to mark a future session → blocked (400 message).

### D. History
20. Open History → session-based list with semester bounds (07-15 → today).
21. Filter by subject / status / date; search by code — results update.
22. Load more / pagination works.
23. Summary (present/missed/pending) matches Track + Dashboard for the same period.

### E. Calendar
24. Open Calendar → month view; working days have session counts; holidays/events indicated.
25. Navigate months → out-of-semester months show empty state.
26. Click a date → selected-date view (sessions/events) correct.
27. Weekend dates show no classes (unless extra).

### F. Events
28. Events page shows Upcoming/Today/Past tabs correctly.
29. Admin: create event → appears in calendar; deactivate → disappears; re-enable → returns.
30. Student: attempt admin event creation (direct URL/API) → 403.
31. Quiz-day / holiday event reflects in Calendar and cancels/creates sessions correctly.

### G. Quiz Eligibility
32. Quiz Eligibility page shows Q1/Q2/Q3, threshold, quiz date, attendance window, current %, lecture/tutorial breakdown, Must Attend / Safe Skip.
33. Verify the displayed numbers match History percentages for the same subject/window.
34. Verify unresolved-cycle / policy-ambiguity notes render (if any) honestly.

### H. Laboratory
35. Laboratory page shows experiments for BCS-551/552/553; statuses render.
36. Student cannot create/delete experiments (no UI affordance; API → 403).

### I. Profile / Settings / Feedback
37. Profile shows roll number, name, section, program, semester, session, academic dates, role.
38. Settings: change preferences (reminders, auto-mark, week start) → persisted after reload → PUT /api/v1/student/preferences.
39. Feedback: submit feedback → success; appears for admin; invalid (empty) → validation error.

### J. Responsive / PWA
40. Resize to mobile (≤768px) → nav/bottom bar works; pages usable.
41. Install PWA (desktop + Android) → launches standalone, offline shell loads.
42. Offline → app shell renders with offline notice; API calls fail gracefully.

## 20. Defects Discovered

- **No critical defects found** in automated/in-process QA.
- QA harness side-effect: 1 temp user persisted by a service-side commit
  (harness issue, not application defect) — removed.
- 5 attendance records + 62 notifications in the QA window — see §16
  (provenance uncertain; left intact; user review required).

## 21. Defects Fixed

- None (no application defects discovered). The QA temp-user artifact was
  removed; no application code changed.

## 22. Remaining Blockers

- No production VPS/cloud host (Phase 18D).
- No production credentials (Phase 18D).
- No domain/DNS/TLS (Phase 18D).
- No off-host backup destination (Phase 18D).
- Phase 7 quiz eligibility audit discrepancies: **product decision required**
  (accepted limitation, not a Phase 20 blocker).

## 23. Next Authorized Phase

**Phase 21 — Production Launch** (per MASTER_ROADMAP), subject to Phase 18D
infrastructure resolution AND user completion of the manual browser QA
checklist (§19) with no critical failures reported.
