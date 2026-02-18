/**
 * 时间线抽屉 — 显示 Job 生命周期时间线
 * 从右侧滑入
 */

interface TimelineEvent {
  timestamp: string;
  label: string;
  detail?: string;
  type?: "info" | "success" | "warning" | "error";
}

interface TimelineDrawerProps {
  visible: boolean;
  title: string;
  events: TimelineEvent[];
  onClose: () => void;
}

const TYPE_COLORS: Record<string, string> = {
  info: "#22D3EE",
  success: "#22C55E",
  warning: "#F59E0B",
  error: "#EF4444",
};

export function TimelineDrawer({
  visible,
  title,
  events,
  onClose,
}: TimelineDrawerProps) {
  if (!visible) return null;

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 9000,
        display: "flex",
      }}
    >
      {/* Backdrop */}
      <div
        style={{ flex: 1, backgroundColor: "rgba(0,0,0,0.4)" }}
        onClick={onClose}
      />

      {/* Drawer */}
      <div
        style={{
          width: 400,
          backgroundColor: "#1E2536",
          borderLeft: "1px solid #2D3548",
          display: "flex",
          flexDirection: "column",
          animation: "slideInRight 0.2s ease",
        }}
      >
        {/* Header */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            padding: "16px 20px",
            borderBottom: "1px solid #2D3548",
          }}
        >
          <h3 style={{ margin: 0, fontSize: 14, color: "#E2E8F4" }}>
            {title}
          </h3>
          <button
            onClick={onClose}
            style={{
              background: "none",
              border: "none",
              color: "#64748B",
              cursor: "pointer",
              fontSize: 18,
            }}
          >
            ✕
          </button>
        </div>

        {/* Timeline */}
        <div style={{ flex: 1, overflow: "auto", padding: 20 }}>
          {events.length === 0 ? (
            <div style={{ color: "#64748B", fontSize: 13 }}>暂无事件</div>
          ) : (
            events.map((evt, i) => {
              const color = TYPE_COLORS[evt.type ?? "info"];
              return (
                <div
                  key={i}
                  style={{
                    display: "flex",
                    gap: 12,
                    marginBottom: 20,
                    position: "relative",
                  }}
                >
                  {/* Line */}
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      width: 16,
                    }}
                  >
                    <span
                      style={{
                        width: 10,
                        height: 10,
                        borderRadius: "50%",
                        backgroundColor: color,
                        flexShrink: 0,
                      }}
                    />
                    {i < events.length - 1 && (
                      <span
                        style={{
                          flex: 1,
                          width: 1,
                          backgroundColor: "#2D3548",
                          marginTop: 4,
                        }}
                      />
                    )}
                  </div>

                  {/* Content */}
                  <div style={{ flex: 1, paddingTop: 0 }}>
                    <div
                      style={{
                        fontSize: 12,
                        color: "#E2E8F4",
                        fontWeight: 500,
                        marginBottom: 2,
                      }}
                    >
                      {evt.label}
                    </div>
                    <div style={{ fontSize: 11, color: "#64748B" }}>
                      {new Date(evt.timestamp).toLocaleString()}
                    </div>
                    {evt.detail && (
                      <div
                        style={{
                          fontSize: 11,
                          color: "#94A3B8",
                          marginTop: 4,
                        }}
                      >
                        {evt.detail}
                      </div>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}

export default TimelineDrawer;
