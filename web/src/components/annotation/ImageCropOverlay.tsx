/**
 * ImageCropOverlay: 在页面截图上画框裁剪商品子图。
 *
 * 用法:
 * - mode="add": 添加新子图
 * - mode="adjust": 调整已有子图的裁剪范围 (传入 initialBbox)
 */
import { useRef, useState, useCallback, useEffect } from "react";

interface Props {
  screenshotUrl: string;
  mode: "add" | "adjust";
  initialBbox?: number[]; // [x1,y1,x2,y2] 调整模式的初始框
  onConfirm: (bbox: number[]) => void;
  onCancel: () => void;
}

export default function ImageCropOverlay({
  screenshotUrl,
  mode,
  initialBbox,
  onConfirm,
  onCancel,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const [drawing, setDrawing] = useState(false);
  const [start, setStart] = useState<{ x: number; y: number } | null>(null);
  const [current, setCurrent] = useState<{ x: number; y: number } | null>(null);
  const [bbox, setBbox] = useState<number[] | null>(initialBbox || null);
  const [imgNatural, setImgNatural] = useState({ w: 0, h: 0 });

  // 拖拽调整句柄
  const [resizing, setResizing] = useState<string | null>(null);
  const resizeStart = useRef<{ x: number; y: number; bbox: number[] } | null>(null);

  const getRelPos = useCallback(
    (e: React.MouseEvent | MouseEvent) => {
      const img = imgRef.current;
      if (!img) return { x: 0, y: 0 };
      const rect = img.getBoundingClientRect();
      const scaleX = imgNatural.w / rect.width;
      const scaleY = imgNatural.h / rect.height;
      return {
        x: Math.round((e.clientX - rect.left) * scaleX),
        y: Math.round((e.clientY - rect.top) * scaleY),
      };
    },
    [imgNatural],
  );

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if (resizing) return;
      const pos = getRelPos(e);
      setStart(pos);
      setCurrent(pos);
      setDrawing(true);
      setBbox(null);
    },
    [getRelPos, resizing],
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (drawing && start) {
        setCurrent(getRelPos(e));
      }
    },
    [drawing, start, getRelPos],
  );

  const handleMouseUp = useCallback(() => {
    if (drawing && start && current) {
      const x1 = Math.min(start.x, current.x);
      const y1 = Math.min(start.y, current.y);
      const x2 = Math.max(start.x, current.x);
      const y2 = Math.max(start.y, current.y);
      if (x2 - x1 > 10 && y2 - y1 > 10) {
        setBbox([x1, y1, x2, y2]);
      }
    }
    setDrawing(false);
    setStart(null);
    setCurrent(null);
  }, [drawing, start, current]);

  // 全局 mouse up (防止鼠标移出容器)
  useEffect(() => {
    const up = () => {
      if (drawing) handleMouseUp();
      if (resizing) setResizing(null);
    };
    window.addEventListener("mouseup", up);
    return () => window.removeEventListener("mouseup", up);
  }, [drawing, handleMouseUp, resizing]);

  // Resize handles for adjusting bbox
  const handleResizeStart = useCallback(
    (handle: string, e: React.MouseEvent) => {
      e.stopPropagation();
      if (!bbox) return;
      setResizing(handle);
      resizeStart.current = { x: e.clientX, y: e.clientY, bbox: [...bbox] };
    },
    [bbox],
  );

  useEffect(() => {
    if (!resizing || !resizeStart.current) return;
    const onMove = (e: MouseEvent) => {
      const img = imgRef.current;
      if (!img || !resizeStart.current) return;
      const rect = img.getBoundingClientRect();
      const scaleX = imgNatural.w / rect.width;
      const scaleY = imgNatural.h / rect.height;
      const dx = (e.clientX - resizeStart.current.x) * scaleX;
      const dy = (e.clientY - resizeStart.current.y) * scaleY;
      const ob = resizeStart.current.bbox;
      const nb = [...ob];

      if (resizing.includes("t")) nb[1] = Math.round(ob[1] + dy);
      if (resizing.includes("b")) nb[3] = Math.round(ob[3] + dy);
      if (resizing.includes("l")) nb[0] = Math.round(ob[0] + dx);
      if (resizing.includes("r")) nb[2] = Math.round(ob[2] + dx);

      // Clamp
      nb[0] = Math.max(0, nb[0]);
      nb[1] = Math.max(0, nb[1]);
      nb[2] = Math.min(imgNatural.w, nb[2]);
      nb[3] = Math.min(imgNatural.h, nb[3]);

      if (nb[2] - nb[0] > 10 && nb[3] - nb[1] > 10) {
        setBbox(nb);
      }
    };
    const onUp = () => setResizing(null);
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [resizing, imgNatural]);

  // 显示框的坐标 (相对于渲染图片)
  const getDisplayBox = () => {
    const img = imgRef.current;
    if (!img || !imgNatural.w) return null;
    let b = bbox;
    if (drawing && start && current) {
      b = [
        Math.min(start.x, current.x),
        Math.min(start.y, current.y),
        Math.max(start.x, current.x),
        Math.max(start.y, current.y),
      ];
    }
    if (!b) return null;
    const rect = img.getBoundingClientRect();
    const sx = rect.width / imgNatural.w;
    const sy = rect.height / imgNatural.h;
    return {
      left: b[0] * sx,
      top: b[1] * sy,
      width: (b[2] - b[0]) * sx,
      height: (b[3] - b[1]) * sy,
    };
  };

  const displayBox = getDisplayBox();
  const handleSize = 8;

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 10000,
        backgroundColor: "rgba(0,0,0,0.8)",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          gap: 12,
          alignItems: "center",
          marginBottom: 12,
          color: "#E2E8F0",
          fontSize: 13,
        }}
      >
        <span style={{ fontWeight: 600 }}>
          {mode === "add" ? "🖼 添加商品子图" : "✏️ 调整裁剪范围"}
        </span>
        <span style={{ color: "#64748B" }}>
          在截图上{bbox ? "调整" : "画"}框选择商品区域
        </span>
        {bbox && (
          <span style={{ color: "#22D3EE", fontFamily: "monospace", fontSize: 11 }}>
            [{bbox.map(Math.round).join(", ")}] {bbox[2] - bbox[0]}×{bbox[3] - bbox[1]}px
          </span>
        )}
      </div>

      {/* Image + crop area */}
      <div
        ref={containerRef}
        style={{ position: "relative", cursor: drawing ? "crosshair" : bbox ? "default" : "crosshair" }}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
      >
        <img
          ref={imgRef}
          src={screenshotUrl}
          alt="page"
          draggable={false}
          onLoad={(e) => {
            const img = e.currentTarget;
            setImgNatural({ w: img.naturalWidth, h: img.naturalHeight });
          }}
          style={{
            maxWidth: "85vw",
            maxHeight: "75vh",
            borderRadius: 4,
            border: "1px solid #2D3548",
            userSelect: "none",
          }}
        />

        {/* Selection rectangle */}
        {displayBox && (
          <div
            style={{
              position: "absolute",
              left: displayBox.left,
              top: displayBox.top,
              width: displayBox.width,
              height: displayBox.height,
              border: "2px dashed #22D3EE",
              backgroundColor: "rgba(34,211,238,0.1)",
              pointerEvents: drawing ? "none" : "auto",
            }}
          >
            {/* Resize handles (only when not drawing) */}
            {!drawing && bbox && (
              <>
                {["tl", "tr", "bl", "br", "t", "b", "l", "r"].map((h) => {
                  const pos: React.CSSProperties = {};
                  if (h.includes("t")) pos.top = -handleSize / 2;
                  if (h.includes("b")) pos.bottom = -handleSize / 2;
                  if (h.includes("l")) pos.left = -handleSize / 2;
                  if (h.includes("r")) pos.right = -handleSize / 2;
                  if (h === "t" || h === "b") { pos.left = "50%"; pos.marginLeft = -handleSize / 2; }
                  if (h === "l" || h === "r") { pos.top = "50%"; pos.marginTop = -handleSize / 2; }
                  const cursors: Record<string, string> = {
                    tl: "nw-resize", tr: "ne-resize", bl: "sw-resize", br: "se-resize",
                    t: "n-resize", b: "s-resize", l: "w-resize", r: "e-resize",
                  };
                  return (
                    <div
                      key={h}
                      onMouseDown={(e) => handleResizeStart(h, e)}
                      style={{
                        position: "absolute",
                        ...pos,
                        width: handleSize,
                        height: handleSize,
                        backgroundColor: "#22D3EE",
                        borderRadius: 2,
                        cursor: cursors[h],
                        zIndex: 2,
                      }}
                    />
                  );
                })}
              </>
            )}
          </div>
        )}
      </div>

      {/* Buttons */}
      <div style={{ display: "flex", gap: 12, marginTop: 16 }}>
        <button
          onClick={onCancel}
          style={{
            padding: "6px 20px",
            backgroundColor: "transparent",
            border: "1px solid #475569",
            borderRadius: 4,
            color: "#94A3B8",
            cursor: "pointer",
            fontSize: 13,
          }}
        >
          取消 (Esc)
        </button>
        <button
          disabled={!bbox}
          onClick={() => bbox && onConfirm(bbox)}
          style={{
            padding: "6px 20px",
            backgroundColor: bbox ? "#0EA5E9" : "#1E293B",
            border: "none",
            borderRadius: 4,
            color: bbox ? "#FFF" : "#475569",
            cursor: bbox ? "pointer" : "not-allowed",
            fontSize: 13,
            fontWeight: 600,
          }}
        >
          确认裁剪
        </button>
      </div>
    </div>
  );
}
