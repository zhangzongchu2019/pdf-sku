/**
 * Cache derived preview assets locally.
 * 只缓存缩略图/预览图，不缓存原始大图。
 */
/// <reference lib="webworker" />
declare const self: ServiceWorkerGlobalScope;

const CACHE_NAME = "pdf-sku-derived-images-v2";
const DERIVED_ASSET_PATTERN = /\/api\/v1\/jobs\/[^/]+\/(?:pages\/\d+\/(?:thumbnail|preview)|images\/[^/]+\/(?:thumbnail|preview))/;

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

/* Fetch — cache-first for derived images */
self.addEventListener("fetch", (event) => {
  const { request } = event;

  if (!DERIVED_ASSET_PATTERN.test(request.url)) return;

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
    if (url && DERIVED_ASSET_PATTERN.test(url)) {
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
