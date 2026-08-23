# AttendanceDash Pro — Project Bible & AI Developer Handoff

> ## ⚠️ DOCUMENTATION BOUNDARY (2026-08-23)
>
> The documents in this directory (docs/00–22 and the S3.x series) describe the
> **legacy single-page web application** and its Firebase-era architecture. That
> legacy application has been **retired** (Phase 15 — Legacy Web App + Legacy PWA
> Retirement). Its root-level files (`index.html`, `js/`, `css/`, `assets/`, root
> `manifest.json`, root `service-worker.js`, `offline.html`) have been removed from
> the repository. This documentation is preserved for historical provenance.
>
> **The active application is:** Next.js frontend (`frontend/`) + FastAPI backend
> (`backend/`) + PostgreSQL + JWT authentication. Firebase is fully retired
> (Phases 14A–14E). The current Next.js PWA (Phase 13, `frontend/public/`) is the
> active PWA.
>
> For current project status, see `MASTER_ROADMAP.md`, `implementation_plan.md`,
> `task.md`, and `walkthrough.md` at the repository root.

This directory contains the permanent technical reference for AttendanceDash Pro.

It is written for **AI agents and human developers** who need to continue work on this project with minimal context loss.

---

## Document Index

| Doc | Title | Contents |
|---|---|---|
| [00](00_EXECUTIVE_SUMMARY.md) | Executive Summary | Vision, maturity, goals |
| [01](01_PROJECT_OVERVIEW.md) | Project Overview | Target platform, design philosophy, scalability |
| [02](02_TECH_STACK.md) | Technology Stack | Firebase, PWA, SDK strategy, module graph |
| [03](03_FOLDER_STRUCTURE.md) | Folder Structure | Every file explained, purpose, ownership |
| [04](04_ARCHITECTURE.md) | Complete Architecture | Layer diagram, data flow, bootstrap sequence |
| [05](05_CALENDAR_ENGINE.md) | Calendar Engine | API, domain models, event priority, known limits |
| [06](06_ATTENDANCE_ENGINE.md) | Attendance Engine | Optimizer algorithm, API, internal structure |
| [07](07_QUIZ_ENGINE.md) | Quiz Engine | Eligibility rules, domain models, policy resolution |
| [08](08_LABORATORY_ENGINE.md) | Laboratory Engine | Lab experiments, milestones, storage format |
| [09](09_ACADEMIC_EVENT_SYSTEM.md) | Academic Event System | Registry, controller, lifecycle, storage, known issues |
| [10](10_STORAGE_AND_SYNC.md) | Storage and Synchronization | AppState, localStorage, Firestore sync, known issues |
| [11](11_UI_ARCHITECTURE.md) | UI Architecture | recalculateAndRender, component builders, rendering rules |
| [12](12_PWA_AND_DEPLOYMENT.md) | PWA and Deployment | Service worker, caching, manifest, install flow |
| [13](13_CODING_STANDARDS.md) | Coding Standards | Naming, module rules, engine rules, CSS conventions |
| [14](14_TESTING_AND_QA.md) | Testing and QA | Unit tests, AST validation, Puppeteer, manual QA |
| [15](15_KNOWN_BUGS_AND_TECHNICAL_DEBT.md) | Known Bugs and Technical Debt | All confirmed bugs and design debt |
| [16](16_ROADMAP.md) | Product Roadmap | Immediate priorities, near-term, medium-term, long-term |
| [17](17_AI_HANDOFF.md) | AI Developer Handoff | Architectural invariants, pitfalls, how to add features |
| [18](18_ARCHITECTURE_DECISION_RECORDS.md) | Architecture Decision Records | Chronological log of major architectural choices |
| [19](19_DEPENDENCY_GRAPH.md) | Dependency Graph | Module dependencies, rules, and allowed imports |
| [20](20_DATA_DICTIONARY.md) | Data Dictionary | Persistent data structures, lifecycles, ownership |
| [21](21_CHANGELOG.md) | Changelog | Evolution across major phases and feature additions |
| [22](22_AI_WORKING_CONTEXT.md) | AI Working Context | Permanent working mindset, rules, and philosophy for future AI |
| [S3.2](S3.2_FUNCTIONAL_GAP_AUDIT.md) | S3.2 Functional Gap Audit | Read-only forensic feature audit |
| [S3.5](S3.5_UI_UX_AUDIT.md) | S3.5 UI/UX Audit | Read-only UI/UX forensic audit |
| [S3.6](S3.6_PERSISTENCE_SYNC_AUDIT.md) | S3.6 Persistence & Sync Audit | Persistence lifecycle audit, P0/P1/P2 fixes |
| [S3.7](S3.7_MOBILE_PWA_AUDIT.md) | S3.7 Mobile/PWA Audit | PWA forensic audit, offline characterisation |
| [S3.8](S3.8_FULL_REGRESSION_REPORT.md) | S3.8 Full Regression Report | Master regression matrix, cross-system tests |
| [S3.9](S3.9_PRODUCTION_READINESS_AUDIT.md) | S3.9 Production Readiness Audit | Security, storage resilience, deployment readiness |
| [S3.10](S3.10_CURRENT_SEMESTER_BASELINE.md) | S3.10 Current-Semester Baseline | Frozen baseline: version, academic, architecture, regression, persistence, PWA, invariants |

---

## Quick Start for the Next Developer

1. **Read [17 — AI Handoff](17_AI_HANDOFF.md) first.** It contains the invariants you must not violate.
2. **Read the frozen baseline** — [S3.10](S3.10_CURRENT_SEMESTER_BASELINE.md) is the authoritative current-semester snapshot (version, architecture, engines, test baseline, deployment facts).
3. **Start new features from the Roadmap** — [16 — Roadmap](16_ROADMAP.md) has a prioritized list.
4. **Reconcile legacy docs** — [15 — Known Bugs](15_KNOWN_BUGS_AND_TECHNICAL_DEBT.md) still lists BUG-001/BUG-002 which are already fixed in code (see S3.10); treat the baseline as authoritative.

---

## Architecture in One Diagram

```mermaid
graph TD
    TT[timetable.json] --> CE[Calendar Engine]
    CE --> AE[Attendance Engine]
    AE --> QE[Quiz Engine]
    
    CE --> Events[Academic Events]
    AE --> LE[Laboratory Engine]
    
    Events --> EC[EventsController]
    EC --> AS[AppState]
    AS --> FS[Firestore]
    AS --> LS[localStorage]
    
    AS --> RR[recalculateAndRender]
    RR --> UI[ui.js DOM]
```

---

## Application Version

**Current**: `2.0.3`  
**Current Phase**: S3.10 — Current-Semester Baseline Freeze (complete; baseline in `docs/S3.10_CURRENT_SEMESTER_BASELINE.md`)
