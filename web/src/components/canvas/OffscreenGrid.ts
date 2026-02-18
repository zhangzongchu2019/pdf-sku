/**
 * 离屏 Canvas 点阵背景生成器 [V1.1 D5]
 * 一次生成 pattern，避免每帧重绘
 */
export class OffscreenGrid {
  private pattern: CanvasPattern | null = null;

  /**
   * 生成点阵 pattern
   * @param ctx - 目标 Canvas 上下文
   * @param dotSize - 点大小 (px)
   * @param gap - 点间距 (px)
   * @param color - 点颜色 rgba
   */
  createPattern(
    ctx: CanvasRenderingContext2D,
    dotSize: number = 1,
    gap: number = 20,
    color: string = "rgba(255, 255, 255, 0.03)",
  ): CanvasPattern | null {
    const offscreen = document.createElement("canvas");
    offscreen.width = gap;
    offscreen.height = gap;
    const offCtx = offscreen.getContext("2d");
    if (!offCtx) return null;

    offCtx.fillStyle = color;
    offCtx.fillRect(0, 0, dotSize, dotSize);

    this.pattern = ctx.createPattern(offscreen, "repeat");
    return this.pattern;
  }

  getPattern(): CanvasPattern | null {
    return this.pattern;
  }

  /** Fill background with pattern */
  fillBackground(
    ctx: CanvasRenderingContext2D,
    width: number,
    height: number,
  ) {
    if (!this.pattern) return;
    ctx.fillStyle = this.pattern;
    ctx.fillRect(0, 0, width, height);
  }
}
