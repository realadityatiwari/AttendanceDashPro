# AttendanceDash Pro — AI Prompt Templates

> ## ⚠️ BOUNDARY NOTE (2026-08-23)
>
> These prompt templates were written for the **legacy single-page web application**
> (root `index.html`, `js/`, `css/`, `assets/`, legacy PWA) and reference its files.
> The legacy application has been **retired** (Phase 15 — Legacy Web App + Legacy
> PWA Retirement); its root-level runtime files no longer exist. The prompts are
> preserved for historical provenance. The **active application** is the Next.js
> frontend (`frontend/`) + FastAPI backend (`backend/`) + PostgreSQL + JWT — do not
> apply these legacy-app prompts to the active codebase without adaptation.

This directory contains production-grade prompt templates designed to standardize development for any AI coding agent (Claude, Codex, Gemini, Cursor, Windsurf, etc.). 

These prompts enforce the project's strict architectural rules, unidirectional data flow, and cross-platform parity. 

By using these templates, you ensure that every future AI agent acts with the same context, discipline, and engineering philosophy as the original architects.

---

## Prompt Index

| Prompt | Use Case |
|---|---|
| `01_MASTER_IMPLEMENTATION_PROMPT` | The default prompt for any new feature or major task. |
| `02_ARCHITECTURE_REVIEW_PROMPT` | Used to validate a proposed design before writing code. |
| `03_FEATURE_PLANNING_PROMPT` | Used to generate an implementation plan for user approval. |
| `04_FEATURE_IMPLEMENTATION_PROMPT` | Used to write code after an implementation plan is approved. |
| `05_BUG_FIX_PROMPT` | Used to diagnose and safely resolve a bug without breaking architecture. |
| `06_REFACTORING_PROMPT` | Used to restructure code while preserving exact behavior. |
| `07_CODE_REVIEW_PROMPT` | Used to audit newly written code against project standards. |
| `08_REGRESSION_TEST_PROMPT` | Used to manually or automatically verify baseline functionality. |
| `09_DOCUMENTATION_UPDATE_PROMPT` | Used to update the Project Bible and ADRs. |
| `10_AI_HANDOFF_UPDATE_PROMPT` | Used to conclude a development phase and update handoff docs. |
| `11_RELEASE_CHECKLIST` | Used immediately before a release. |
| `12_NEW_MODULE_PROMPT` | Used when creating a new `.js` file to ensure proper dependency layering. |
| `13_UI_UX_IMPLEMENTATION_PROMPT` | Used for purely visual or UX changes in `ui.js`. |
| `15_PERFORMANCE_OPTIMIZATION_PROMPT` | Used when the app drops frames or rendering is slow. |
| `16_SECURITY_REVIEW_PROMPT` | Used to audit security and XSS vulnerabilities. |
| `17_TEST_GENERATION_PROMPT` | Used to write Node.js unit tests for the pure engines. |
| `18_DEBUGGING_PROMPT` | Used to trace state mutations during a crash or bad calculation. |
| `20_PROJECT_AUDIT_PROMPT` | Used for holistic, repository-wide health checks. |

---

## Recommended AI Workflows

Copy and paste the contents of these markdown files into your AI's context window (or use them as System Prompts / Custom Instructions) depending on the task.

### 1. New Feature Workflow
Use this sequence when building a brand new feature (e.g., "Surprise Quizzes").
1. Inject `03_FEATURE_PLANNING_PROMPT`
2. *(Wait for user approval on the plan)*
3. Inject `04_FEATURE_IMPLEMENTATION_PROMPT`
4. Inject `08_REGRESSION_TEST_PROMPT`
5. Inject `09_DOCUMENTATION_UPDATE_PROMPT`

### 2. Standard Task Workflow
For most day-to-day development.
1. Inject `01_MASTER_IMPLEMENTATION_PROMPT`

### 3. Bug Fix Workflow
1. Inject `18_DEBUGGING_PROMPT` to trace the root cause.
2. Inject `05_BUG_FIX_PROMPT` to implement the fix.
3. Inject `08_REGRESSION_TEST_PROMPT` to ensure it didn't break standard behavior.

### 4. Refactoring Workflow
1. Inject `02_ARCHITECTURE_REVIEW_PROMPT` to analyze the current state.
2. Inject `06_REFACTORING_PROMPT` to execute the structural change.
3. Inject `08_REGRESSION_TEST_PROMPT` to prove behavior is identical.
4. Inject `09_DOCUMENTATION_UPDATE_PROMPT` to update the Data Dictionary or Dependency Graph.

### 5. Major Architecture Change
1. Inject `03_FEATURE_PLANNING_PROMPT`
2. *(Wait for user approval)*
3. Inject `04_FEATURE_IMPLEMENTATION_PROMPT`
4. Inject `09_DOCUMENTATION_UPDATE_PROMPT` (Must create a new ADR).
5. Inject `10_AI_HANDOFF_UPDATE_PROMPT`

### 6. Release Workflow
1. Inject `11_RELEASE_CHECKLIST`
2. *(Verify all boxes are checked)*
3. Inject `10_AI_HANDOFF_UPDATE_PROMPT`
