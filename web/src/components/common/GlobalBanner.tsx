import { useNotificationStore } from "../../stores/notificationStore";

/**
 * 全局 Banner — urgent 级别通知持久显示 [V1.1 A2]
 */
export function GlobalBanner() {
  const urgentItems = useNotificationStore((s) =>
    s.items.filter((i) => i.level === "urgent" && !i.read),
  );

  if (urgentItems.length === 0) return null;

  const latest = urgentItems[0];
  const markRead = useNotificationStore((s) => s.markRead);

  return (
    <div
      role="alert"
      aria-live="assertive"
      style={{
        backgroundColor: "rgba(248, 113, 113, 0.15)",
        borderBottom: "1px solid #F87171",
        color: "#F87171",
        padding: "8px 16px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        fontSize: 13,
      }}
    >
      <span>🔴 {latest.message}</span>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        {urgentItems.length > 1 && (
          <span style={{ color: "#94A3B8", fontSize: 12 }}>
            +{urgentItems.length - 1} 条紧急通知
          </span>
        )}
        <button
          onClick={() => markRead(latest.id)}
          style={{
            background: "none",
            border: "1px solid #F87171",
            color: "#F87171",
            borderRadius: 4,
            padding: "2px 8px",
            cursor: "pointer",
            fontSize: 12,
          }}
        >
          关闭
        </button>
      </div>
    </div>
  );
}

export default GlobalBanner;
