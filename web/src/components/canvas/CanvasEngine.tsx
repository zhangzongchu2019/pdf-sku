import { useRef, useEffect, useState, useCallback } from "react";
import type { SKU, Annotation } from "../../types/models";

interface Props {
  imageUrl: string | null;
  skus: SKU[];
  selectedSkuId: string | null;
  onSelectSku: (id: string | null) => void;
  annotations: Partial<Annotation>[];
}

const COLORS = ["#1890ff", "#52c41a", "#faad14", "#eb2f96", "#722ed1", "#13c2c2"];

export default function CanvasEngine({ imageUrl, skus, selectedSkuId, onSelectSku, annotations }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [img, setImg] = useState<HTMLImageElement | null>(null);
  const [scale, setScale] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });

  // Load image
  useEffect(() => {
    if (!imageUrl) return;
    const image = new Image();
    image.crossOrigin = "anonymous";
    image.onload = () => {
      setImg(image);
      // Fit to container
      if (containerRef.current) {
        const containerW = containerRef.current.clientWidth;
        const s = Math.min(1, containerW / image.width);
        setScale(s);
        setOffset({ x: 0, y: 0 });
      }
    };
    image.onerror = () => setImg(null);
    image.src = imageUrl;
  }, [imageUrl]);

  // Render
  const render = useCallback(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;

    const container = containerRef.current;
    if (container) {
      canvas.width = container.clientWidth;
      canvas.height = container.clientHeight;
    }

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.save();
    ctx.translate(offset.x, offset.y);
    ctx.scale(scale, scale);

    // Draw image
    if (img) {
      ctx.drawImage(img, 0, 0);
    } else {
      ctx.fillStyle = "#f5f5f5";
      ctx.fillRect(0, 0, canvas.width / scale, canvas.height / scale);
      ctx.fillStyle = "#999";
      ctx.font = "16px sans-serif";
      ctx.textAlign = "center";
      ctx.fillText("页面图片加载中...", canvas.width / (2 * scale), canvas.height / (2 * scale));
    }

    // Draw SKU bounding boxes
    skus.forEach((sku, i) => {
      if (!sku.source_bbox || sku.source_bbox.length < 4) return;
      const [x1, y1, x2, y2] = sku.source_bbox;
      const color = COLORS[i % COLORS.length];
      const isSelected = sku.sku_id === selectedSkuId;
      const hasAnnotation = annotations.some((a) => a.payload?.sku_id === sku.sku_id);

      ctx.strokeStyle = isSelected ? "#ff4d4f" : hasAnnotation ? "#faad14" : color;
      ctx.lineWidth = isSelected ? 3 : 2;
      ctx.setLineDash(hasAnnotation ? [5, 3] : []);
      ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);

      // Label
      const label = sku.sku_id.slice(-6);
      ctx.fillStyle = ctx.strokeStyle;
      ctx.font = "bold 11px sans-serif";
      ctx.fillText(label, x1 + 2, y1 - 4);
    });

    ctx.restore();
  }, [img, skus, selectedSkuId, annotations, scale, offset]);

  useEffect(() => {
    const raf = requestAnimationFrame(render);
    return () => cancelAnimationFrame(raf);
  }, [render]);

  // Mouse interactions
  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    setScale((s) => Math.max(0.1, Math.min(5, s * delta)));
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button === 1 || e.ctrlKey) {
      setDragging(true);
      setDragStart({ x: e.clientX - offset.x, y: e.clientY - offset.y });
      return;
    }
    // Click to select SKU
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const cx = (e.clientX - rect.left - offset.x) / scale;
    const cy = (e.clientY - rect.top - offset.y) / scale;

    const clicked = skus.find((sku) => {
      if (!sku.source_bbox || sku.source_bbox.length < 4) return false;
      const [x1, y1, x2, y2] = sku.source_bbox;
      return cx >= x1 && cx <= x2 && cy >= y1 && cy <= y2;
    });

    onSelectSku(clicked?.sku_id ?? null);
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (dragging) {
      setOffset({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
    }
  };

  const handleMouseUp = () => setDragging(false);

  return (
    <div ref={containerRef} className="canvas-container">
      <canvas
        ref={canvasRef}
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        style={{ cursor: dragging ? "grabbing" : "crosshair" }}
      />
      <div className="canvas-controls">
        <button onClick={() => setScale((s) => Math.min(5, s * 1.2))}>+</button>
        <span>{Math.round(scale * 100)}%</span>
        <button onClick={() => setScale((s) => Math.max(0.1, s / 1.2))}>-</button>
        <button onClick={() => { setScale(1); setOffset({ x: 0, y: 0 }); }}>↺</button>
      </div>
    </div>
  );
}
