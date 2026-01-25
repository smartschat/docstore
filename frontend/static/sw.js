// Minimal service worker required for PWA install prompt
// This service worker passes all fetch requests through to the network

self.addEventListener('install', (event) => {
  // Skip waiting to activate immediately
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  // Claim all clients immediately
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (event) => {
  // Pass through all requests to network (no caching)
  event.respondWith(fetch(event.request));
});
