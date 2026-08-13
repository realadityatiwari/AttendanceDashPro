# AttendanceDash Pro — Master Roadmap

> **Project Source of Truth**
>
> This document defines the direction, phase structure, priorities, architectural boundaries, and production path for AttendanceDash Pro.
>
> **Current position:** Phase 4.5 complete (audit ✅ · Track ✅ · Sign Up ✅) → **Phase 5 (Attendance History) is next**.

---

## 🧭 Project Direction

AttendanceDash Pro is being developed as a real, production-ready attendance intelligence platform — not merely a polished frontend.

The standard for completion is:

```text
UI
 ↓
API
 ↓
Service
 ↓
Repository
 ↓
Database
 ↓
Engine
 ↓
Calculated Result
```

Every layer must agree.

A page appearing to work is **not** sufficient evidence that the feature works.

---

# 📍 Current Status

| Phase | Area | Status |
|---|---|---|
| 0 | Architecture & Reality Audit | 🟢 Complete / Frozen |
| 1 | Design System Foundation | 🟢 Complete / Frozen |
| 2 | Desktop Shell & Global UX | 🟢 Complete / Frozen |
| 3 | Home Dashboard | 🟢 Complete / Frozen |
| 4 | Track Attendance | 🟢 Complete / Frozen |
| 4.5 | Data Integrity & Account Foundation | 🟢 Complete / Frozen |
| **5** | **Attendance History** | 🟡 **NEXT** |
| 6 | Calendar & Academic Events | ⚪ Planned |
| 7 | Quiz Eligibility & Schedule UX | ⚪ Planned |
| 8 | Attendance Analytics / Intelligence | ⚪ Planned |
| 9 | Laboratory System | ⚪ Planned |
| 10 | Settings, Feedback & Account Management | ⚪ Planned |
| 11 | Notifications & Reminders | ⚪ Planned |
| 12 | Mobile / Responsive Experience | ⚪ Planned |
| 13 | PWA / Installability | ⚪ Planned |
| 14 | Firebase Retirement | 🔴 Later |
| 15 | Production Security Hardening | 🔴 Later |
| 16 | Data Integrity & Migration Hardening | 🔴 Later |
| 17 | Production Infrastructure | 🔴 Later |
| 18 | CI/CD | 🔴 Later |
| 19 | Production QA | 🔴 Later |
| 20 | Production Launch | 🔴 Later |
| 21 | Post-Launch | 🔵 Ongoing |

---

# 🟢 Phase 0 — Architecture & Reality Audit

**Status: COMPLETE / FROZEN**

Established the actual baseline:

- Frontend/backend architecture
- PostgreSQL state
- API surface
- Existing engines
- Firebase retirement status
- Existing pages/components
- Database relationships
- Existing data gaps
- Technical debt

### Freeze rule

Do not repeat this audit unless a later discovery directly contradicts the baseline.

---

# 🟢 Phase 1 — Design System Foundation

**Status: COMPLETE / FROZEN**

Implemented the visual foundation:

- Dark visual system
- Typography
- Color system
- Cards
- Badges
- Progress indicators
- Semantic status variants
- High-density layouts

Primary accent:

```text
#3B82F6
```

Legacy purple/magenta styling is not part of the target design system.

### Freeze rule

Do not redesign or rewrite these primitives merely for preference. Reopen only for a genuine defect or a deliberate product decision.

---

# 🟢 Phase 2 — Desktop Shell & Global UX

**Status: COMPLETE / FROZEN**

Implemented:

- Desktop top navigation
- User/profile menu
- Profile modal
- Appearance modal
- Settings modal
- Feedback modal foundation
- Install-app foundation
- Global dialog behavior
- Active navigation
- Authentication-aware shell
- Logout

Firebase-specific shell dependencies were removed.

### Freeze rule

Do not revisit the shell unless a real bug or explicit product requirement requires it.

---

# 🟢 Phase 3 — Home Dashboard

**Status: COMPLETE / FROZEN**

Implemented:

- Greeting
- Today's Attendance
- Weekly attendance
- Overall attendance
- Quiz snapshot
- Attention items
- Upcoming events
- Loading states
- Error states
- Empty states
- Dashboard aggregation endpoint

The dashboard consumes real backend data.

### Freeze rule

Do not repeatedly rebuild the dashboard because of visual preferences. Reopen only for real defects or later feature integration.

---

# 🟢 Phase 4 — Track Attendance

**Status: COMPLETE / FROZEN**

Implemented:

- Daily attendance view
- Date navigation
- Session cards
- Present / Absent
- Attendance changes
- Cancelled-session handling
- Mark All Present
- Cache/optimistic update behavior
- Enrollment authorization
- Backend daily-session endpoint

### Critical product requirement

> **15 July 2026 → current date**

Track must expose the student's complete semester attendance history.

**✅ SATISFIED in Phase 4.5.2** — Track navigates the full semester range (bounds from
`/student/me`, no hardcoded dates), shows every session type including practicals, and
supports manual historical re-entry through the canonical mutation endpoint. The 26
historical lab sessions remain unmarked pending the user's manual reconstruction.

If the historical data cannot be reliably recovered, manual re-entry is acceptable.

**Rebuilding the architecture is not acceptable.**

### Freeze rule

The attendance architecture is considered foundational. Do not rewrite it to solve a data problem.

---

# 🟢 Phase 4.5 — Data Integrity & Account Foundation

**Status: COMPLETE / FROZEN** — 4.5.1 audit ✅ · 4.5.2 historical Track ✅ · 4.5.3 Real Sign Up ✅.

## 4.5.1 — Historical Attendance Audit

**Status: COMPLETE** (read-only, 2026-08-13 → report `docs/phase_4_5_data_audit.md`).

Verdict: **B — PRESERVE WITH MANUAL CORRECTION**.

- Database structure healthy, zero structural corruption.
- 78 records exist (54 ATTENDED / 24 MISSED), 124 sessions in semester range, 46 unmarked (20 theory + 26 lab).
- Labs (BCS-551 ×8, BCS-552 ×10, BCS-553 ×8) never marked; laboratory tables empty.
- 4.5.1-B forensic investigation (report `docs/phase_4_5_1B_lab_attendance_forensics.md`) PROVED the legacy
  PWA silently skipped lab subjects in analytics (`getAttendanceData` required a QUIZ milestone and returned on
  error) — lab marking worked mechanically but counted nowhere. The PostgreSQL architecture does not repeat this
  defect.

### Possible verdicts

#### A — PRESERVE

Existing data is sufficiently complete and trustworthy.

#### B — PRESERVE WITH MANUAL CORRECTION

Most data is usable, but some manual correction/re-entry is required.

#### C — RESET DEVELOPMENT DATA

The data itself is sufficiently unreliable that a clean development baseline is safer.

### Critical rule

**Do not delete or reset anything during the audit.**

---

## 4.5.2 — Historical Track Coverage

**Status: COMPLETE** (2026-08-14).

- Track navigates the full semester history **2026-07-15 → current date**, bounded by the real
  `semester_start`/`semester_end` from `/student/me` (no hardcoded dates); date picker + Today + clamped arrows.
- Every scheduled session is visible: LECTURE, TUTORIAL, PRACTICAL/LAB, Pending, Attended, Missed, Cancelled.
- Practical sessions (BCS-551/552/553) appear as normal attendance sessions — the legacy
  quiz-window/attendance confusion is not repeated.
- Missing record = PENDING (no database row is created for pending).
- One canonical mutation endpoint (`POST /api/v1/attendance`) handles historical marking and Present↔Absent
  corrections; cancelled sessions rejected (409); reads scoped to the student's enrolled subjects; unique
  constraint preserved.
- Root-cause fix landed: frontend `AttendanceStatus`/`ClassType` enums corrected to the live backend contract
  (`Attended`/`Missed`/`Pending`, `P`), which had silently broken Track marking and history state rendering.
- Analytics engines untouched; verified labs flow through the canonical pipeline (`GET /attendance/summary/BCS-551`
  → practical 8/8 PENDING).
- The 26 historical lab sessions remain unmarked by design — the user establishes historical truth manually
  through Track. No invented attendance, no laboratory experiment rows.

---

## 4.5.3 — Real Sign Up

**Status: COMPLETE** (2026-08-14).

- `POST /api/v1/auth/register` + `/signup` page (Full Name, 13-digit Roll Number, Password,
  Confirm Password, show/hide, Create Account, link to Login).
- **Enrollment provisioning**: academic context resolved from authoritative configuration only —
  active `AcademicSession` → its `Semester` → its `Section` → all semester `Subject` rows — created
  transactionally with the user. The client cannot submit section/semester/session/subject IDs.
  Single-section semesters auto-assign; ambiguous configurations are rejected explicitly.
- **firebase_uid**: made NULLABLE (migration `c3d4e5f6a7b8`) for PostgreSQL-native identity;
  all 29 legacy UIDs preserved; column retained for Phase 14 (Firebase Retirement).
- **Passwords**: same `pbkdf2_sha256` format/verifier as login (`hash_password` added to
  `app/core/security.py`); never logged or echoed.
- **JWT**: issued immediately after registration through the exact `create_access_token` used by
  login (no second auth flow); student enters the app shell directly.
- Duplicate roll number → 409 (`IntegrityError` race guard); validation 422; ambiguous academic
  config 409/503; all failures roll back — no partial accounts, no orphan enrollments.

**Firebase must not return.**

---

# 🟡 Phase 5 — Attendance History

**Status: NEXT** (after Phase 4.5 froze).

Turn the existing history functionality into a production-quality experience.

Build/polish:

- Complete historical list
- Subject filtering
- Date filtering
- Attendance-state filtering
- Search
- Pagination/infinite loading
- Session details
- Correct Present/Absent display
- Semester-start history
- Loading states
- Error states
- Empty states

### Architectural rule

History and Track must consume the **same canonical attendance records**.

No duplicate attendance source.

---

# 🟡 Phase 6 — Calendar & Academic Events

Build the complete calendar/event experience.

## Calendar

- Month/day navigation
- Working days
- Weekends
- Holidays
- Academic events
- Class schedule
- Selected date
- Event indicators

## Events

- Upcoming
- Today
- Past
- Event details
- Event types
- Holiday indicators
- Substitution schedules

## Event persistence

Eventually support controlled event mutation:

```text
Admin
  ↓
Create Event
  ↓
Academic Events
  ↓
Calendar Engine
  ↓
Track / Dashboard / Quiz Eligibility
```

The event system must feed the existing engines instead of creating parallel rules.

---

# 🟡 Phase 7 — Quiz Eligibility & Schedule UX

The backend eligibility architecture is already substantially implemented and audited.

Now complete the user-facing experience.

For every relevant subject:

- Quiz I
- Quiz II
- Quiz III
- Required percentage
- Quiz date
- Attendance window
- Current percentage
- Eligibility
- Must Attend
- Safe Skip
- Lecture/tutorial breakdown
- Unresolved state
- Policy ambiguity

### Critical rule

The existing eligibility engine remains authoritative.

Do not move quiz calculations into React.

---

# 🟡 Phase 8 — Attendance Analytics / Intelligence

Turn the existing calculations into a strong intelligence experience.

## Overall analytics

- Current percentage
- Lecture/tutorial breakdown
- Subject-wise percentage
- Weekly trend
- Semester trend

## Forecasting

Examples:

> If you attend the next 3 classes…

> You can safely skip 2 lectures…

> You need 5 consecutive classes to reach 75%…

## Risk states

```text
SAFE
WATCH
AT RISK
CRITICAL
```

### Architectural rule

Dashboard, Track, History and Quiz Eligibility must remain consistent because they derive from the same canonical calculations.

This phase improves **analytics presentation and intelligence**, not by repeatedly rebuilding the core engines.

---

# 🟡 Phase 9 — Laboratory System

Complete the laboratory experience for:

- BCS-551
- BCS-552
- BCS-553

Build/polish:

- Experiment list
- Experiment number
- Title
- Completion state
- Signed/pending state
- Conducted date
- Marks
- Remarks
- Progress
- Experiment details

Then define whether students should be allowed to mutate laboratory records.

Do not invent mutation behavior without defining the academic workflow.

---

# 🟡 Phase 10 — Settings, Feedback & Account Management

Turn the Phase 2 foundations into real functionality.

## Settings

Potentially:

- Notification preferences
- Default landing page
- Attendance display preferences
- Reminder preferences
- Account preferences

Likely requires:

```text
user_preferences
```

plus GET/PUT API endpoints.

## Feedback

Implement a real feedback system:

```text
POST /feedback
```

with:

- Feedback type
- Message
- Optional context
- Timestamp
- User association

Never fake a successful submission.

## Profile

Complete:

- Name
- Roll number
- Section
- Program
- Semester
- Session
- Academic dates

---

# 🟡 Phase 11 — Notifications & Reminders

Only after the academic/event architecture is stable.

Potential features:

- Upcoming class reminder
- Quiz approaching
- Attendance-below-threshold warning
- Must-attend warning
- Safe-skip information
- Academic event notification

### Architectural rule

Notifications consume engine outputs.

They do **not** independently calculate attendance.

---

# 🟡 Phase 12 — Mobile / Responsive Experience

Desktop is currently the primary visual reference.

Build a genuine mobile experience rather than simply shrinking desktop.

Include:

- Mobile navigation
- Responsive top bar
- Bottom navigation where appropriate
- Responsive cards
- Touch targets
- Mobile date navigation
- Mobile Track workflow
- Mobile profile menu
- Responsive quiz cards
- Responsive analytics

---

# 🟡 Phase 13 — PWA / Installability

Implement genuine installability:

- Web manifest
- Service worker
- Icons
- Install prompt
- Standalone detection
- Offline strategy
- Cached application shell
- Correct online/offline states

Do not claim offline functionality unless the underlying data strategy actually supports it.

---

# 🔴 Phase 14 — Firebase Retirement

**Late-stage phase.**

Do not remove Firebase prematurely.

Before retirement, prove:

```text
Frontend
 ├── No Firebase Auth
 ├── No Firebase SDK dependency
 ├── No Firestore reads
 ├── No Firestore writes
 └── No Firebase-specific state

Backend
 ├── No firebase-admin
 └── No Firebase authentication dependency

Data
 └── PostgreSQL is authoritative
```

Then:

1. Remove frontend Firebase dependencies.
2. Remove Firebase configuration.
3. Remove legacy code.
4. Archive required legacy data if necessary.
5. Update deployment/configuration.
6. Remove Firebase dependencies.

---

# 🔴 Phase 15 — Production Security Hardening

## Authentication

- Password policy
- Secure password hashing
- JWT expiry
- Refresh strategy if required
- Token invalidation strategy
- Brute-force protection
- Login rate limiting

## Authorization

Verify every sensitive endpoint against cross-user access:

```text
Can User A access User B's data?
```

Especially:

- Attendance
- History
- Quiz eligibility
- Laboratory
- Profile
- Events
- Feedback
- Preferences

## Database

- Constraints
- Indexes
- Foreign keys
- Uniqueness
- Cascading behavior
- Transaction boundaries

## API

- Validation
- Error handling
- CORS
- Security headers
- Production logging

---

# 🔴 Phase 16 — Data Integrity & Migration Hardening

Before production:

- Database backup
- Restore test
- Migration test
- Rollback strategy
- Seed strategy
- Semester transition strategy
- Duplicate prevention
- Orphan detection
- Data cleanup procedures

## Long-term academic model

The architecture should not remain hardcoded around:

```text
15 July 2026
```

It should understand:

```text
Academic Year
    ↓
Semester
    ↓
Start Date
    ↓
End Date
    ↓
Subjects
    ↓
Enrollment
    ↓
Timetable
    ↓
Attendance
    ↓
Quiz Cycles
```

This is essential for a real multi-semester product.

---

# 🔴 Phase 17 — Production Infrastructure

Move from:

```text
Development PC
 ├── Next.js
 ├── FastAPI
 └── Docker PostgreSQL
```

to production infrastructure:

```text
                    Users
                      │
                 HTTPS / CDN
                      │
              ┌───────▼────────┐
              │ Next.js         │
              │ Frontend        │
              └───────┬────────┘
                      │ HTTPS
              ┌───────▼────────┐
              │ FastAPI         │
              │ Backend         │
              └───────┬────────┘
                      │
                Private network
                      │
              ┌───────▼────────┐
              │ PostgreSQL      │
              └────────────────┘
```

Exact hosting choices will be made later based on cost, reliability and requirements.

---

# 🔴 Phase 18 — CI/CD

Establish a production quality gate:

```text
GitHub
   ↓
Push
   ↓
CI
 ├── TypeScript check
 ├── Python checks
 ├── Frontend build
 └── Migration checks
   ↓
Deployment
```

Development workflows should remain quota-efficient, while production receives appropriate verification.

---

# 🔴 Phase 19 — Production QA

Perform a complete real-user journey.

## Account

- Sign up
- Login
- Wrong password
- Logout
- Refresh
- Session expiration

## Dashboard

- Name
- Attendance
- Weekly data
- Overall data
- Quiz data
- Alerts
- Events

## Track

- 15 July history
- Today's classes
- Future classes
- Present
- Absent
- Corrections
- Mark All Present
- Cancelled sessions

## History

- Complete records
- Filters
- Search
- Dates
- States

## Calendar

- Dates
- Weekends
- Holidays
- Events
- Classes

## Quiz

- Q1
- Q2
- Q3
- Thresholds
- Windows
- Must Attend
- Safe Skip
- Unresolved cycles

## Laboratories

- Subjects
- Experiments
- Records
- Statuses

## Profile

- Information
- Settings
- Logout

---

# 🔴 Phase 20 — Production Launch

Only after QA passes.

Deployment sequence:

```text
Production Database
        ↓
Database Migration
        ↓
Backend
        ↓
Frontend
        ↓
Domain
        ↓
HTTPS
```

Production data setup:

- Semester configuration
- Subjects
- Timetable
- Quiz schedules
- Academic events
- Initial administrative configuration

Monitoring:

- Server errors
- Database health
- API latency
- Authentication failures
- Uptime
- Backups

---

# 🔵 Phase 21 — Post-Launch

After real users begin using the system:

- Monitor errors
- Collect feedback
- Identify calculation discrepancies
- Improve UX
- Fix production bugs
- Optimize expensive queries
- Improve mobile experience
- Handle semester rollover

Only after the core product is stable should ambitious new features be added.

---

# 🔗 Critical Dependency Path

```text
PHASE 0
   ↓
PHASE 1
   ↓
PHASE 2
   ↓
PHASE 3
   ↓
PHASE 4
   ↓
PHASE 4.5  ← CURRENT
   ↓
PHASE 5
   ↓
PHASE 6
   ↓
PHASE 7
   ↓
PHASE 8
   ↓
PHASE 9
   ↓
PHASE 10
   ↓
PHASE 11
   ↓
PHASE 12
   ↓
PHASE 13
   ↓
PHASE 14
   ↓
PHASE 15
   ↓
PHASE 16
   ↓
PHASE 17
   ↓
PHASE 18
   ↓
PHASE 19
   ↓
PHASE 20
   ↓
PHASE 21
```

This is a dependency path, not a rule that every subtask must be executed serially. Independent work can be parallelized when it is safe.

---

# 🏛️ Core Architectural Rules

## Rule 1 — Data, business logic and presentation stay separate

```text
DATA
PostgreSQL
   ↓
BUSINESS LOGIC
Repositories
   ↓
Services
   ↓
Engines
   ↓
PRESENTATION
Next.js
   ↓
Components
   ↓
UI
```

Do not move business calculations into React simply because it is convenient.

---

## Rule 2 — One canonical source of truth

Attendance must have one authoritative data path.

```text
Attendance Records
        ↓
Services
        ↓
Engines
        ↓
Dashboard
Track
History
Quiz
Analytics
```

No feature-specific duplicate calculations.

---

## Rule 3 — Data problems do not justify architecture rewrites

If historical data is bad:

```text
BAD DATA
   ↓
repair / reset / re-enter
```

NOT:

```text
BAD DATA
   ↓
rewrite engines
   ↓
rewrite services
   ↓
rewrite architecture
```

Manual data entry is acceptable.

Repeatedly rebuilding complex architecture is not.

---

## Rule 4 — Completed phases are frozen

Once a phase passes implementation and manual verification:

> **Do not touch it again unless a genuine defect or explicit product requirement requires reopening it.**

This prevents endless refactoring and regressions.

---

## Rule 5 — Empty states do not prove correctness

An endpoint returning:

```json
[]
```

does not prove the endpoint works.

Every feature must eventually be checked against meaningful real data.

---

## Rule 6 — Backend contracts must match the database

Do not invent frontend/backend fields that don't exist.

ORM → Schema → API → TypeScript → UI

must remain aligned.

---

## Rule 7 — Security is part of correctness

A feature is not complete if:

```text
User A can access User B's data.
```

Authorization must be checked at the backend boundary.

---

# ✅ Definition of "Production Ready"

AttendanceDash Pro is not considered finished merely because the UI looks good.

A real student must be able to:

```text
Sign Up
   ↓
Login
   ↓
See actual subjects
   ↓
See semester timetable
   ↓
Mark attendance
   ↓
See historical attendance
   ↓
See accurate percentages
   ↓
Understand attendance risk
   ↓
See quiz eligibility
   ↓
Know exactly how many classes they must attend
   ↓
See calendar/events
   ↓
Track laboratories
   ↓
Manage profile/settings
   ↓
Use desktop/mobile
   ↓
Install the application if supported
   ↓
Use it securely in production
```

And the same underlying data must produce consistent answers everywhere.

---

# 🧠 Adaptive Project Governance

The roadmap is the **direction**, not a prison.

The user is responsible for:

- Manual browser testing
- Reporting bugs
- Reporting unexpected behavior
- Reporting missing features
- Reporting UX problems
- Providing real-world feedback

The project roadmap is responsible for:

- Maintaining priorities
- Deciding where discoveries belong
- Reordering phases when necessary
- Protecting completed architecture
- Deciding when a phase should reopen
- Creating execution prompts
- Tracking completed vs remaining work
- Preventing unnecessary rework
- Preserving architectural integrity

### Working principle

> **User reports reality. Roadmap adapts to reality.**

A newly discovered bug may:

- remain inside the current phase,
- become a targeted hotfix,
- create a new sub-phase,
- reorder upcoming work,
- or reopen a frozen phase if the defect is architectural.

But we do **not** restart the project because of every issue.

---

# 🚦 Current Operating State

```text
PHASE 0  ████████████████████  COMPLETE 🔒
PHASE 1  ████████████████████  COMPLETE 🔒
PHASE 2  ████████████████████  COMPLETE 🔒
PHASE 3  ████████████████████  COMPLETE 🔒
PHASE 4  ████████████████████  COMPLETE 🔒

PHASE 4.5 ████████████████████  COMPLETE 🔒 (audit · Track · Sign Up)

PHASE 5  ██░░░░░░░░░░░░░░░░░░  CURRENT 🟡
PHASE 6  ░░░░░░░░░░░░░░░░░░░░  PLANNED
PHASE 7  ░░░░░░░░░░░░░░░░░░░░  PLANNED
...
PHASE 20 ░░░░░░░░░░░░░░░░░░░░  PLANNED
PHASE 21 ░░░░░░░░░░░░░░░░░░░░  ONGOING
```

## Immediate Next Action

**Phase 5: Attendance History**

Phase 4.5 is frozen. The audit (4.5.1) reached verdict **B — PRESERVE WITH MANUAL CORRECTION**;
Track (4.5.2) covers the full semester history with practical attendance flowing through the
canonical pipeline; registration (4.5.3) creates PostgreSQL-native accounts with transactional
enrollment and immediate JWT authentication.

Next: turn the existing history functionality into a production-quality experience (complete
historical list, subject/date/state filtering, search, pagination/infinite loading, session
details, correct Present/Absent display, semester-start history, loading/error/empty states).
History and Track must consume the same canonical attendance records.
