import '@testing-library/jest-dom/vitest';

// jsdom has no canvas 2D context; uPlot defers a draw to a microtask that throws
// on ctx.clearRect after the component's synchronous try/catch has returned.
// Stub a no-op 2D context so charts mount without unhandled async errors in tests.
if (typeof HTMLCanvasElement !== 'undefined') {
  HTMLCanvasElement.prototype.getContext = (() => ({
    canvas: { width: 0, height: 0 },
    clearRect: () => {}, fillRect: () => {}, strokeRect: () => {}, beginPath: () => {}, moveTo: () => {}, lineTo: () => {}, stroke: () => {}, fill: () => {}, save: () => {}, restore: () => {}, translate: () => {}, scale: () => {}, rect: () => {}, clip: () => {}, closePath: () => {}, setLineDash: () => {}, measureText: () => ({ width: 0 }), fillText: () => {}, arc: () => {}, rotate: () => {}, ellipse: () => {}, createLinearGradient: () => ({ addColorStop: () => {} }),
    lineWidth: 1, strokeStyle: '', fillStyle: '', font: '',
  })) as unknown as typeof HTMLCanvasElement.prototype.getContext;
}

// Disable uPlot in jsdom; its deferred canvas path renderer expects a native context.
// CONSEQUENCE: no test using this setup can observe chart geometry — a recorder
// that strokes every point at NaN looks identical to one that works. Trend.tsx
// shipped blank behind a green suite because of exactly that. Geometry is
// covered by Trend.geometry.test.tsx, which installs its own recording canvas.
if (typeof window !== 'undefined' && /jsdom/i.test(window.navigator.userAgent)) {
  HTMLCanvasElement.prototype.getContext = (() => null) as unknown as typeof HTMLCanvasElement.prototype.getContext;
}

// jsdom lacks ResizeObserver; @tanstack/react-virtual and Trend need one.
if (!('ResizeObserver' in globalThis)) {
  class ResizeObserverStub {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  }
  (globalThis as unknown as { ResizeObserver: typeof ResizeObserverStub }).ResizeObserver =
    ResizeObserverStub;
}
// jsdom lacks Path2D; uPlot constructs one during series path build. Stub a
// no-op constructor so Trend's drawHalo path-read does not throw async.
if (typeof globalThis.Path2D === 'undefined') {
  (globalThis as unknown as { Path2D: new () => unknown }).Path2D = class {
    constructor() {}
  };
}
// jsdom lacks ResizeObserver; @tanstack/react-virtual and Trend need one.
// jsdom lacks matchMedia; reduced-motion checks need it.
if (!window.matchMedia) {
  window.matchMedia = (query: string) =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    }) as unknown as MediaQueryList;
}

// Radix Select/DropdownMenu call these DOM APIs jsdom does not implement.
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}
if (!Element.prototype.hasPointerCapture) {
  Element.prototype.hasPointerCapture = () => false;
  Element.prototype.setPointerCapture = () => {};
  Element.prototype.releasePointerCapture = () => {};
}
// uPlot performs async path building (Path2D, clip/fill) after the component's
// synchronous mount returns; jsdom lacks Path2D. The errors surface as
// vitest "Errors" (not failures) — the actual test outcomes stay green.
// Green here says the environment tolerated the chart, NOT that the chart drew
// anything: see the CONSEQUENCE note above.