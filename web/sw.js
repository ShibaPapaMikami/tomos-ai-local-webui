const CACHE_NAME = "gemma4-pwa-0.8.231-greeting-context";
const APP_SHELL = [
  "/",
  "/mobile.html",
  "/offline.html",
  "/manifest.webmanifest",
  "/styles.css?v=0.8.230-purpose-routing",
  "/i18n.js?v=0.8.230-purpose-routing",
  "/utils.js?v=0.8.209-tomos53",
  "/translation.js?v=0.8.209-tomos53",
  "/local-tools.js?v=0.8.209-tomos53",
  "/weather.js?v=0.8.209-tomos53",
  "/image-tools.js?v=0.8.209-tomos53",
  "/asr.js?v=0.8.209-tomos53",
  "/attachments.js?v=0.8.209-tomos53",
  "/composer.js?v=0.8.209-tomos53",
  "/workspace.js?v=0.8.225-note-no-save",
  "/training.js?v=0.8.209-tomos53",
  "/tomos-character-core.js?v=0.8.209-tomos53",
  "/character-core-adapter.js?v=0.8.209-tomos53",
  "/character.js?v=0.8.209-tomos53",
  "/person-name-fortune.js?v=0.8.209-tomos53",
  "/person-relationship.js?v=0.8.209-tomos53",
  "/models.js?v=0.8.230-purpose-routing",
  "/messages.js?v=0.8.211-listground1",
  "/sidebar.js?v=0.8.219-searchfix",
  "/settings.js?v=0.8.230-purpose-routing",
  "/management.js?v=0.8.222-note-pack-error",
  "/router.js?v=0.8.209-tomos53",
  "/search.js?v=0.8.227-youtube-grounded",
  "/pwa.js?v=0.8.231-greeting-context",
  "/mobile-standalone.js?v=0.8.209-tomos53",
  "/app.js?v=0.8.231-greeting-context",
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
