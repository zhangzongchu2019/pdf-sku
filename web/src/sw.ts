/**
 * Service Worker for screenshot caching
 * 缓存截图到 Cache API，减少重复下载
 */
/// <reference lib="webworker" />
declare const self: ServiceWorkerGlobalScope;

const CACHE_NAME = "pdf-sku-screenshots-v1";
const SCREENSHOT_PATTERN = /\/api\/v1\/jobs\/[^/]+\/pages\/\d+\/screenshot/;

/* Install */
self.addEventListener("install", (_event) => {
  self.skipWaiting();
});

/* Activate — clean old caches */
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k.startsWith("pdf-sku-") && k !== CACHE_NAME)
          .map((k) => caches.delete(k)),
      ),
    ),
  );
  self.clients.claim();
});

/* Fetch — cache-first for screenshots */
self.addEventListener("fetch", (event) => {
  const { request } = event;

  // Only cache screenshot requests
  if (!SCREENSHOT_PATTERN.test(request.url)) return;

  event.respondWith(
    caches.open(CACHE_NAME).then(async (cache) => {
      const cached = await cache.match(request);
      if (cached) return cached;

      try {
        const response = await fetch(request);
        if (response.ok) {
          // Clone before caching since response body can only be consumed once
          cache.put(request, response.clone());
        }
        return response;
      } catch {
        // Return 503 if offline and not in cache
        return new Response("Offline", { status: 503 });
      }
    }),
  );
});

/* Message handler for cache management */
self.addEventListener("message", (event) => {
  if (event.data?.type === "CLEAR_SCREENSHOT_CACHE") {
    caches.delete(CACHE_NAME).then(() => {
      event.source?.postMessage({ type: "CACHE_CLEARED" });
    });
  }

  if (event.data?.type === "PREFETCH_SCREENSHOT") {
    const url = event.data.url as string;
    if (url && SCREENSHOT_PATTERN.test(url)) {
      caches.open(CACHE_NAME).then(async (cache) => {
        const existing = await cache.match(url);
        if (!existing) {
          try {
            const response = await fetch(url);
            if (response.ok) {
              await cache.put(url, response);
            }
          } catch {
            // silently ignore prefetch failures
          }
        }
      });
    }
  }
});

export {};
