You are an expert AI backend developer integrating Firebase for AttendanceDash Pro.

# PREREQUISITES
Before executing this prompt, you MUST:
1. Read `docs/17_AI_HANDOFF.md` and `docs/22_AI_WORKING_CONTEXT.md`.
2. Understand the existing data structures in `docs/20_DATA_DICTIONARY.md`.

# INSTRUCTIONS

Modify Firebase backend operations with extreme caution to prevent data loss or sync loops.

### 1. Firebase Version
The project uses the Firebase **compat** SDK via CDN (`firebase.firestore()`). Do NOT use the modern modular SDK (`getFirestore(app)`).

### 2. Local-First Hydration
Firestore is secondary. `AppState` is always hydrated from `localStorage` first for instant 50ms startup. Cloud sync happens in the background. Do not block the initial render waiting for Firestore.

### 3. Cloud Sync Debounce
All mutations (clicking attendance, creating events) must flow through `triggerCloudSync()` in `storage.js`, which uses a 1000ms debounce to batch writes and prevent quota exhaustion.

### 4. Firestore Security Rules
If you are persisting a new field to the `students/{uid}` document, you MUST update `firestore.rules`.
- Only allow fields explicitly defined in the schema.
- Validate types (e.g., `request.resource.data.newField is list`).
- Ensure users can only read/write their own document.

### 5. Migration Strategy
If changing an existing data structure, write a seamless migration block in `app.js` to convert legacy user data into the new format on load. Do not break existing users.
