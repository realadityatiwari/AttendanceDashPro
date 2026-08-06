# 12 — PWA and Deployment

**Files**: `js/pwa.js`, `service-worker.js`, `manifest.json`  
**Status**: ✅ PWA complete. Deployment via local server (Firebase Hosting configured but not actively used).

---

## PWA Architecture

The application is a fully compliant Progressive Web App supporting:
- Installation on Android home screen via `beforeinstallprompt`.
- Offline-capable static asset serving via service worker.
- Standalone display mode (no browser chrome).

---

## Service Worker (`service-worker.js`)

### Versioning Strategy

The cache name is versioned using the `v` query parameter passed during registration:

```javascript
// service-worker.js
const version = new URL(location).searchParams.get('v') || '1.0.0';
const CACHE_NAME = 'attendance-dash-v' + version;

// pwa.js
navigator.serviceWorker.register(`/service-worker.js?v=${APP_VERSION}`)
```

`APP_VERSION` is defined in `utils.js` as `'2.0.2'`. To bust the service worker cache for all users, increment `APP_VERSION`. The old cache will be deleted during the `activate` event.

### Caching Strategy

| Request Type | Strategy | Rationale |
|---|---|---|
| Firebase API calls | Network only (bypassed entirely) | Auth/Firestore must always be live |
| Static assets (allowlist) | Cache first, network fallback | Deterministic, fast offline |
| Navigation requests | Network first, cache fallback | Fresh content preferred |
| Everything else | Network first, cache fallback | General fallback |

### Static Asset Allowlist

The following paths are pre-cached during service worker install:
```
/, /index.html, /offline.html, /css/styles.css, /css/responsive.css,
/js/app.js, /js/auth.js, /js/storage.js, /js/ui.js,
/js/attendance-engine.js, /js/laboratory-engine.js, /js/quiz-engine.js,
/js/calendar-engine.js, /js/dateContext.js, /js/utils.js,
/js/validation.js, /js/firebase.js, /js/feedback.js, /js/pwa.js,
/manifest.json, /timetable.json, /assets/icons/icon-192.png,
/assets/icons/icon-512.png, /assets/icons/maskable-512.png
```

> ⚠️ **Note**: `js/events-controller.js` is NOT in the static asset allowlist. It must be added or it won't be available offline.

### Cache Invalidation

Old caches are pruned in the `activate` event:
```javascript
keys.map((key) => {
  if (key.startsWith('attendance-dash-v') && key !== CACHE_NAME) {
    return caches.delete(key);
  }
});
```

---

## Web App Manifest (`manifest.json`)

| Field | Value | Notes |
|---|---|---|
| `name` | AttendanceDash Pro | Full name |
| `short_name` | Attendance | Used on home screen |
| `display` | standalone | No browser chrome |
| `display_override` | ['standalone', 'minimal-ui'] | Fallback hierarchy |
| `orientation` | portrait | Lock to portrait |
| `theme_color` | #1e1e1e | Dark header tint |
| `background_color` | #121212 | Splash screen |
| `start_url` | / | Opens app root |
| `scope` | / | Full app scope |
| `id` | / | Unique install identity |

---

## Install Flow (`js/pwa.js`)

1. On `beforeinstallprompt`: stash the event in `deferredPrompt`, show `#profileInstallAppBtn`.
2. On button click: call `deferredPrompt.prompt()`, await user choice.
3. On `appinstalled`: hide button, clear prompt.
4. If already in `standalone` mode: hide button immediately.

---

## Offline Behavior

If the user navigates while offline:
- Static cached assets load from service worker cache.
- Firebase calls fail silently (network only, no fallback).
- If no cached navigation match: `offline.html` is served.
- `offline.html` shows a simple "You're offline" message.

**Important**: The app's local-first storage means all logged attendance data is still readable offline. The user can view their current attendance even without network. Only cloud sync and Firebase Auth are network-dependent.

---

## Deployment

### Local Development

```bash
npx serve . -p 8080
```

This is the current development server. No build step required.

### Firebase Hosting (Configured, Not Active)

`firebase.json` declares a Firestore config. Firebase Hosting is configured by the `.firebaserc` file:

```json
{"projects": {"default": "attendancedashpro"}}
```

To deploy:
```bash
firebase deploy --only hosting
```

However, the current `firebase.json` does **not** include a `hosting` configuration block. One needs to be added.

### Vercel (Past Deployment)

The application was previously hosted on Vercel. The regression report references Vercel import case-sensitivity issues. The case-sensitivity checker (`check_imports.js`) was built for this environment.

---

## Version Management

`APP_VERSION` in `utils.js` (`'2.0.2'`) drives:
1. Service worker cache key.
2. Feedback metadata payload (`version` field).

To release a new version:
1. Increment `APP_VERSION` in `utils.js`.
2. Redeploy (any hosting provider).
3. All users will get new service worker cache on next visit.

---

## PWA Checklist Status

| Requirement | Status |
|---|---|
| HTTPS (required for SW) | ✅ (Firebase/Vercel provide HTTPS) |
| Service Worker registered | ✅ |
| Web App Manifest | ✅ |
| 192x192 icon | ✅ |
| 512x512 icon | ✅ |
| Maskable icon | ✅ |
| Offline fallback | ✅ |
| `start_url` responds offline | ✅ (via cache) |
| `manifest.id` set | ✅ |
| `events-controller.js` in SW cache | ❌ Missing |
