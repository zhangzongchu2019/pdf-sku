import { useState, useEffect } from "react";
import type { SLALevel } from "../types/models";

function pad(n: number) {
  return n.toString().padStart(2, "0");
}

/**
 * SLA 倒计时 — requestAnimationFrame 驱动，4 级紧急度
 */
export function useSLATimer(deadline: string | null, slaLevel: SLALevel = "NORMAL") {
  const [remaining, setRemaining] = useState("");
  const [urgency, setUrgency] = useState<"normal" | "warning" | "critical">("normal");

  useEffect(() => {
    if (!deadline) return;
    const deadlineMs = new Date(deadline).getTime();

    let rafId: number;
    const tick = () => {
      const diff = deadlineMs - Date.now();
      if (diff <= 0) {
        setRemaining("00:00");
        setUrgency("critical");
        return;
      }
      const h = Math.floor(diff / 3600000);
      const m = Math.floor((diff % 3600000) / 60000);
      const s = Math.floor((diff % 60000) / 1000);
      setRemaining(h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`);

      setUrgency(
        slaLevel === "CRITICAL" || slaLevel === "AUTO_RESOLVE"
          ? "critical"
          : slaLevel === "HIGH"
            ? "warning"
            : "normal",
      );
      rafId = requestAnimationFrame(tick);
    };
    rafId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafId);
  }, [deadline, slaLevel]);

  return { remaining, urgency };
}
