# 21 — Changelog

This document tracks the evolution of the AttendanceDash Pro architecture across major development phases.

---

## Phase F1.3 — Academic Event Management System (UI)
*Status: Code-complete, pending browser validation.*

**Features Introduced**:
- Event creation form (bottom sheet).
- Events list UI in the Academic Tools workspace.
- Active/Archived tab filtering for events.

**Architecture Changes**:
- Implemented `events-controller.js` as the strict mutation layer for academic events.
- Enforced soft-delete (archive) as the default event lifecycle.
- Shifted Academic Tools from a root navigation tab into a sub-workspace within Profile.

**Known Regressions**:
- Discovered BUG-001 (Firestore rules block event sync) and BUG-002 (Service worker cache omits controller). Both block full offline/sync functionality for the feature.

---

## Phase F1.2 — Academic Event System (Backend)
*Status: Complete*

**Features Introduced**:
- `AcademicEventRegistry` defining all valid event types (extra lectures, holidays, emergency closures).
- Event delta computation in the Calendar Engine.

**Architecture Changes**:
- Decided on date-indexed storage (`AppState.academicEvents["YYYY-MM-DD"] = [...]`) for O(1) rendering performance.
- Added event versioning and history trailing to the `AcademicEvent` schema.

---

## Phase F1.1 — Subject-Specific Timelines
*Status: Complete*

**Features Introduced**:
- Decoupled the attendance window start/end dates so they can be defined per subject.
- Mixed-timeline support (some subjects have custom timelines, others use global fallback).

**Architecture Changes**:
- Shifted timeline definitions into `timetable.json`.
- Modified `getAttendanceData` to query window boundaries per subject rather than globally.

---

## Phase S1.10 — Stabilization (Regression Incident)
*Status: Resolved*

**Incident**:
- A syntax error in `ui.js` (unclosed template literal and duplicate variable declaration) broke the entire application.
- Because of the PWA service worker, the broken JS was cached, causing a white screen / unclickable buttons even after fixes were deployed.

**Resolution**:
- Fixed the syntax errors.
- Incremented `APP_VERSION` to bust the cache.
- Instituted mandatory AST validation (`acorn`) for `ui.js` after major edits.

---

## Phase A2.4 — Quiz Engine Consolidation
*Status: Complete*

**Features Introduced**:
- Dashboard now displays exactly how many classes a student must attend to become eligible.

**Architecture Changes**:
- Removed all duplicate attendance math from `quiz-engine.js`.
- Refactored `quiz-engine.js` into a pure rules engine.
- Introduced `OptimizationResult` passing from Attendance Engine to Quiz Engine.
- Enforced the "UI is a pure consumer" rule (UI never orchestrates engines).

---

## Phase A2.3 — Calendar Engine Extraction
*Status: Complete*

**Features Introduced**:
- Unified handling of holidays, weekends, and working Saturdays.

**Architecture Changes**:
- Extracted all temporal logic from UI and Attendance Engine into `calendar-engine.js`.
- Established the strict Engine Layering rule (Calendar is the absolute bottom layer).

---

## Phase A1 — Foundation
*Status: Complete*

**Features Introduced**:
- Basic percentage calculation.
- LocalStorage persistence.
- Firebase Authentication.
- Static timetable parsing.
- Responsive CSS (Desktop/Mobile).

**Architecture Changes**:
- Decided on zero-build, Vanilla JS + ES Modules.
- Chose `AppState` singleton hydration strategy.
