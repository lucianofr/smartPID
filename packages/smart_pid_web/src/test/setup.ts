import '@testing-library/jest-dom/vitest';

// jsdom has no canvas 2D context; uPlot defers a draw to a microtask that throws
// on ctx.clearRect after the component's synchronous try/catch has returned.
// Stub a no-op 2D context so charts mount without unhandled async errors in tests.
if (typeof HTMLCanvasElement !== 'undefined') {
  HTMLCanvasElement.prototype.getContext = (() =>
    ({
      canvas: { width: 0, height: 0 },
      clearRect: () => {},
      fillRect: () => {},
      strokeRect: () => {},
      beginPath: () => {},
      moveTo: () => {},
      lineTo: () => {},
      stroke: () => {},
      fill: () => {},
      save: () => {},
      restore: () => {},
      translate: () => {},
      scale: () => {},
      rect: () => {},
      clip: () => {},
      closePath: () => {},
      setLineDash: () => {},
      measureText: () => ({ width: 0 }),
      fillText: () => {},
      arc: () => {},
      lineWidth: 1,
      strokeStyle: '',
      fillStyle: '',
      font: '',
    })) as unknown as typeof HTMLCanvasElement.prototype.getContext;
}

// jsdom lacks ResizeObserver; @tanstack/react-virtual instantiates one to track the
// scroll element. A no-op stand-in keeps the virtualizer happy (size is fed via the
// element's offsetWidth/offsetHeight, which AlarmPanel.test stubs to a real viewport).
if (!('ResizeObserver' in globalThis)) {
  class ResizeObserverStub {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  }
  (globalThis as unknown as { ResizeObserver: typeof ResizeObserverStub }).ResizeObserver =
    ResizeObserverStub;
}

// jsdom lacks matchMedia; ThemeProvider/reduced-motion checks need it.
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
