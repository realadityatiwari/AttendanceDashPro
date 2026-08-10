const CACHE_PREFIX = 'attendance-dash-v';
const version = new URL(location).searchParams.get('v') || '1.0.0';
const CACHE_NAME = CACHE_PREFIX + version;

const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/offline.html',
  '/css/styles.css',
  '/css/responsive.css',
  '/js/app.js',
  '/js/auth.js',
  '/js/storage.js',
  '/js/ui.js',
  '/js/attendance-engine.js',
  '/js/laboratory-engine.js',
  '/js/quiz-engine.js',
  '/js/calendar-engine.js',
  '/js/daily-attendance.js',
  '/css/daily-attendance.css',
  '/js/dateContext.js',
  '/js/utils.js',
  '/js/validation.js',
  '/js/firebase.js',
  '/js/feedback.js',
  '/js/pwa.js',
  '/js/events-controller.js',
  '/manifest.json',
  '/timetable.json',
  '/assets/icons/icon-192.png',
  '/assets/icons/icon-512.png',
  '/assets/icons/maskable-512.png'
];

self.addEventListener('install', (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    })
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key.startsWith(CACHE_PREFIX) && key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // 1. Bypass Firebase completely (Network Only)
  if (url.hostname.includes('firestore.googleapis.com') || 
      url.hostname.includes('identitytoolkit.googleapis.com')) {
    return; // browser handles it directly
  }

  // 2. Static Assets (Cache First, fallback to Network)
  const isStatic = STATIC_ASSETS.includes(url.pathname) || url.pathname === '/';
  
  if (isStatic) {
    event.respondWith(
      caches.match(event.request).then((cachedResponse) => {
        if (cachedResponse) return cachedResponse;
        return fetch(event.request).then((networkResponse) => {
          // Optional: cache dynamically if we want, but user wants explicit allowlist
          return networkResponse;
        }).catch(() => {
          // If offline and requesting navigation, serve offline.html
          if (event.request.mode === 'navigate') {
            return caches.match('/offline.html');
          }
        });
      })
    );
    return;
  }

  // 3. Navigation Requests (Network First, fallback to Cache, then offline.html)
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request).catch(() => {
        return caches.match(event.request).then((cachedResponse) => {
          return cachedResponse || caches.match('/offline.html');
        });
      })
    );
    return;
  }

  // 4. Everything else (Network First, fallback to Cache)
  event.respondWith(
    fetch(event.request).catch(() => {
      return caches.match(event.request);
    })
  );
});
