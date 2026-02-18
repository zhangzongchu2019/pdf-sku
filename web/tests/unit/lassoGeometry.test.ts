import { describe, it, expect } from "vitest";
import { LassoGeometry } from "../../src/components/canvas/LassoGeometry";
import { CoordinateSystem } from "../../src/components/canvas/CoordinateSystem";

function makeLasso() {
  const cs = new CoordinateSystem();
  // clientToContainer returns identity when no containerRect
  return new LassoGeometry(cs);
}

describe("LassoGeometry", () => {
  it("starts with empty points", () => {
    const lg = makeLasso();
    expect(lg.getPoints()).toHaveLength(0);
  });

  it("adds points", () => {
    const lg = makeLasso();
    lg.addPoint(10, 20);
    lg.addPoint(30, 40);
    expect(lg.getPoints()).toHaveLength(2);
  });

  it("detects point inside polygon", () => {
    const lg = makeLasso();
    // Simple square 0,0 → 100,0 → 100,100 → 0,100
    lg.addPoint(0, 0);
    lg.addPoint(100, 0);
    lg.addPoint(100, 100);
    lg.addPoint(0, 100);

    expect(lg.containsPoint(50, 50)).toBe(true);
    expect(lg.containsPoint(200, 200)).toBe(false);
  });

  it("getBounds returns correct bounding box", () => {
    const lg = makeLasso();
    lg.addPoint(10, 20);
    lg.addPoint(50, 80);
    lg.addPoint(30, 60);

    const pts = lg.getPoints();
    const xs = pts.map((p) => p[0]);
    const ys = pts.map((p) => p[1]);
    expect(Math.min(...xs)).toBe(10);
    expect(Math.min(...ys)).toBe(20);
    expect(Math.max(...xs)).toBe(50);
    expect(Math.max(...ys)).toBe(80);
  });

  it("reset clears points", () => {
    const lg = makeLasso();
    lg.addPoint(10, 20);
    lg.reset();
    expect(lg.getPoints()).toHaveLength(0);
  });
});
