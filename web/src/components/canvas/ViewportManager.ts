import { CoordinateSystem } from "./CoordinateSystem";

/**
 * 视口管理（缩放 + 平移）[§4.3]
 */
export class ViewportManager {
  private coords: CoordinateSystem;
  private onRender: (() => void) | null = null;
  private MIN_ZOOM = 0.3;
  private MAX_ZOOM = 3.0;

  constructor(coords: CoordinateSystem) {
    this.coords = coords;
  }

  setRenderCallback(cb: () => void) {
    this.onRender = cb;
  }

  /** 滚轮缩放：基于鼠标位置 */
  handleWheel(e: WheelEvent) {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    const newZoom = clamp(
      this.coords.zoom * delta,
      this.MIN_ZOOM,
      this.MAX_ZOOM,
    );

    const [mx, my] = [e.offsetX, e.offsetY];
    const ratio = newZoom / this.coords.zoom;
    this.coords.panX = mx - (mx - this.coords.panX) * ratio;
    this.coords.panY = my - (my - this.coords.panY) * ratio;
    this.coords.zoom = newZoom;
    this.requestRender();
  }

  /** Alt+拖拽 / 中键平移 */
  handlePan(dx: number, dy: number) {
    this.coords.panX += dx;
    this.coords.panY += dy;
    this.requestRender();
  }

  /** 适配窗口 (Ctrl+Shift+0) */
  fitToContainer() {
    this.coords.zoom = 1.0;
    this.coords.panX = 0;
    this.coords.panY = 0;
    this.requestRender();
  }

  get offsetX() {
    return (
      (this.coords.containerWidth - this.coords.renderedWidth) / 2 +
      this.coords.panX
    );
  }

  get offsetY() {
    return (
      (this.coords.containerHeight - this.coords.renderedHeight) / 2 +
      this.coords.panY
    );
  }

  get effectiveScale() {
    return this.coords.fitScale * this.coords.zoom;
  }

  get zoom() {
    return this.coords.zoom;
  }

  private rafPending = false;
  private requestRender() {
    if (this.rafPending) return;
    this.rafPending = true;
    requestAnimationFrame(() => {
      this.rafPending = false;
      this.onRender?.();
    });
  }
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}
