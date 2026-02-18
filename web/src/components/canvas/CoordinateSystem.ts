/**
 * 坐标系统 — 归一化坐标 ↔ 屏幕像素 转换 [§4.2]
 */
export class CoordinateSystem {
  private imageWidth: number = 1;
  private imageHeight: number = 1;

  zoom: number = 1.0; // 30% ~ 300%
  panX: number = 0;
  panY: number = 0;

  containerWidth: number = 0;
  containerHeight: number = 0;
  private containerRect: DOMRect | null = null;

  setImageSize(w: number, h: number) {
    this.imageWidth = w;
    this.imageHeight = h;
  }

  /** [V1.1 D2] 更新容器位置（ResizeObserver 回调时调用） */
  updateContainerRect(rect: DOMRect) {
    this.containerWidth = rect.width;
    this.containerHeight = rect.height;
    this.containerRect = rect;
  }

  /** 归一化坐标 (0.0~1.0) → 屏幕像素（相对于容器） */
  normalizedToScreen(nx: number, ny: number): [number, number] {
    const renderedW = this.renderedWidth;
    const renderedH = this.renderedHeight;
    const offsetX = (this.containerWidth - renderedW) / 2 + this.panX;
    const offsetY = (this.containerHeight - renderedH) / 2 + this.panY;
    return [nx * renderedW + offsetX, ny * renderedH + offsetY];
  }

  /** 屏幕像素 → 归一化坐标 */
  screenToNormalized(sx: number, sy: number): [number, number] {
    const renderedW = this.renderedWidth;
    const renderedH = this.renderedHeight;
    const offsetX = (this.containerWidth - renderedW) / 2 + this.panX;
    const offsetY = (this.containerHeight - renderedH) / 2 + this.panY;
    return [(sx - offsetX) / renderedW, (sy - offsetY) / renderedH];
  }

  /** [V1.1 D2] 全局鼠标事件坐标 → 容器相对坐标 */
  clientToContainer(clientX: number, clientY: number): [number, number] {
    if (!this.containerRect) return [clientX, clientY];
    return [
      clientX - this.containerRect.left,
      clientY - this.containerRect.top,
    ];
  }

  get renderedWidth(): number {
    return this.imageWidth * this.fitScale * this.zoom;
  }

  get renderedHeight(): number {
    return this.imageHeight * this.fitScale * this.zoom;
  }

  get fitScale(): number {
    if (!this.imageWidth || !this.imageHeight) return 1;
    return Math.min(
      this.containerWidth / this.imageWidth,
      this.containerHeight / this.imageHeight,
    );
  }
}
