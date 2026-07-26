import { describe, expect, it } from 'vitest';
import { ff, makeStatus } from '@/test/fixtures';
import { toTwinPoint, TWIN_WINDOW_SECONDS } from './twinTrend';

describe('toTwinPoint', () => {
  it('reads FFSignal values and an ISO timestamp onto the recorder time base', () => {
    const frame = makeStatus({
      pv: ff(50),
      sp: ff(55),
      co: ff(40),
      timestamp: '2026-06-19T00:00:01.000Z',
    });
    expect(toTwinPoint(frame)).toEqual({
      x: Date.parse('2026-06-19T00:00:01.000Z') / 1000,
      pv: 50,
      sp: 55,
      co: 40,
    });
  });

  it('passes a monitor-mode float timestamp through unchanged', () => {
    expect(toTwinPoint(makeStatus({ timestamp: 1_750_000_000.5 }))?.x).toBe(1_750_000_000.5);
  });

  it('drops a frame whose timestamp cannot be placed on the axis', () => {
    expect(toTwinPoint(makeStatus({ timestamp: 'not-a-time' }))).toBeNull();
    expect(toTwinPoint(makeStatus({ timestamp: Number.NaN }))).toBeNull();
  });

  it('keeps a window long enough to watch a slow step settle', () => {
    expect(TWIN_WINDOW_SECONDS).toBeGreaterThanOrEqual(120);
  });
});
