import "@testing-library/jest-dom";

/* Mock IntersectionObserver */
class MockIntersectionObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.IntersectionObserver = MockIntersectionObserver as unknown as typeof IntersectionObserver;

/* Mock ResizeObserver */
class MockResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = MockResizeObserver as unknown as typeof ResizeObserver;

/* Mock matchMedia */
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
});

/* Mock Canvas */
HTMLCanvasElement.prototype.getContext = (() => ({
  fillRect: () => {},
  clearRect: () => {},
  fillText: () => {},
  measureText: () => ({ width: 0 }),
  beginPath: () => {},
  closePath: () => {},
  moveTo: () => {},
  lineTo: () => {},
  stroke: () => {},
  fill: () => {},
  arc: () => {},
  rect: () => {},
  save: () => {},
  restore: () => {},
  translate: () => {},
  scale: () => {},
  drawImage: () => {},
  setTransform: () => {},
  createLinearGradient: () => ({ addColorStop: () => {} }),
  canvas: { width: 800, height: 600 },
})) as unknown as typeof HTMLCanvasElement.prototype.getContext;
