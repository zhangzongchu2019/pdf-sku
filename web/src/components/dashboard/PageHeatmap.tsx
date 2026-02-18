/**
 * 页面热力图 — Canvas 渲染，每行 20 格，支持 1000 页
 * 按 page_confidence + status 上色
 * hover → tooltip, click → navigate to annotate
 */
import { useRef, useEffect, useState, useCallback } from "react";
import { STATUS_COLORS } from "../../utils/designTokens";

export interface PageHeatmapCell {
  page_no: number;
  status: string;
  confidence?: number;
  page_type?: string;
  duration_ms?: number;
  import_status?: string;
}

interface PageHeatmapProps {
  pages: PageHeatmapCell[];
  onPageClick: (pageNo: number) => void;
}

const CELL_W = 14;
const CELL_H = 18;
const GAP = 2;
const COLS = 20;

const STATUS_COLOR_MAP: Record<string, string> = {
  AI_COMPLETED: "#52C41A",
  HUMAN_COMPLETED: "#1890FF",
  IMPORTED_CONFIRMED: "#1890FF",
  HUMAN_QUEUED: "#FAAD14",
  HUMAN_PROCESSING: "#FAAD14",
  AI_FAILED: "#FF4D4F",
  IMPORT_FAILED: "#FF4D4F",
  DEAD_LETTER: "#FF4D4F",
  BLANK: "#434343",
  PENDING: "#262626",
};

export function PageHeatmap({ pages, onPageClick }: PageHeatmapProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [tooltip, setTooltip] = useState<{
    x: number;
    y: number;
    cell: PageHeatmapCell;
  } | null>(null);

  const rows = Math.ceil(pages.length / COLS);
  const canvasW = COLS * (CELL_W + GAP) - GAP;
  const canvasH = rows * (CELL_H + GAP) - GAP;

  // Draw cells
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = canvasW * dpr;
    canvas.height = canvasH * dpr;
    canvas.style.width = `${canvasW}px`;
    canvas.style.height = `${canvasH}px`;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, canvasW, canvasH);

    pages.forEach((p, i) => {
      const col = i % COLS;
      const row = Math.floor(i / COLS);
      const x = col * (CELL_W + GAP);
      const y = row * (CELL_H + GAP);
      const color =
        STATUS_COLOR_MAP[p.status] ??
        (STATUS_COLORS as Record<string, string>)[p.status] ??
        "#262626";

      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.roundRect(x, y, CELL_W, CELL_H, 2);
      ctx.fill();

      // Confidence overlay (alpha darken for low confidence)
      if (p.confidence !== undefined && p.confidence < 0.8) {
        ctx.fillStyle = `rgba(0,0,0,${0.4 * (1 - p.confidence)})`;
        ctx.beginPath();
        ctx.roundRect(x, y, CELL_W, CELL_H, 2);
        ctx.fill();
      }
    });
  }, [pages, canvasW, canvasH]);

  // Hit test for hover
  const hitTest = useCallback(
    (clientX: number, clientY: number) => {
      const canvas = canvasRef.current;
      if (!canvas) return null;
      const rect = canvas.getBoundingClientRect();
      const mx = clientX - rect.left;
      const my = clientY - rect.top;
      const col = Math.floor(mx / (CELL_W + GAP));
      const row = Math.floor(my / (CELL_H + GAP));
      if (col < 0 || col >= COLS || row < 0 || row >= rows) return null;
      const idx = row * COLS + col;
      return pages[idx] ?? null;
    },
    [pages, rows],
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      const cell = hitTest(e.clientX, e.clientY);
      if (cell) {
        setTooltip({
          x: e.clientX,
          y: e.clientY,
          cell,
        });
      } else {
        setTooltip(null);
      }
    },
    [hitTest],
  );

  const handleClick = useCallback(
    (e: React.MouseEvent) => {
      const cell = hitTest(e.clientX, e.clientY);
      if (cell) onPageClick(cell.page_no);
    },
    [hitTest, onPageClick],
  );

  return (
    <div style={{ position: "relative" }}>
      {/* Legend */}
      <div
        style={{
          display: "flex",
          gap: 12,
          marginBottom: 8,
          flexWrap: "wrap",
        }}
      >
        {Object.entries(STATUS_COLOR_MAP).map(([status, color]) => (
          <div
            key={status}
            style={{ display: "flex", alignItems: "center", gap: 4 }}
          >
            <span
              style={{
                width: 10,
                height: 10,
                borderRadius: 2,
                backgroundColor: color,
                display: "inline-block",
              }}
            />
            <span style={{ fontSize: 10, color: "#64748B" }}>{status}</span>
          </div>
        ))}
      </div>

      <canvas
        ref={canvasRef}
        style={{ cursor: "pointer" }}
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setTooltip(null)}
        onClick={handleClick}
      />

      {/* Tooltip */}
      {tooltip && (
        <div
          style={{
            position: "fixed",
            left: tooltip.x + 12,
            top: tooltip.y + 12,
            pointerEvents: "none",
            zIndex: 1000,
            backgroundColor: "#1E2536",
            border: "1px solid #2D3548",
            borderRadius: 6,
            padding: "6px 10px",
            fontSize: 11,
            color: "#E2E8F4",
            boxShadow: "0 4px 12px rgba(0,0,0,0.4)",
          }}
        >
          <div>
            页面 {tooltip.cell.page_no} · {tooltip.cell.status}
          </div>
          {tooltip.cell.confidence !== undefined && (
            <div style={{ color: "#94A3B8" }}>
              置信度: {(tooltip.cell.confidence * 100).toFixed(0)}%
            </div>
          )}
          {tooltip.cell.page_type && (
            <div style={{ color: "#94A3B8" }}>
              类型: {tooltip.cell.page_type}
            </div>
          )}
          {tooltip.cell.duration_ms !== undefined && (
            <div style={{ color: "#94A3B8" }}>
              耗时: {(tooltip.cell.duration_ms / 1000).toFixed(1)}s
            </div>
          )}
          {tooltip.cell.import_status && (
            <div style={{ color: "#94A3B8" }}>
              导入: {tooltip.cell.import_status === "confirmed" ? "✓确认" : "~假设"}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default PageHeatmap;
