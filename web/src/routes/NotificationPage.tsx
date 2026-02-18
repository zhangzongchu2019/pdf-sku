/**
 * 通知中心页 /notifications
 */
import { useNotificationStore } from "../stores/notificationStore";

const levelColors: Record<string, string> = {
  urgent: "#EF4444",
  warning: "#F59E0B",
  info: "#3B82F6",
};

export default function NotificationPage() {
  const notifications = useNotificationStore((s) => s.notifications);
  const markRead = useNotificationStore((s) => s.markRead);
  const clearAll = useNotificationStore((s) => s.clearAll);

  const unreadCount = notifications.filter((n) => !n.read).length;

  return (
    <div style={{ padding: 24, maxWidth: 800, margin: "0 auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <h2 style={{ margin: 0, fontSize: 18, color: "#E2E8F4" }}>
          通知中心
          {unreadCount > 0 && (
            <span style={{ marginLeft: 8, fontSize: 12, padding: "2px 8px", backgroundColor: "#EF444420", borderRadius: 10, color: "#EF4444" }}>
              {unreadCount} 未读
            </span>
          )}
        </h2>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            onClick={() => notifications.filter((n) => !n.read).forEach((n) => markRead(n.id))}
            style={{ padding: "4px 12px", backgroundColor: "transparent", border: "1px solid #2D3548", borderRadius: 4, color: "#94A3B8", cursor: "pointer", fontSize: 12 }}
          >
            全部已读
          </button>
          <button
            onClick={clearAll}
            style={{ padding: "4px 12px", backgroundColor: "transparent", border: "1px solid #2D3548", borderRadius: 4, color: "#94A3B8", cursor: "pointer", fontSize: 12 }}
          >
            清空
          </button>
        </div>
      </div>

      {notifications.length === 0 ? (
        <div style={{ textAlign: "center", padding: 60, color: "#64748B" }}>暂无通知</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {notifications.map((n) => (
            <div
              key={n.id}
              onClick={() => { if (!n.read) markRead(n.id); }}
              style={{
                padding: "12px 16px",
                backgroundColor: n.read ? "transparent" : "#1E293B33",
                border: "1px solid #2D354866",
                borderRadius: 6,
                cursor: n.read ? "default" : "pointer",
                borderLeft: `3px solid ${levelColors[n.level] ?? "#64748B"}`,
                display: "flex",
                justifyContent: "space-between",
                alignItems: "flex-start",
                gap: 12,
              }}
            >
              <div style={{ flex: 1 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                  {!n.read && (
                    <span style={{ width: 6, height: 6, borderRadius: "50%", backgroundColor: "#3B82F6", flexShrink: 0 }} />
                  )}
                  <span style={{ fontSize: 13, color: "#E2E8F4", fontWeight: n.read ? 400 : 500 }}>
                    {n.message}
                  </span>
                </div>
                <div style={{ fontSize: 11, color: "#64748B", marginLeft: n.read ? 0 : 14 }}>
                  {new Date(n.timestamp).toLocaleString()}
                </div>
              </div>
              <span style={{
                fontSize: 10, padding: "1px 6px",
                backgroundColor: `${levelColors[n.level] ?? "#64748B"}18`,
                color: levelColors[n.level] ?? "#64748B",
                borderRadius: 3, flexShrink: 0,
              }}>
                {n.level}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
