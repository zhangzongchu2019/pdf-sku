/**
 * 画布性能监控器 [§4.7]
 * 基于帧率自适应降级
 */
export class PerformanceMonitor {
  private fpsBuffer: number[] = [];
  private lastFrame = 0;
  private degradeLevel: "none" | "mild" | "heavy" = "none";

  tick(timestamp: number) {
    if (this.lastFrame) {
      const fps = 1000 / (timestamp - this.lastFrame);
      this.fpsBuffer.push(fps);
      if (this.fpsBuffer.length > 300) this.fpsBuffer.shift(); // 5s window @ 60fps

      if (this.fpsBuffer.length >= 300) {
        const avg =
          this.fpsBuffer.reduce((a, b) => a + b) / this.fpsBuffer.length;
        if (avg < 30) this.degradeLevel = "heavy";
        else if (avg < 45) this.degradeLevel = "mild";
        else this.degradeLevel = "none";
      }
    }
    this.lastFrame = timestamp;
  }

  get level() {
    return this.degradeLevel;
  }

  get avgFps(): number {
    if (this.fpsBuffer.length === 0) return 60;
    return this.fpsBuffer.reduce((a, b) => a + b) / this.fpsBuffer.length;
  }

  reset() {
    this.fpsBuffer = [];
    this.lastFrame = 0;
    this.degradeLevel = "none";
  }
}
