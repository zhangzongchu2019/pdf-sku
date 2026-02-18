import { CoordinateSystem } from "./CoordinateSystem";
import { ViewportManager } from "./ViewportManager";

/**
 * Canvas 渲染引擎 [§4.4]
 * 负责截图渲染 + 离屏点阵背景
 */
export class CanvasRenderer {
  private canvas: HTMLCanvasElement;
  private ctx: CanvasRenderingContext2D;
  private dpr: number;
  private image: HTMLImageElement | null = null;
  private resizeObserver: ResizeObserver;
  private gridPattern: CanvasPattern | null = null;
  private coords: CoordinateSystem;

  constructor(canvas: HTMLCanvasElement, coords: CoordinateSystem) {
    this.canvas = canvas;
    this.coords = coords;
    this.ctx = canvas.getContext("2d")!;
    this.dpr = window.devicePixelRatio || 1;
    this.setupRetina();

    // [V1.1 D1] ResizeObserver
    this.resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        this.setupRetina();
        this.coords.updateContainerRect(
          entry.target.getBoundingClientRect(),
        );
        this.render();
      }
    });
    if (canvas.parentElement) {
      this.resizeObserver.observe(canvas.parentElement);
    }

    // [V1.1 D5] Offscreen Canvas grid pattern
    this.gridPattern = this.createGridPattern();
  }

  private setupRetina() {
    const rect = this.canvas.getBoundingClientRect();
    this.canvas.width = rect.width * this.dpr;
    this.canvas.height = rect.height * this.dpr;
    this.canvas.style.width = `${rect.width}px`;
    this.canvas.style.height = `${rect.height}px`;
    this.ctx.scale(this.dpr, this.dpr);
  }

  /** [V1.1 D5] Offscreen grid pattern */
  private createGridPattern(): CanvasPattern | null {
    const offscreen = document.createElement("canvas");
    offscreen.width = 20;
    offscreen.height = 20;
    const offCtx = offscreen.getContext("2d")!;
    offCtx.fillStyle = "rgba(255, 255, 255, 0.03)";
    offCtx.fillRect(0, 0, 1, 1);
    return this.ctx.createPattern(offscreen, "repeat");
  }

  /** Load page screenshot */
  async loadImage(url: string): Promise<void> {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.crossOrigin = "anonymous";
      img.onload = () => {
        this.image = img;
        this.coords.setImageSize(img.naturalWidth, img.naturalHeight);
        resolve();
      };
      img.onerror = reject;
      img.src = url;
    });
  }

  /** Render frame */
  render(viewport?: ViewportManager) {
    const { ctx } = this;
    const w = this.canvas.width / this.dpr;
    const h = this.canvas.height / this.dpr;

    ctx.clearRect(0, 0, w, h);

    // Grid background
    if (this.gridPattern) {
      ctx.fillStyle = this.gridPattern;
      ctx.fillRect(0, 0, w, h);
    }

    // Page screenshot
    if (this.image && viewport) {
      ctx.save();
      ctx.translate(viewport.offsetX, viewport.offsetY);
      const scale = viewport.effectiveScale;
      ctx.scale(scale, scale);
      ctx.drawImage(this.image, 0, 0, this.image.width, this.image.height);
      ctx.restore();
    }
  }

  destroy() {
    this.resizeObserver.disconnect();
  }
}
