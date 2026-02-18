import { useSLATimer } from "../../hooks/useSLATimer";
import type { SLALevel } from "../../types/models";

/**
 * SLA 状态栏 [§6.4]
 */
interface SLAStatusBarProps {
  deadline: string | null;
  slaLevel: SLALevel;
  taskId: string;
  reworkCount?: number;
}

export function SLAStatusBar({ deadline, slaLevel, taskId, reworkCount = 0 }: SLAStatusBarProps) {
  const { remaining, urgency } = useSLATimer(deadline, slaLevel);

  const bgColor =
    urgency === "critical"
      ? "rgba(248, 113, 113, 0.15)"
      : urgency === "warning"
        ? "rgba(251, 191, 36, 0.15)"
        : "rgba(34, 211, 238, 0.1)";

  const textColor =
    urgency === "critical"
      ? "#F87171"
      : urgency === "warning"
        ? "#FBBF24"
        : "#22D3EE";

  return (
    <div
      role="timer"
      aria-label={`SLA 剩余时间: ${remaining}`}
      aria-live={urgency === "critical" ? "assertive" : "polite"}
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "6px 16px",
        backgroundColor: bgColor,
        borderBottom: `1px solid ${textColor}33`,
        fontSize: 13,
        color: textColor,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <span>⏱ SLA: {remaining || "--:--"}</span>
        <span style={{ color: "#94A3B8", fontSize: 12 }}>
          优先级: {slaLevel}
        </span>
        {reworkCount > 0 && (
          <span style={{ color: "#FBBF24", fontSize: 12 }}>
            返工 ×{reworkCount}
          </span>
        )}
      </div>
      <span style={{ color: "#64748B", fontSize: 11 }}>
        Task: {taskId?.slice(0, 8)}
      </span>
    </div>
  );
}

export default SLAStatusBar;
