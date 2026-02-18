/**
 * 批量操作浮层 [V1.1 A5]
 */
import type { AnnotationGroup } from "../../types/models";

interface BatchActionFloaterProps {
  selectedCount: number;
  groups: AnnotationGroup[];
  onCreateGroup: () => void;
  onAddToGroup: (groupId: string) => void;
  onSetRole: (role: string) => void;
  onClearSelection: () => void;
}

export function BatchActionFloater({
  selectedCount,
  groups,
  onCreateGroup,
  onAddToGroup,
  onSetRole,
  onClearSelection,
}: BatchActionFloaterProps) {
  if (selectedCount <= 1) return null;

  return (
    <div
      role="toolbar"
      aria-label="批量操作"
      style={{
        position: "absolute",
        bottom: 16,
        left: "50%",
        transform: "translateX(-50%)",
        display: "flex",
        alignItems: "center",
        gap: 8,
        padding: "8px 16px",
        backgroundColor: "#242B3D",
        border: "1px solid #2D3548",
        borderRadius: 8,
        boxShadow: "0 4px 16px rgba(0,0,0,0.3)",
        zIndex: 100,
        fontSize: 13,
        color: "#E2E8F4",
      }}
    >
      <span style={{ color: "#22D3EE", fontWeight: 500 }}>
        {selectedCount} 个元素已选中
      </span>
      <span style={{ color: "#2D3548" }}>|</span>
      <ActionButton onClick={onCreateGroup}>创建新组 (G)</ActionButton>
      {groups.length > 0 && (
        <div style={{ position: "relative" }}>
          <DropdownButton label="归入分组 →">
            {groups.map((g) => (
              <button
                key={g.id}
                onClick={() => onAddToGroup(g.id)}
                style={{
                  display: "block",
                  width: "100%",
                  padding: "4px 12px",
                  background: "none",
                  border: "none",
                  color: "#E2E8F4",
                  textAlign: "left",
                  cursor: "pointer",
                  fontSize: 12,
                }}
              >
                归入「{g.label}」
              </button>
            ))}
          </DropdownButton>
        </div>
      )}
      <DropdownButton label="标记角色 →">
        {["PRODUCT_MAIN", "DETAIL", "SCENE", "LOGO", "DECORATION", "SIZE_CHART"].map(
          (role) => (
            <button
              key={role}
              onClick={() => onSetRole(role)}
              style={{
                display: "block",
                width: "100%",
                padding: "4px 12px",
                background: "none",
                border: "none",
                color: "#E2E8F4",
                textAlign: "left",
                cursor: "pointer",
                fontSize: 12,
              }}
            >
              {role}
            </button>
          ),
        )}
      </DropdownButton>
      <button
        onClick={onClearSelection}
        style={{
          background: "none",
          border: "none",
          color: "#64748B",
          cursor: "pointer",
          fontSize: 12,
        }}
      >
        取消
      </button>
    </div>
  );
}

function ActionButton({
  onClick,
  children,
}: {
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: "4px 10px",
        backgroundColor: "#22D3EE22",
        border: "1px solid #22D3EE44",
        color: "#22D3EE",
        borderRadius: 4,
        cursor: "pointer",
        fontSize: 12,
      }}
    >
      {children}
    </button>
  );
}

function DropdownButton({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  const [open, setOpen] = React.useState(false);

  return (
    <div
      style={{ position: "relative" }}
      onMouseLeave={() => setOpen(false)}
    >
      <button
        onClick={() => setOpen(!open)}
        style={{
          padding: "4px 10px",
          backgroundColor: "transparent",
          border: "1px solid #2D3548",
          color: "#94A3B8",
          borderRadius: 4,
          cursor: "pointer",
          fontSize: 12,
        }}
      >
        {label}
      </button>
      {open && (
        <div
          style={{
            position: "absolute",
            bottom: "100%",
            left: 0,
            marginBottom: 4,
            backgroundColor: "#242B3D",
            border: "1px solid #2D3548",
            borderRadius: 6,
            padding: "4px 0",
            minWidth: 150,
            boxShadow: "0 -2px 8px rgba(0,0,0,0.2)",
            zIndex: 1,
          }}
        >
          {children}
        </div>
      )}
    </div>
  );
}

import React from "react";

export default BatchActionFloater;
