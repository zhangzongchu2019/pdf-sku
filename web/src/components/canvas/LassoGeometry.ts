import { CoordinateSystem } from "./CoordinateSystem";
import type { AnnotationElement } from "../../types/models";

/**
 * 套索几何计算 [§4.6]
 * 射线法判断多边形包含关系
 */
export class LassoGeometry {
  private points: [number, number][] = [];
  private coords: CoordinateSystem;

  constructor(coords: CoordinateSystem) {
    this.coords = coords;
  }

  /** [V1.1 D2] addPoint uses container-relative coords */
  addPoint(clientX: number, clientY: number) {
    const [cx, cy] = this.coords.clientToContainer(clientX, clientY);
    this.points.push([cx, cy]);
  }

  getSVGPath(): string {
    if (this.points.length < 2) return "";
    return (
      this.points
        .map((p, i) => `${i === 0 ? "M" : "L"} ${p[0]} ${p[1]}`)
        .join(" ") + " Z"
    );
  }

  getPoints(): [number, number][] {
    return this.points;
  }

  /** Ray casting point-in-polygon test */
  containsPoint(px: number, py: number): boolean {
    let inside = false;
    const pts = this.points;
    for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
      const [xi, yi] = pts[i];
      const [xj, yj] = pts[j];
      if (
        yi > py !== yj > py &&
        px < ((xj - xi) * (py - yi)) / (yj - yi) + xi
      ) {
        inside = !inside;
      }
    }
    return inside;
  }

  /** Capture elements whose center falls within lasso */
  captureElements(elements: AnnotationElement[]): string[] {
    return elements
      .filter((el) => {
        const cx = el.bbox.x + el.bbox.w / 2;
        const cy = el.bbox.y + el.bbox.h / 2;
        const [sx, sy] = this.coords.normalizedToScreen(cx, cy);
        return this.containsPoint(sx, sy);
      })
      .map((el) => el.id);
  }

  reset() {
    this.points = [];
  }
}
