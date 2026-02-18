import { useEffect } from "react";

/**
 * 生产环境 Long Task 监控 [V1.1 F1]
 * 监控 >thresholdMs 的 long task 并上报
 */
export function useLongTaskMonitor(thresholdMs = 100) {
  useEffect(() => {
    if (import.meta.env.DEV) return;
    if (!("PerformanceObserver" in window)) return;

    const observer = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (entry.duration > thresholdMs) {
          try {
            navigator.sendBeacon?.(
              "/api/v1/metrics/longtask",
              JSON.stringify({
                duration: entry.duration,
                startTime: entry.startTime,
                page: window.location.pathname,
                timestamp: Date.now(),
              }),
            );
          } catch {
            // silent
          }
        }
      }
    });

    try {
      observer.observe({ entryTypes: ["longtask"] });
    } catch {
      // Safari doesn't support longtask
    }

    return () => observer.disconnect();
  }, [thresholdMs]);
}
