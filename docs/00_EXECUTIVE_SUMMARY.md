# 00 — Executive Summary

## Project Vision

AttendanceDash Pro is a production-quality, offline-capable Progressive Web App that gives university students at AKTU-affiliated institutions (SRMCEM and similar) a real-time, mathematically rigorous view of their attendance standing across all subjects. It replaces manual spreadsheet tracking with an intelligent, engine-driven system that calculates exactly how many classes a student must attend — or can safely skip — to remain eligible for each upcoming quiz.

---

## Problem Being Solved

AKTU enforces a minimum attendance threshold that determines quiz eligibility. The institution's own ERP portal shows only a raw cumulative percentage — it does not tell a student:

- How many more classes they **must attend** to become eligible for the next quiz.
- How many they can **safely skip** without falling below the threshold.
- The impact of marking a **pending class** as attended or missed *before* making the choice.
- How a **specific subject's** timeline differs from global quiz dates.

AttendanceDash Pro solves all of these problems with a single, exhaustive mathematical optimizer that evaluates every valid (Lectures, Tutorials) attendance combination to find the minimum classes required to meet the target percentage.

---

## Target Users

- **Primary**: Students at SRMCEM (Section CSE-51, V Semester, 2026–27).
- **Planned**: Any AKTU-affiliated institution with a compatible timetable configuration.

---

## Current Maturity

| Layer | Status |
|---|---|
| Calendar Engine | ✅ Complete — production-stable |
| Attendance Engine | ✅ Complete — production-stable |
| Quiz Engine | ✅ Complete — production-stable |
| Laboratory Engine | ✅ Complete — stable, basic feature set |
| Academic Event System (backend) | ✅ Complete — runtime events, registry, controller |
| Academic Event System (UI) | 🟡 Implemented, requires browser validation |
| Date Context / Simulation Mode | ✅ Complete |
| Storage & Cloud Sync | ✅ Complete |
| PWA / Offline | ✅ Complete |
| Authentication | ✅ Complete |
| Feedback System | ✅ Complete |
| Holiday Calendar (UI) | ⬜ Planned |
| Quiz Schedule Manager (UI) | ⬜ Planned |
| ERP Integration | ⬜ Future |

**Current application version**: `2.0.2`  
**Current phase**: `F1.3` — Academic Event Management System (CRUD + Live Engine Integration)

---

## Long-Term Goals

1. Support multiple sections, batches, and institutions via configuration-only changes (zero engine rewrites).
2. Provide a full ERP integration that auto-populates attendance from the university portal.
3. Build a complete academic calendar manager — holidays, extra classes, quiz schedule adjustments — through a rich UI.
4. Extend the Laboratory Engine to support grading, marks, and viva tracking.
5. Enable offline-first operation with full conflict-free sync upon reconnection.

---

## Current Development Status

The core architectural foundation is **locked and stable**. The three-engine architecture (Calendar → Attendance → Quiz) has been through multiple stabilization passes and is considered production-quality. All duplicate business logic has been eliminated. The Academic Event System backend is complete.

The immediate next work is browser-level validation and testing of the Academic Event CRUD UI (Phase F1.3 completion), followed by the Holiday Calendar and Quiz Schedule Manager features.

> **For the inheriting AI**: The architecture is not negotiable. No engine rewrites are planned. Focus on building features on top of the stable foundation. See [17_AI_HANDOFF.md](17_AI_HANDOFF.md) for the complete handoff briefing.
