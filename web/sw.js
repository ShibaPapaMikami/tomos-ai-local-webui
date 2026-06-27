const CACHE_NAME = "gemma4-pwa-0.8.197-mobile-chat-tools-1";
const APP_SHELL = [
  "/",
  "/mobile.html",
  "/offline.html",
  "/manifest.webmanifest",
  "/styles.css?v=0.8.197",
  "/i18n.js?v=0.8.197",
  "/utils.js?v=0.8.197",
  "/translation.js?v=0.8.197",
  "/local-tools.js?v=0.8.197",
  "/weather.js?v=0.8.197",
  "/image-tools.js?v=0.8.197",
  "/asr.js?v=0.8.197",
  "/attachments.js?v=0.8.197",
  "/composer.js?v=0.8.197",
  "/workspace.js?v=0.8.197",
  "/training.js?v=0.8.197",
  "/character.js?v=0.8.197",
  "/models.js?v=0.8.197",
  "/messages.js?v=0.8.197",
  "/sidebar.js?v=0.8.197",
  "/settings.js?v=0.8.197",
  "/management.js?v=0.8.197",
  "/router.js?v=0.8.197",
  "/search.js?v=0.8.197",
  "/pwa.js?v=0.8.197-pwa1",
  "/mobile-standalone.js?v=0.8.197-mobile1",
  "/app.js?v=0.8.197-pwa1",
  "/icons/icon.svg",
  "/icons/icon-192.png",
  "/icons/icon-512.png"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(APP_SHELL))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);
  if (url.pathname.startsWith("/api/")) return;

  if (event.request.mode === "navigate") {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
          return response;
        })
        .catch(() => {
          if (url.pathname === "/m" || url.pathname === "/mobile.html") {
            return caches.match("/mobile.html") || caches.match("/offline.html");
          }
          return caches.match(event.request) || caches.match("/") || caches.match("/mobile.html") || caches.match("/offline.html");
        })
    );
    return;
  }

  event.respondWith(
    caches.match(event.request)
      .then((cached) => cached || fetch(event.request).then((response) => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
        }
        return response;
      }))
      .catch(() => caches.match("/offline.html"))
  );
});
