import { useRef, useEffect, useCallback, useState } from "react";
import { CoordinateSystem } from "../canvas/CoordinateSystem";
import { ViewportManager } from "../canvas/ViewportManager";
import { CanvasRenderer as CanvasRendererEngine } from "../canvas/CanvasRendererEngine";
import { LassoGeometry } from "../canvas/LassoGeometry";
import type { AnnotationElement, AnnotationGroup } from "../../types/models";
import { GROUP_COLORS } from "../../utils/designTokens";

/**
 * 标注画布工作台 [§4.1]
 * Canvas 底层 + DOM 覆盖层 混合架构
 */
interface CanvasWorkbenchProps {
  screenshotUrl: string;
  elements: AnnotationElement[];
  groups: AnnotationGroup[];
  selectedElementIds: string[];
  toolMode: "select" | "lasso";
  onSelectElements: (ids: string[], multi: boolean) => void;
  onLassoCapture: (ids: string[]) => void;
  onContextMenu?: (elementId: string, x: number, y: number) => void;
}

export function CanvasWorkbench({
  screenshotUrl,
  elements,
  groups,
  selectedElementIds,
  toolMode,
  onSelectElements,
  onLassoCapture,
  onContextMenu,
}: CanvasWorkbenchProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const coordsRef = useRef(new CoordinateSystem());
  const viewportRef = useRef(new ViewportManager(coordsRef.current));
  const rendererRef = useRef<CanvasRendererEngine | null>(null);
  const lassoRef = useRef(new LassoGeometry(coordsRef.current));
  const [lassoPath, setLassoPath] = useState("");
  const [isLassoing, setIsLassoing] = useState(false);

  // Initialize renderer
  useEffect(() => {
    if (!canvasRef.current) return;
    const renderer = new CanvasRendererEngine(canvasRef.current, coordsRef.current);
    rendererRef.current = renderer;
    viewportRef.current.setRenderCallback(() => renderer.render(viewportRef.current));
    return () => renderer.destroy();
  }, []);

  // Load image
  useEffect(() => {
    if (!screenshotUrl || !rendererRef.current) return;
    rendererRef.current.loadImage(screenshotUrl).then(() => {
      rendererRef.current!.render(viewportRef.current);
    });
  }, [screenshotUrl]);

  // Wheel zoom
  const handleWheel = useCallback((e: WheelEvent) => {
    viewportRef.current.handleWheel(e);
  }, []);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    container.addEventListener("wheel", handleWheel, { passive: false });
    return () => container.removeEventListener("wheel", handleWheel);
  }, [handleWheel]);

  // Lasso tool
  const handlePointerDown = (e: React.PointerEvent) => {
    if (toolMode !== "lasso") return;
    setIsLassoing(true);
    lassoRef.current.reset();
    lassoRef.current.addPoint(e.clientX, e.clientY);
    setLassoPath(lassoRef.current.getSVGPath());
  };

  const handlePointerMove = (e: React.PointerEvent) => {
    if (!isLassoing) return;
    lassoRef.current.addPoint(e.clientX, e.clientY);
    setLassoPath(lassoRef.current.getSVGPath());
  };

  const handlePointerUp = () => {
    if (!isLassoing) return;
    setIsLassoing(false);
    const captured = lassoRef.current.captureElements(elements);
    if (captured.length > 0) {
      onLassoCapture(captured);
    }
    lassoRef.current.reset();
    setLassoPath("");
  };

  // Element click (event delegation)
  const handleOverlayClick = (e: React.MouseEvent) => {
    const target = (e.target as HTMLElement).closest("[data-element-id]");
    const id = target?.getAttribute("data-element-id");
    if (id) {
      onSelectElements([id], e.ctrlKey || e.metaKey);
    }
  };

  // Context menu
  const handleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault();
    const target = (e.target as HTMLElement).closest("[data-element-id]");
    const id = target?.getAttribute("data-element-id");
    if (id && onContextMenu) {
      onContextMenu(id, e.clientX, e.clientY);
    }
  };

  // Group color map
  const groupColorMap = new Map<string, string>();
  groups.forEach((g, i) => {
    g.elementIds.forEach((eid) =>
      groupColorMap.set(eid, GROUP_COLORS[i % GROUP_COLORS.length]),
    );
  });

  const coords = coordsRef.current;

  return (
    <div
      ref={containerRef}
      data-tour="canvas-workbench"
      style={{
        position: "relative",
        flex: 1,
        overflow: "hidden",
        backgroundColor: "#0F1117",
        cursor: toolMode === "lasso" ? "crosshair" : "default",
      }}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
    >
      {/* Canvas layer */}
      <canvas
        ref={canvasRef}
        style={{ width: "100%", height: "100%", display: "block" }}
      />

      {/* DOM overlay - elements */}
      <div
        style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0 }}
        onClick={handleOverlayClick}
        onContextMenu={handleContextMenu}
      >
        {elements.map((el) => {
          const [sx, sy] = coords.normalizedToScreen(el.bbox.x, el.bbox.y);
          const sw = el.bbox.w * coords.renderedWidth;
          const sh = el.bbox.h * coords.renderedHeight;
          const isSelected = selectedElementIds.includes(el.id);
          const groupColor = groupColorMap.get(el.id);

          return (
            <div
              key={el.id}
              data-element-id={el.id}
              role={el.type === "image" ? "img" : "article"}
              aria-label={`${el.type === "image" ? "图片" : "文本"}元素 ${el.id}，AI: ${el.aiRole}，${Math.round(el.confidence * 100)}%`}
              aria-selected={isSelected}
              style={{
                position: "absolute",
                left: 0,
                top: 0,
                transform: `translate3d(${sx}px, ${sy}px, 0)`,
                width: sw,
                height: sh,
                border: `2px solid ${isSelected ? "#22D3EE" : groupColor ?? (el.type === "image" ? "#4ADE80" : "#60A5FA")}`,
                backgroundColor: isSelected
                  ? "rgba(34, 211, 238, 0.1)"
                  : "transparent",
                borderRadius: 2,
                willChange: "transform",
                cursor: "pointer",
                pointerEvents: "auto",
              }}
            >
              <span
                style={{
                  position: "absolute",
                  top: -1,
                  left: -1,
                  padding: "0 4px",
                  fontSize: 10,
                  lineHeight: "16px",
                  backgroundColor: groupColor ?? (el.type === "image" ? "#4ADE80" : "#60A5FA"),
                  color: "#000",
                  borderRadius: "0 0 4px 0",
                }}
              >
                {el.type === "image" ? "IMG" : "TXT"}
              </span>
            </div>
          );
        })}

        {/* Group bounding boxes */}
        {groups.map((g, gi) => {
          const gElements = elements.filter((el) => g.elementIds.includes(el.id));
          if (gElements.length === 0) return null;
          const xs = gElements.map((el) => el.bbox.x);
          const ys = gElements.map((el) => el.bbox.y);
          const x2s = gElements.map((el) => el.bbox.x + el.bbox.w);
          const y2s = gElements.map((el) => el.bbox.y + el.bbox.h);
          const [sx, sy] = coords.normalizedToScreen(Math.min(...xs), Math.min(...ys));
          const [ex, ey] = coords.normalizedToScreen(Math.max(...x2s), Math.max(...y2s));
          const color = GROUP_COLORS[gi % GROUP_COLORS.length];

          return (
            <div
              key={g.id}
              style={{
                position: "absolute",
                left: 0,
                top: 0,
                transform: `translate3d(${sx - 4}px, ${sy - 4}px, 0)`,
                width: ex - sx + 8,
                height: ey - sy + 8,
                border: `1px dashed ${color}`,
                borderRadius: 4,
                pointerEvents: "none",
              }}
            >
              <span
                style={{
                  position: "absolute",
                  top: -14,
                  left: 0,
                  fontSize: 10,
                  color,
                  whiteSpace: "nowrap",
                }}
              >
                {g.label}
              </span>
            </div>
          );
        })}
      </div>

      {/* Lasso SVG */}
      {isLassoing && lassoPath && (
        <svg
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: "100%",
            height: "100%",
            pointerEvents: "none",
          }}
        >
          <path
            d={lassoPath}
            fill="rgba(34, 211, 238, 0.1)"
            stroke="#22D3EE"
            strokeWidth={2}
            strokeDasharray="6 3"
          />
        </svg>
      )}
    </div>
  );
}

export default CanvasWorkbench;
