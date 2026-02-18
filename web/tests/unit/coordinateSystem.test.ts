import { describe, it, expect } from "vitest";
import { CoordinateSystem } from "../../src/components/canvas/CoordinateSystem";

describe("CoordinateSystem", () => {
  function makeCS() {
    const cs = new CoordinateSystem();
    cs.setImageSize(800, 600);
    cs.updateContainerRect({ left: 0, top: 0, width: 800, height: 600, right: 800, bottom: 600, x: 0, y: 0, toJSON: () => ({}) } as DOMRect);
    return cs;
  }

  it("initializes with identity transform", () => {
    const cs = makeCS();
    const [sx, sy] = cs.normalizedToScreen(0, 0);
    // At zoom=1, fitScale=1 so origin maps to top-left offset
    expect(typeof sx).toBe("number");
    expect(typeof sy).toBe("number");
  });

  it("converts screen to normalized coordinates", () => {
    const cs = makeCS();
    const [nx, ny] = cs.screenToNormalized(400, 300);
    // Center of 800x600 container with 800x600 image at zoom 1 => (0.5, 0.5)
    expect(nx).toBeCloseTo(0.5, 1);
    expect(ny).toBeCloseTo(0.5, 1);
  });

  it("applies zoom correctly", () => {
    const cs = makeCS();
    cs.zoom = 2;
    const w = cs.renderedWidth;
    expect(w).toBe(1600); // 800 * fitScale(1) * zoom(2)
  });

  it("clamps zoom property manually", () => {
    const cs = makeCS();
    cs.zoom = 0.3;
    expect(cs.zoom).toBe(0.3);
    cs.zoom = 3.0;
    expect(cs.zoom).toBe(3.0);
  });

  it("applies pan offset", () => {
    const cs = makeCS();
    cs.panX = 50;
    cs.panY = 30;
    const [sx, sy] = cs.normalizedToScreen(0, 0);
    // panX shifts the screen x by 50
    expect(sx).toBe(50);
    expect(sy).toBe(30);
  });
});
