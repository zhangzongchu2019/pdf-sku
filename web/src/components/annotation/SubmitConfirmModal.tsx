/**
 * 提交确认弹窗 — Ctrl+Enter 触发
 * settingsStore.skipSubmitConfirm = true 时直接提交不弹窗
 */
import React, { useEffect, useRef, useCallback } from "react";

interface SubmitConfirmModalProps {
  visible: boolean;
  ungroupedCount: number;
  groupCount: number;
  warningMessages: string[];
  onConfirm: () => void;
  onCancel: () => void;
}

export function SubmitConfirmModal({
  visible,
  ungroupedCount,
  groupCount,
  warningMessages,
  onConfirm,
  onCancel,
}: SubmitConfirmModalProps) {
  const confirmRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (visible) confirmRef.current?.focus();
  }, [visible]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") onConfirm();
    },
    [onCancel, onConfirm],
  );

  if (!visible) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="确认提交"
      onKeyDown={handleKeyDown}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 9999,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: "rgba(0,0,0,0.6)",
      }}
      onClick={onCancel}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: 420,
          backgroundColor: "#1E2536",
          border: "1px solid #2D3548",
          borderRadius: 12,
          padding: 24,
          boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
        }}
      >
        <h3 style={{ margin: "0 0 16px", fontSize: 16, color: "#E2E8F4" }}>
          确认提交标注
        </h3>

        <div style={{ fontSize: 13, color: "#94A3B8", marginBottom: 16 }}>
          <p style={{ margin: "0 0 8px" }}>分组数: {groupCount}</p>
          {ungroupedCount > 0 && (
            <p
              style={{
                margin: "0 0 8px",
                color: "#F59E0B",
                fontWeight: 500,
              }}
            >
              ⚠ 仍有 {ungroupedCount} 个元素未分组
            </p>
          )}
        </div>

        {warningMessages.length > 0 && (
          <div
            style={{
              backgroundColor: "#F59E0B11",
              border: "1px solid #F59E0B33",
              borderRadius: 6,
              padding: 12,
              marginBottom: 16,
            }}
          >
            {warningMessages.map((msg, i) => (
              <p
                key={i}
                style={{ margin: "0 0 4px", fontSize: 12, color: "#F59E0B" }}
              >
                • {msg}
              </p>
            ))}
          </div>
        )}

        <div
          style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}
        >
          <button
            onClick={onCancel}
            style={{
              padding: "8px 16px",
              backgroundColor: "transparent",
              border: "1px solid #2D3548",
              borderRadius: 6,
              color: "#94A3B8",
              cursor: "pointer",
              fontSize: 13,
            }}
          >
            取消
          </button>
          <button
            ref={confirmRef}
            onClick={onConfirm}
            style={{
              padding: "8px 16px",
              backgroundColor: "#22D3EE",
              border: "none",
              borderRadius: 6,
              color: "#0F172A",
              fontWeight: 600,
              cursor: "pointer",
              fontSize: 13,
            }}
          >
            确认提交 (Ctrl+Enter)
          </button>
        </div>
      </div>
    </div>
  );
}

export default SubmitConfirmModal;
