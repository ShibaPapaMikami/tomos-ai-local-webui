const CACHE_NAME = "gemma4-pwa-0.8.205-tomos1";
const APP_SHELL = [
  "/",
  "/mobile.html",
  "/offline.html",
  "/manifest.webmanifest",
  "/styles.css?v=0.8.205-tomos1",
  "/i18n.js?v=0.8.205-tomos1",
  "/utils.js?v=0.8.205-tomos1",
  "/translation.js?v=0.8.205-tomos1",
  "/local-tools.js?v=0.8.205-tomos1",
  "/weather.js?v=0.8.205-tomos1",
  "/image-tools.js?v=0.8.205-tomos1",
  "/asr.js?v=0.8.205-tomos1",
  "/attachments.js?v=0.8.205-tomos1",
  "/composer.js?v=0.8.205-tomos1",
  "/workspace.js?v=0.8.205-tomos1",
  "/training.js?v=0.8.205-tomos1",
  "/character.js?v=0.8.205-tomos1",
  "/models.js?v=0.8.205-tomos1",
  "/messages.js?v=0.8.205-tomos1",
  "/sidebar.js?v=0.8.205-tomos1",
  "/settings.js?v=0.8.205-tomos1",
  "/management.js?v=0.8.205-tomos1",
  "/router.js?v=0.8.205-tomos1",
  "/search.js?v=0.8.205-tomos1",
  "/pwa.js?v=0.8.205-tomos1",
  "/mobile-standalone.js?v=0.8.205-tomos1",
  "/app.js?v=0.8.205-tomos1",
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
