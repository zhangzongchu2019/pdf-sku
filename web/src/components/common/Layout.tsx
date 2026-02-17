import React from "react";
import { Link, useLocation } from "react-router-dom";
import { useNotificationStore } from "../../stores/notificationStore";
import { useSSEStore } from "../../stores/sseStore";

const NAV = [
  { path: "/", label: "仪表盘", icon: "📊" },
  { path: "/upload", label: "上传", icon: "📤" },
  { path: "/jobs", label: "任务列表", icon: "📋" },
  { path: "/tasks", label: "标注队列", icon: "✏️" },
  { path: "/config", label: "配置", icon: "⚙️" },
];

export default function Layout({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const notifications = useNotificationStore((s) => s.notifications);
  const removeNotification = useNotificationStore((s) => s.remove);
  const sseConnected = useSSEStore((s) => s.connected);

  return (
    <div className="app-layout">
      <nav className="sidebar">
        <div className="sidebar-header">
          <h1 className="logo">PDF-SKU</h1>
          <span className={`sse-indicator ${sseConnected ? "connected" : "disconnected"}`}>
            {sseConnected ? "● 已连接" : "○ 未连接"}
          </span>
        </div>
        <ul className="nav-list">
          {NAV.map((item) => (
            <li key={item.path}>
              <Link
                to={item.path}
                className={`nav-link ${location.pathname === item.path ? "active" : ""}`}
              >
                <span className="nav-icon">{item.icon}</span>
                <span>{item.label}</span>
              </Link>
            </li>
          ))}
        </ul>
      </nav>

      <main className="main-content">
        {children}
      </main>

      <div className="notification-container">
        {notifications.map((n) => (
          <div key={n.id} className={`notification notification-${n.type}`}
               onClick={() => removeNotification(n.id)}>
            {n.message}
          </div>
        ))}
      </div>
    </div>
  );
}
