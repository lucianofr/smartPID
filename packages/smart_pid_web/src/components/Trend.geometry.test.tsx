/**
 * Geometry regression for the §6.7 recorder.
 *
 * `Trend.test.tsx` only proves the component mounts — and it cannot prove more,
 * because `src/test/setup.ts` kills `getContext` under jsdom and `Trend` skips
 * uPlot entirely there. That blind spot let the trend ship blank: uPlot ran,
 * auto-scaled y, stroked the right colors at the right widths, and mapped every
 * single x to NaN, so the canvas stayed empty while 681 unit tests were green.
 *
 * This suite restores just enough of a canvas to read back COORDINATES: a
 * recording `Path2D` plus a recording 2D context. Nothing is rasterised — the
 * assertions are on the numbers uPlot hands the rasteriser.
 */
import { render, waitFor } from '@testing-library/react';
import { afterAll, beforeAll, beforeEach, describe, expect, it } from 'vitest';
import { Trend, type TrendSeriesData } from './Trend';

interface Point {
  x: number;
  y: number;
}

/** Every Path2D uPlot allocates: series strokes, point markers, gap clips. */
const paths: Point[][] = [];

class RecordingPath2D {
  private readonly points: Point[] = [];
  constructor() {
    paths.push(this.points);
  }
  moveTo(x: number, y: number): void {
    this.points.push({ x, y });
  }
  lineTo(x: number, y: number): void {
    this.points.push({ x, y });
  }
  arc(x: number, y: number): void {
    this.points.push({ x, y });
  }
  bezierCurveTo(_ax: number, _ay: number, _bx: number, _by: number, x: number, y: number): void {
    this.points.push({ x, y });
  }
  rect(): void {}
  closePath(): void {}
  addPath(): void {}
}

/**
 * Style/state properties uPlot writes; everything else resolves to a no-op so
 * the stub tracks uPlot's context usage without a hand-maintained method list.
 */
function recordingContext(canvas: HTMLCanvasElement): CanvasRenderingContext2D {
  const target: Record<string, unknown> = {
    canvas,
    strokeStyle: '',
    fillStyle: '',
    font: '',
    lineWidth: 1,
    lineCap: 'butt',
    lineJoin: 'miter',
    lineDashOffset: 0,
    globalAlpha: 1,
    textAlign: 'start',
    textBaseline: 'alphabetic',
    measureText: () => ({ width: 8 }),
    getTransform: () => ({ a: 1, b: 0, c: 0, d: 1, e: 0, f: 0 }),
    createLinearGradient: () => ({ addColorStop: () => {} }),
  };
  const noop = () => undefined;
  return new Proxy(target, {
    get: (t, prop) => (prop in t ? t[prop as string] : noop),
    set: (t, prop, value) => {
      t[prop as string] = value;
      return true;
    },
  }) as unknown as CanvasRenderingContext2D;
}

const EMPTY: TrendSeriesData = { t: [], pv: [], sp: [], co: [] };
const LIVE: TrendSeriesData = {
  t: [1785115014, 1785115015, 1785115016, 1785115017, 1785115018],
  pv: [84.0, 83.2, 82.1, 80.4, 79.6],
  sp: [50, 50, 50, 50, 50],
  co: [70, 70, 70, 70, 70],
};

let restore: () => void;

beforeAll(() => {
  const uaDescriptor = Object.getOwnPropertyDescriptor(window.navigator, 'userAgent');
  const priorGetContext = HTMLCanvasElement.prototype.getContext;
  const priorPath2D = globalThis.Path2D;

  // `Trend` deliberately skips uPlot when the UA says jsdom (no canvas measure
  // there). Present as a browser so the production path actually runs.
  Object.defineProperty(window.navigator, 'userAgent', {
    value: 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36',
    configurable: true,
  });
  HTMLCanvasElement.prototype.getContext = function getContext(this: HTMLCanvasElement) {
    return recordingContext(this);
  } as unknown as typeof HTMLCanvasElement.prototype.getContext;
  globalThis.Path2D = RecordingPath2D as unknown as typeof Path2D;

  restore = () => {
    if (uaDescriptor) Object.defineProperty(window.navigator, 'userAgent', uaDescriptor);
    HTMLCanvasElement.prototype.getContext = priorGetContext;
    globalThis.Path2D = priorPath2D;
  };
});

afterAll(() => restore());
beforeEach(() => {
  paths.length = 0;
});

describe('Trend geometry', () => {
  it('maps live samples to finite canvas coordinates when data arrives after mount', async () => {
    // Mount order matters: the recorder is built before the first realtime
    // frame, so uPlot starts with an empty series and a [null, null] x range.
    const view = render(<Trend data={EMPTY} ariaLabel="Tendência TIC-E2E" height={280} />);

    view.rerender(
      <Trend
        data={LIVE}
        ariaLabel="Tendência TIC-E2E"
        penTip={{ t: LIVE.t[4], pv: LIVE.pv[4] as number }}
        aiTicks={[]}
        height={280}
      />,
    );

    // uPlot commits on a microtask; wait for the three series paths (PV/SP/CO).
    await waitFor(() => expect(paths.filter((p) => p.length > 0).length).toBeGreaterThanOrEqual(3));

    const drawn = paths.filter((p) => p.length > 0);
    const nan = drawn
      .flat()
      .filter((p) => !Number.isFinite(p.x) || !Number.isFinite(p.y));
    expect({ paths: drawn.length, nanCoords: nan.length }).toEqual({
      paths: drawn.length,
      nanCoords: 0,
    });

    // Finite is not enough: a collapsed or single-sample x range plots every
    // point on one column. A five-second window must occupy real width.
    const spanning = drawn.filter((p) => {
      const xs = p.map((pt) => pt.x);
      return p.length >= 2 && Math.max(...xs) - Math.min(...xs) > 1;
    });
    expect(spanning.length).toBeGreaterThanOrEqual(3);
  });
});
