/**
 * 任务锁状态指示器
 * 显示当前任务被谁锁定、何时超时
 */
import { useMemo } from "react";

interface LockStatusIndicatorProps {
  lockedBy: string | null;
  lockedAt: string | null;
  timeoutAt: string | null;
  currentUserId: string;
}

export function LockStatusIndicator({
  lockedBy,
  lockedAt,
  timeoutAt,
  currentUserId,
}: LockStatusIndicatorProps) {
  const isMe = lockedBy === currentUserId;

  const timeLeft = useMemo(() => {
    if (!timeoutAt) return null;
    const diff = new Date(timeoutAt).getTime() - Date.now();
    if (diff <= 0) return "已超时";
    const min = Math.floor(diff / 60000);
    const sec = Math.floor((diff % 60000) / 1000);
    return `${min}:${sec.toString().padStart(2, "0")}`;
  }, [timeoutAt]);

  if (!lockedBy) return null;

  const bgColor = isMe ? "#22D3EE11" : "#EF444411";
  const borderColor = isMe ? "#22D3EE33" : "#EF444433";
  const textColor = isMe ? "#22D3EE" : "#EF4444";
  const label = isMe ? "你已锁定此任务" : `被 ${lockedBy} 锁定`;

  return (
    <div
      role="status"
      aria-label={label}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        padding: "4px 10px",
        backgroundColor: bgColor,
        border: `1px solid ${borderColor}`,
        borderRadius: 6,
        fontSize: 12,
        color: textColor,
      }}
    >
      <span style={{ width: 6, height: 6, borderRadius: "50%", backgroundColor: textColor }} />
      <span>{label}</span>
      {timeLeft && (
        <span style={{ color: "#94A3B8", marginLeft: 4 }}>
          剩余 {timeLeft}
        </span>
      )}
      {lockedAt && (
        <span style={{ color: "#64748B", fontSize: 11, marginLeft: 4 }}>
          {new Date(lockedAt).toLocaleTimeString()}
        </span>
      )}
    </div>
  );
}

export default LockStatusIndicator;
