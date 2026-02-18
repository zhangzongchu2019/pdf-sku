import { useState, useRef, useEffect, useLayoutEffect, type ReactNode } from "react";

/**
 * 右键上下文菜单 [V1.1 A1]
 */
export interface ContextMenuItem {
  label: string;
  icon?: ReactNode;
  shortcut?: string;
  danger?: boolean;
  disabled?: boolean;
  onClick: () => void;
}

interface ContextMenuProps {
  x: number;
  y: number;
  items: ContextMenuItem[];
  onClose: () => void;
}

export function ContextMenu({ x, y, items, onClose }: ContextMenuProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState({ x, y });

  // Viewport boundary clamp
  useLayoutEffect(() => {
    if (!ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    const clampedX = Math.min(x, window.innerWidth - rect.width - 8);
    const clampedY = Math.min(y, window.innerHeight - rect.height - 8);
    setPos({ x: Math.max(8, clampedX), y: Math.max(8, clampedY) });
  }, [x, y]);

  // Click outside to close
  useEffect(() => {
    const handleClickOutside = () => onClose();
    document.addEventListener("click", handleClickOutside);
    return () => document.removeEventListener("click", handleClickOutside);
  }, [onClose]);

  return (
    <div
      ref={ref}
      role="menu"
      aria-label="上下文菜单"
      style={{
        position: "fixed",
        left: pos.x,
        top: pos.y,
        zIndex: 9999,
        backgroundColor: "#242B3D",
        border: "1px solid #2D3548",
        borderRadius: 6,
        boxShadow: "0 4px 16px rgba(0,0,0,0.3)",
        padding: "4px 0",
        minWidth: 180,
      }}
    >
      {items.map((item, i) => (
        <button
          key={i}
          role="menuitem"
          disabled={item.disabled}
          onClick={() => {
            item.onClick();
            onClose();
          }}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            width: "100%",
            padding: "6px 12px",
            border: "none",
            backgroundColor: "transparent",
            color: item.danger ? "#F87171" : item.disabled ? "#4B5563" : "#E2E8F4",
            fontSize: 13,
            cursor: item.disabled ? "not-allowed" : "pointer",
            textAlign: "left",
          }}
          onMouseEnter={(e) => {
            if (!item.disabled)
              e.currentTarget.style.backgroundColor = "#2D3548";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = "transparent";
          }}
        >
          <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
            {item.icon && <span>{item.icon}</span>}
            <span>{item.label}</span>
          </span>
          {item.shortcut && (
            <span style={{ color: "#64748B", fontSize: 11, marginLeft: 16 }}>
              {item.shortcut}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}

export default ContextMenu;
