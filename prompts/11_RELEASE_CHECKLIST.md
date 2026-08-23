You are an expert AI release manager preparing a production deployment for AttendanceDash Pro.

# PREREQUISITES
Before executing this prompt, you MUST:
1. Read `docs/17_AI_HANDOFF.md` and `docs/22_AI_WORKING_CONTEXT.md`.

# INSTRUCTIONS

Generate and complete the following release checklist artifact. Do not deploy until all items are verified.

### Release Checklist

#### 1. Architecture Review
- [ ] No duplicated business logic exists.
- [ ] Engines strictly follow the layered dependency graph.
- [ ] `ui.js` remains a pure consumer.

#### 2. Regression Tests
- [ ] Engine tests pass (`npm test`).
- [ ] Attendance math baseline verified.

#### 3. Cross-Platform Verification
- [ ] Verified on Desktop viewport.
- [ ] Verified on Mobile viewport (responsive layouts).
- [ ] Verified on Installed PWA (manifest loaded).

#### 4. Offline & PWA Verification
- [ ] `APP_VERSION` incremented in `utils.js` (forces cache bust).
- [ ] All new JavaScript, CSS, and asset files added to `STATIC_ASSETS` array in `service-worker.js`.
- [ ] Offline hydration from `localStorage` verified.

#### 5. Documentation Verification
- [ ] Project Bible (`/docs`) fully updated.
- [ ] Data Dictionary (`20_DATA_DICTIONARY.md`) reflects latest schema.
- [ ] Changelog (`21_CHANGELOG.md`) populated with release notes.

#### 6. Known Bug Review
- [ ] Review `15_KNOWN_BUGS_AND_TECHNICAL_DEBT.md`. Any critical blockages?
