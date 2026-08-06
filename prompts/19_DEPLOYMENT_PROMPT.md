You are an expert AI DevOps engineer deploying AttendanceDash Pro.

# PREREQUISITES
Before executing this prompt, you MUST:
1. Read `docs/17_AI_HANDOFF.md` and `docs/22_AI_WORKING_CONTEXT.md`.

# INSTRUCTIONS

Execute the deployment process for Firebase Hosting.

### 1. Pre-deployment Validation
Have all regression tests passed? Has the Service Worker `APP_VERSION` been bumped? Has `firestore.rules` been updated to match any new schema fields?

### 2. PWA Manifest Check
Ensure `manifest.json` correctly points to the required icons and that the start URL works offline.

### 3. Deployment Execution
Run `firebase deploy --only hosting,firestore:rules` (or as appropriate). 

### 4. Post-deployment Verification
Instruct the user to hard-refresh their browser and verify the new `APP_VERSION` is printed in the console or visible in the UI.
