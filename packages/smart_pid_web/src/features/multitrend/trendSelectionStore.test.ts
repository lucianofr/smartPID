import { beforeEach, describe, expect, it, vi } from 'vitest';
import { freeSlot, MAX_SLOTS, type TrendSlot } from './types';
import {
  readTrendSelection,
  TREND_SELECTION_KEY,
  writeTrendSelection,
} from './trendSelectionStore';

const occupied = (controllerId: number): TrendSlot => ({
  controllerId,
  series: { pv: true, sp: false, co: true },
});

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

describe('trendSelectionStore', () => {
  it('falls back to four free slots when nothing is stored', () => {
    expect(readTrendSelection()).toEqual([freeSlot(), freeSlot(), freeSlot(), freeSlot()]);
  });

  it('round-trips a written layout', () => {
    const slots = [occupied(3), freeSlot(), occupied(7), freeSlot()];
    writeTrendSelection(slots);
    expect(readTrendSelection()).toEqual(slots);
  });

  it('writes under the spid.multitrend key and nothing else', () => {
    writeTrendSelection([occupied(1), freeSlot(), freeSlot(), freeSlot()]);
    expect(Object.keys(localStorage)).toEqual([TREND_SELECTION_KEY]);
    expect(TREND_SELECTION_KEY).toBe('spid.multitrend');
  });

  it('discards unparseable storage wholesale', () => {
    localStorage.setItem(TREND_SELECTION_KEY, 'not json {');
    expect(readTrendSelection()).toEqual([freeSlot(), freeSlot(), freeSlot(), freeSlot()]);
  });

  it('discards a payload that is not exactly four slots', () => {
    localStorage.setItem(TREND_SELECTION_KEY, JSON.stringify([occupied(1), occupied(2)]));
    expect(readTrendSelection()).toEqual([freeSlot(), freeSlot(), freeSlot(), freeSlot()]);
    expect(readTrendSelection()).toHaveLength(MAX_SLOTS);
  });

  it('discards a payload whose slot shape is wrong', () => {
    localStorage.setItem(
      TREND_SELECTION_KEY,
      JSON.stringify([
        { controllerId: '3', series: { pv: true, sp: true, co: true } },
        freeSlot(),
        freeSlot(),
        freeSlot(),
      ]),
    );
    expect(readTrendSelection()).toEqual([freeSlot(), freeSlot(), freeSlot(), freeSlot()]);
  });

  it('discards a payload with a missing signal flag', () => {
    localStorage.setItem(
      TREND_SELECTION_KEY,
      JSON.stringify([
        { controllerId: 3, series: { pv: true, sp: true } },
        freeSlot(),
        freeSlot(),
        freeSlot(),
      ]),
    );
    expect(readTrendSelection()).toEqual([freeSlot(), freeSlot(), freeSlot(), freeSlot()]);
  });

  it('degrades to session-only when the write throws', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('QuotaExceededError');
    });
    expect(() => writeTrendSelection([occupied(1), freeSlot(), freeSlot(), freeSlot()])).not.toThrow();
  });

  it('degrades to four free slots when the read throws', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new DOMException('SecurityError');
    });
    expect(readTrendSelection()).toEqual([freeSlot(), freeSlot(), freeSlot(), freeSlot()]);
  });
});
