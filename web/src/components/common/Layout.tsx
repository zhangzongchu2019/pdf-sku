import React from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useNotificationStore } from "../../stores/notificationStore";
import { useSSEStore } from "../../stores/sseStore";
import { useUploadStore } from "../../stores/uploadStore";
import { useAuthStore } from "../../stores/authStore";

/* ---- Navigation sections ---- */
const MAIN_NAV = [
  { path: "/", label: "仪表盘", icon: "📊" },
  { path: "/upload", label: "上传", icon: "📤" },
  { path: "/jobs", label: "任务列表", icon: "📋" },
  { path: "/tasks", label: "标注队列", icon: "✏️" },
];

const ANNOTATOR_NAV = [
  { path: "/annotate/my-stats", label: "我的统计", icon: "📈" },
  { path: "/annotate/history", label: "标注历史", icon: "📖" },
];

const OPS_NAV = [
  { path: "/admin/users", label: "用户管理", icon: "🔐" },
  { path: "/annotators", label: "标注员管理", icon: "👥" },
  { path: "/eval", label: "质量评估", icon: "🏆" },
  { path: "/ops/custom-attr-upgrades", label: "属性升级", icon: "🔄" },
  { path: "/config", label: "配置管理", icon: "⚙️" },
  { path: "/config/import", label: "导入配置", icon: "📦" },
];

const BOTTOM_NAV = [
  { path: "/notifications", label: "通知", icon: "🔔" },
  { path: "/settings", label: "设置", icon: "⚙️" },
];

function NavSection({ title, items, currentPath }: { title?: string; items: typeof MAIN_NAV; currentPath: string }) {
  return (
    <div>
      {title && (
        <div style={{ fontSize: 10, color: "#475569", textTransform: "uppercase", padding: "12px 16px 4px", letterSpacing: "0.05em" }}>
          {title}
        </div>
      )}
      <ul className="nav-list" style={{ listStyle: "none", margin: 0, padding: 0 }}>
        {items.map((item) => {
          const active = item.path === "/" ? currentPath === "/" : currentPath.startsWith(item.path);
          return (
            <li key={item.path}>
              <Link
                to={item.path}
                className={`nav-link ${active ? "active" : ""}`}
              >
                <span className="nav-icon">{item.icon}</span>
                <span>{item.label}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export default function Layout({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const navigate = useNavigate();
  const notifications = useNotificationStore((s) => s.notifications);
  const removeNotification = useNotificationStore((s) => s.remove);
  const unreadCount = notifications.filter((n) => !n.read).length;
  const sseConnected = useSSEStore((s) => s.status === "connected");
  const uploadItems = useUploadStore((s) => s.uploads);
  const activeUploads = uploadItems.filter((f) => f.status === "uploading" || f.status === "hashing");
  const { username, displayName, role, isLoggedIn } = useAuthStore();

  const ROLE_LABELS: Record<string, string> = {
    admin: "管理员",
    uploader: "上传者",
    annotator: "标注员",
    operator: "操作员",
  };

  return (
    <div className="app-layout">
      <nav className="sidebar">
        {/* Header */}
        <div className="sidebar-header">
          <h1 className="logo">PDF-SKU</h1>
          <span className={`sse-indicator ${sseConnected ? "connected" : "disconnected"}`}>
            {sseConnected ? "● 已连接" : "○ 未连接"}
          </span>
        </div>

        {/* Main nav */}
        <NavSection items={MAIN_NAV} currentPath={location.pathname} />

        {/* Annotator section — annotator & admin only */}
        {(role === "annotator" || role === "admin") && (
          <NavSection title="标注" items={ANNOTATOR_NAV} currentPath={location.pathname} />
        )}

        {/* Ops section — admin only */}
        {role === "admin" && (
          <NavSection title="运维" items={OPS_NAV} currentPath={location.pathname} />
        )}

        {/* Spacer */}
        <div style={{ flex: 1 }} />

        {/* Upload progress indicator */}
        {activeUploads.length > 0 && (
          <div
            style={{
              margin: "0 8px 8px",
              padding: "8px 12px",
              backgroundColor: "#22D3EE10",
              border: "1px solid #22D3EE22",
              borderRadius: 6,
              fontSize: 11,
              color: "#22D3EE",
              cursor: "pointer",
            }}
            onClick={() => navigate("/upload")}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ animation: "spin 1s linear infinite", display: "inline-block" }}>⏳</span>
              <span>{activeUploads.length} 个文件上传中</span>
            </div>
            <div
              style={{
                marginTop: 4,
                height: 3,
                backgroundColor: "#22D3EE22",
                borderRadius: 2,
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  height: "100%",
                  width: `${Math.round(activeUploads.reduce((s, f) => s + (f.progress?.percentage ?? 0), 0) / activeUploads.length)}%`,
                  backgroundColor: "#22D3EE",
                  borderRadius: 2,
                  transition: "width 0.3s",
                }}
              />
            </div>
          </div>
        )}

        {/* Bottom nav (notifications + settings) */}
        <div style={{ borderTop: "1px solid #1E293B", paddingTop: 4 }}>
          <ul className="nav-list" style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {BOTTOM_NAV.map((item) => {
              const active = location.pathname.startsWith(item.path);
              return (
                <li key={item.path}>
                  <Link
                    to={item.path}
                    className={`nav-link ${active ? "active" : ""}`}
                    style={{ position: "relative" }}
                  >
                    <span className="nav-icon">{item.icon}</span>
                    <span>{item.label}</span>
                    {item.path === "/notifications" && unreadCount > 0 && (
                      <span style={{
                        position: "absolute",
                        right: 12,
                        top: "50%",
                        transform: "translateY(-50%)",
                        minWidth: 18,
                        height: 18,
                        lineHeight: "18px",
                        textAlign: "center",
                        backgroundColor: "#EF4444",
                        color: "#fff",
                        borderRadius: 9,
                        fontSize: 10,
                        fontWeight: 600,
                        padding: "0 4px",
                      }}>
                        {unreadCount > 99 ? "99+" : unreadCount}
                      </span>
                    )}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>

        {/* User info — click to go to settings */}
        {isLoggedIn && (
          <div
            className="sidebar-user"
            onClick={() => navigate("/settings")}
            style={{ cursor: "pointer" }}
            title="个人信息与设置"
          >
            <div className="sidebar-user-info">
              <span className="sidebar-user-avatar">
                {role === "admin" ? "👑" : role === "annotator" ? "✏️" : "📤"}
              </span>
              <div>
                <div className="sidebar-user-name">{displayName || username}</div>
                <div className="sidebar-user-role">{ROLE_LABELS[role] || role}</div>
              </div>
            </div>
            <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>⚙</span>
          </div>
        )}
      </nav>

      <main className="main-content">
        {children}
      </main>

      {/* Toast notifications */}
      <div className="notification-container">
        {notifications.filter((n) => !n.read).slice(0, 5).map((n) => (
          <div key={n.id} className={`notification notification-${n.type ?? n.level}`}
               onClick={() => removeNotification(n.id)}>
            {n.message}
          </div>
        ))}
      </div>
    </div>
  );
}
