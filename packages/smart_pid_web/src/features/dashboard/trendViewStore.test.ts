import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  readTrendView,
  TREND_VIEW_KEY,
  writeTrendView,
  type TrendViewConfig,
} from './trendViewStore';

const DEFAULTS: TrendViewConfig = {
  count: 30,
  unit: 'minuto',
  autoScale: true,
  pvMin: 0,
  pvMax: 100,
  coMin: 0,
  coMax: 100,
};

const PINNED: TrendViewConfig = {
  count: 5,
  unit: 'segundo',
  autoScale: false,
  pvMin: 40,
  pvMax: 60,
  coMin: 10,
  coMax: 90,
};

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

describe('trendViewStore', () => {
  it('returns the caller defaults when nothing is stored', () => {
    expect(readTrendView('panel', 1, DEFAULTS)).toEqual(DEFAULTS);
  });

  it('round-trips a framing', () => {
    writeTrendView('panel', 1, PINNED);
    expect(readTrendView('panel', 1, DEFAULTS)).toEqual(PINNED);
  });

  it('keeps one framing per loop', () => {
    writeTrendView('panel', 1, PINNED);
    writeTrendView('panel', 2, { ...DEFAULTS, count: 7 });
    expect(readTrendView('panel', 1, DEFAULTS)).toEqual(PINNED);
    expect(readTrendView('panel', 2, DEFAULTS).count).toBe(7);
    // A loop that was never framed still gets the defaults.
    expect(readTrendView('panel', 3, DEFAULTS)).toEqual(DEFAULTS);
  });

  it('keeps the twin and panel framings of the same loop apart', () => {
    writeTrendView('panel', 1, PINNED);
    writeTrendView('twin', 1, { ...DEFAULTS, count: 2, unit: 'hora' });
    expect(readTrendView('panel', 1, DEFAULTS)).toEqual(PINNED);
    expect(readTrendView('twin', 1, DEFAULTS).unit).toBe('hora');
  });

  it('writes under the spid.trendview key and nothing else', () => {
    writeTrendView('panel', 1, PINNED);
    expect(Object.keys(localStorage)).toEqual([TREND_VIEW_KEY]);
    expect(TREND_VIEW_KEY).toBe('spid.trendview');
  });

  it('discards unparseable storage', () => {
    localStorage.setItem(TREND_VIEW_KEY, 'not json {');
    expect(readTrendView('panel', 1, DEFAULTS)).toEqual(DEFAULTS);
  });

  it('discards an entry with a wrong field type without losing its siblings', () => {
    writeTrendView('panel', 2, PINNED);
    const stored: Record<string, unknown> = JSON.parse(
      localStorage.getItem(TREND_VIEW_KEY) as string,
    );
    stored['panel:1'] = { ...PINNED, count: '5' };
    localStorage.setItem(TREND_VIEW_KEY, JSON.stringify(stored));
    expect(readTrendView('panel', 1, DEFAULTS)).toEqual(DEFAULTS);
    expect(readTrendView('panel', 2, DEFAULTS)).toEqual(PINNED);
  });

  it('discards an unknown window unit', () => {
    localStorage.setItem(
      TREND_VIEW_KEY,
      JSON.stringify({ 'panel:1': { ...PINNED, unit: 'semana' } }),
    );
    expect(readTrendView('panel', 1, DEFAULTS)).toEqual(DEFAULTS);
  });

  it('discards a non-finite bound', () => {
    // JSON has no Infinity — it serialises to null, which must not read back.
    localStorage.setItem(
      TREND_VIEW_KEY,
      JSON.stringify({ 'panel:1': { ...PINNED, pvMax: Number.POSITIVE_INFINITY } }),
    );
    expect(readTrendView('panel', 1, DEFAULTS)).toEqual(DEFAULTS);
  });

  it('degrades to session-only when the write throws', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('QuotaExceededError');
    });
    expect(() => writeTrendView('panel', 1, PINNED)).not.toThrow();
  });

  it('degrades to defaults when the read throws', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new DOMException('SecurityError');
    });
    expect(readTrendView('panel', 1, DEFAULTS)).toEqual(DEFAULTS);
  });
});
