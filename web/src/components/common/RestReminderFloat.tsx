/**
 * 休息提醒浮窗 [V1.1 A4]
 */
interface RestReminderFloatProps {
  onDismiss: () => void;
}

export function RestReminderFloat({ onDismiss }: RestReminderFloatProps) {
  return (
    <div
      role="alert"
      aria-live="polite"
      style={{
        position: "fixed",
        bottom: 24,
        right: 24,
        zIndex: 9000,
        backgroundColor: "#242B3D",
        border: "1px solid #2D3548",
        borderRadius: 12,
        padding: "16px 20px",
        display: "flex",
        alignItems: "center",
        gap: 12,
        boxShadow: "0 4px 24px rgba(0,0,0,0.3)",
        color: "#E2E8F4",
        fontSize: 14,
      }}
    >
      <span style={{ fontSize: 24 }}>☕</span>
      <span>你已连续标注超过 1 小时，建议休息 5 分钟</span>
      <button
        onClick={onDismiss}
        style={{
          background: "none",
          border: "1px solid #2D3548",
          color: "#94A3B8",
          borderRadius: 4,
          padding: "4px 12px",
          cursor: "pointer",
          fontSize: 12,
          marginLeft: 8,
        }}
      >
        知道了
      </button>
    </div>
  );
}

export default RestReminderFloat;
