/**
 * 拖拽幽灵 — 拖拽元素时的视觉反馈
 * 跟随鼠标移动，显示拖动元素数量
 */
import { useEffect, useState } from "react";

interface DragGhostProps {
  active: boolean;
  count: number;
  color?: string;
}

export function DragGhost({ active, count, color = "#22D3EE" }: DragGhostProps) {
  const [pos, setPos] = useState({ x: 0, y: 0 });

  useEffect(() => {
    if (!active) return;
    const handler = (e: MouseEvent) => setPos({ x: e.clientX, y: e.clientY });
    window.addEventListener("mousemove", handler);
    return () => window.removeEventListener("mousemove", handler);
  }, [active]);

  if (!active || count === 0) return null;

  return (
    <div
      style={{
        position: "fixed",
        left: pos.x + 12,
        top: pos.y + 12,
        pointerEvents: "none",
        zIndex: 10000,
        display: "flex",
        alignItems: "center",
        gap: 6,
        padding: "4px 10px",
        backgroundColor: "#242B3D",
        border: `1px solid ${color}44`,
        borderRadius: 6,
        boxShadow: "0 4px 12px rgba(0,0,0,0.4)",
        fontSize: 12,
        color,
        fontWeight: 500,
        opacity: 0.9,
      }}
    >
      <span
        style={{
          width: 18,
          height: 18,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          backgroundColor: `${color}22`,
          borderRadius: 4,
          fontSize: 11,
        }}
      >
        {count}
      </span>
      <span>个元素</span>
    </div>
  );
}

export default DragGhost;
