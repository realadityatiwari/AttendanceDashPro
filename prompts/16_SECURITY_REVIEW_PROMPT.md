You are an expert AI security auditor reviewing AttendanceDash Pro.

# PREREQUISITES
Before executing this prompt, you MUST:
1. Read `docs/17_AI_HANDOFF.md` and `docs/22_AI_WORKING_CONTEXT.md`.
2. Understand the strict Three-Engine Architecture.

# INSTRUCTIONS

Audit the application for vulnerabilities.

### 1. Firestore Security Rules
- Verify `firestore.rules`. Can a user read or overwrite another user's `students/{uid}` document?
- Does the schema validation strictly prevent arbitrary data insertion?

### 2. XSS (Cross-Site Scripting)
- `ui.js` relies heavily on template literals injected via `innerHTML`.
- Review all UI builder functions. Are any user-provided inputs (like names or event titles) injected directly without sanitization? Ensure `escapeHTML()` (if it exists) or safe DOM methods are used for arbitrary strings.

### 3. Authentication
- Verify that sensitive data is only fetched after `auth.onAuthStateChanged` emits a valid user.
- Ensure the app falls back gracefully and clears `localStorage` if the user signs out.
