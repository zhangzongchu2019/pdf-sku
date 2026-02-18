import { useState, useEffect } from "react";

export type PerfTier = "high" | "medium" | "low";

/**
 * 自适应性能分级 [§7.5]
 * 根据硬件能力和运行时帧率自动降级
 */
export function usePerformanceTier(): PerfTier {
  const [tier, setTier] = useState<PerfTier>("high");

  useEffect(() => {
    const cores = navigator.hardwareConcurrency ?? 4;
    const memory = (navigator as any).deviceMemory ?? 8;

    if (cores <= 2 || memory <= 2) {
      setTier("low");
      return;
    }
    if (cores <= 4 || memory <= 4) {
      setTier("medium");
      return;
    }

    // Runtime FPS monitoring
    const fpsBuffer: number[] = [];
    let lastFrame = 0;
    let rafId: number;

    const tick = (timestamp: number) => {
      if (lastFrame) {
        const fps = 1000 / (timestamp - lastFrame);
        fpsBuffer.push(fps);
        if (fpsBuffer.length > 300) fpsBuffer.shift();

        if (fpsBuffer.length >= 300) {
          const avg = fpsBuffer.reduce((a, b) => a + b) / fpsBuffer.length;
          if (avg < 30) setTier("low");
          else if (avg < 45) setTier("medium");
          else setTier("high");
        }
      }
      lastFrame = timestamp;
      rafId = requestAnimationFrame(tick);
    };

    rafId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafId);
  }, []);

  return tier;
}
