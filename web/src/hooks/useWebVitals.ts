import { useEffect } from "react";

/**
 * Web Vitals 上报 Hook [§7.2]
 * 仅在生产环境上报 FCP/LCP/FID/CLS/TTFB
 */
export function useWebVitals() {
  useEffect(() => {
    if (import.meta.env.DEV) return;

    const report = (metric: { name: string; value: number }) => {
      try {
        navigator.sendBeacon?.(
          "/api/v1/metrics/web-vitals",
          JSON.stringify({
            name: metric.name,
            value: metric.value,
            page: window.location.pathname,
            timestamp: Date.now(),
          }),
        );
      } catch {
        // silent
      }
    };

    import("web-vitals").then(({ onFCP, onLCP, onINP, onCLS, onTTFB }) => {
      onFCP(report);
      onLCP(report);
      onINP(report);
      onCLS(report);
      onTTFB(report);
    });
  }, []);
}
