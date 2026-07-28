import type { ReactNode } from 'react';
import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import { statusEnvelope } from '@/test/fixtures';
import { createFakeRealtime, TestProviders } from '@/test/providers';
import { freeSlot, MAX_SLOTS } from './types';
import { TREND_SELECTION_KEY } from './trendSelectionStore';
import { useMultiTrendModel } from './useMultiTrendModel';

const controllerA = { id: 1 };
const controllerB = { id: 2 };

/** `null` roster = the stats query has not resolved; nothing is reconciled. */
function setup(roster: readonly number[] | null = null) {
  const realtime = createFakeRealtime();
  const wrapper = ({ children }: { children: ReactNode }) => (
    <TestProviders realtime={realtime.value}>{children}</TestProviders>
  );
  return { realtime, ...renderHook(() => useMultiTrendModel(roster), { wrapper }) };
}

beforeEach(() => {
  localStorage.clear();
});

describe('useMultiTrendModel slot invariants', () => {
  it('assigns a controller with every signal on, then toggles one off', () => {
    const { result } = setup();
    act(() => result.current.assign(0, controllerA));
    act(() => result.current.toggleSeries(0, 'co'));
    expect(result.current.slots[0]).toMatchObject({
      controllerId: 1,
      series: { pv: true, sp: true, co: false },
    });
  });

  it('rejects a slot index outside the four-slot grid', () => {
    const { result } = setup();
    expect(() => result.current.assign(MAX_SLOTS, controllerA)).toThrow(
      'slot must be between 0 and 3',
    );
    expect(() => result.current.assign(-1, controllerA)).toThrow('slot must be between 0 and 3');
    expect(() => result.current.toggleSeries(4, 'pv')).toThrow('slot must be between 0 and 3');
  });

  it('starts with four free slots and releases one on clear', () => {
    const { result } = setup();
    expect(result.current.slots).toHaveLength(MAX_SLOTS);
    expect(result.current.slots.every((s) => s.controllerId === null)).toBe(true);
    act(() => result.current.assign(2, controllerB));
    expect(result.current.slots[2].controllerId).toBe(2);
    act(() => result.current.clear(2));
    expect(result.current.slots[2].controllerId).toBeNull();
  });

  it('never plots more than four controllers', () => {
    const { result } = setup();
    for (let id = 1; id <= MAX_SLOTS; id += 1) act(() => result.current.toggleSignal(id, 'pv'));
    expect(result.current.isFull).toBe(true);
    act(() => result.current.toggleSignal(9, 'pv'));
    expect(result.current.isSelected(9, 'pv')).toBe(false);
    expect(result.current.slots.map((s) => s.controllerId)).toEqual([1, 2, 3, 4]);
  });
});

describe('useMultiTrendModel flat signal toggling', () => {
  it('occupies the first free slot with only the toggled signal', () => {
    const { result } = setup();
    act(() => result.current.toggleSignal(7, 'co'));
    expect(result.current.slots[0]).toMatchObject({
      controllerId: 7,
      series: { pv: false, sp: false, co: true },
    });
    expect(result.current.isSelected(7, 'co')).toBe(true);
    expect(result.current.selection).toEqual([{ loopId: 7, signal: 'co' }]);
  });

  it('frees the slot once the loop has no signal left', () => {
    const { result } = setup();
    act(() => result.current.toggleSignal(7, 'co'));
    act(() => result.current.toggleSignal(7, 'co'));
    expect(result.current.slots[0].controllerId).toBeNull();
    expect(result.current.selection).toEqual([]);
  });

  it('orders selection by slot, then pv/sp/co', () => {
    const { result } = setup();
    act(() => result.current.toggleSignal(2, 'co'));
    act(() => result.current.toggleSignal(2, 'pv'));
    act(() => result.current.toggleSignal(5, 'sp'));
    expect(result.current.selection).toEqual([
      { loopId: 2, signal: 'pv' },
      { loopId: 2, signal: 'co' },
      { loopId: 5, signal: 'sp' },
    ]);
  });
});

describe('useMultiTrendModel live buffers', () => {
  it('buffers frames only for occupied slots', () => {
    const { realtime, result } = setup();
    act(() => result.current.toggleSignal(1, 'pv'));
    act(() => {
      realtime.emit(statusEnvelope(1, 1, { timestamp: 1000, pv: { value: 10, severity: 'GOOD', limit_bits: 'NONE', sub_status: 'NON_SPECIFIC' } }));
      realtime.emit(statusEnvelope(1, 2, { timestamp: 1001, pv: { value: 11, severity: 'GOOD', limit_bits: 'NONE', sub_status: 'NON_SPECIFIC' } }));
      realtime.emit(statusEnvelope(3, 3, { timestamp: 1002 }));
    });
    const [slot0] = result.current.slotSeries;
    expect(slot0.keys).toEqual([{ loopId: 1, signal: 'pv' }]);
    expect(slot0.data[0]).toEqual([1000, 1001]);
    expect(slot0.data[1]).toEqual([10, 11]);
    // Loop 3 was never assigned, so it has no slot and no buffer.
    expect(result.current.slotSeries[1].keys).toEqual([]);
  });

  it('de-dupes a coalesced frame that repeats the last timestamp', () => {
    const { realtime, result } = setup();
    act(() => result.current.toggleSignal(1, 'pv'));
    act(() => {
      realtime.emit(statusEnvelope(1, 1, { timestamp: 1000 }));
      realtime.emit(statusEnvelope(1, 2, { timestamp: 1000 }));
    });
    expect(result.current.slotSeries[0].data[0]).toEqual([1000]);
  });

  it('stops accumulating while paused', () => {
    const { realtime, result } = setup();
    act(() => result.current.toggleSignal(1, 'pv'));
    act(() => realtime.emit(statusEnvelope(1, 1, { timestamp: 1000 })));
    act(() => result.current.setPaused(true));
    act(() => realtime.emit(statusEnvelope(1, 2, { timestamp: 1001 })));
    expect(result.current.slotSeries[0].data[0]).toEqual([1000]);
    act(() => result.current.setPaused(false));
    act(() => realtime.emit(statusEnvelope(1, 3, { timestamp: 1002 })));
    expect(result.current.slotSeries[0].data[0]).toEqual([1000, 1002]);
  });

  it('drops a loop buffer when its slot is released', () => {
    const { realtime, result } = setup();
    act(() => result.current.toggleSignal(1, 'pv'));
    act(() => realtime.emit(statusEnvelope(1, 1, { timestamp: 1000 })));
    act(() => result.current.toggleSignal(1, 'pv'));
    act(() => result.current.toggleSignal(1, 'pv'));
    expect(result.current.slotSeries[0].data[0]).toEqual([]);
  });
});

describe('useMultiTrendModel persistence and reconciliation', () => {
  it('restores a stored layout on mount', () => {
    localStorage.setItem(
      TREND_SELECTION_KEY,
      JSON.stringify([
        { controllerId: 3, series: { pv: true, sp: false, co: true } },
        freeSlot(),
        freeSlot(),
        freeSlot(),
      ]),
    );
    const { result } = setup();
    expect(result.current.slots[0]).toEqual({
      controllerId: 3,
      series: { pv: true, sp: false, co: true },
    });
    expect(result.current.isSelected(3, 'co')).toBe(true);
  });

  it('persists every selection change', () => {
    const { result } = setup();
    act(() => result.current.assign(1, controllerB));
    const stored = JSON.parse(localStorage.getItem(TREND_SELECTION_KEY) ?? 'null') as unknown[];
    expect(stored).toHaveLength(MAX_SLOTS);
    expect(stored[1]).toEqual({ controllerId: 2, series: { pv: true, sp: true, co: true } });
  });

  it('releases a restored slot whose loop is absent from the roster', () => {
    localStorage.setItem(
      TREND_SELECTION_KEY,
      JSON.stringify([
        { controllerId: 3, series: { pv: true, sp: true, co: true } },
        { controllerId: 1, series: { pv: true, sp: false, co: false } },
        freeSlot(),
        freeSlot(),
      ]),
    );
    const { result } = setup([1, 2]);
    expect(result.current.slots[0]).toEqual(freeSlot());
    expect(result.current.slots[1].controllerId).toBe(1);
  });

  it('releases a restored slot that has no signal enabled', () => {
    localStorage.setItem(
      TREND_SELECTION_KEY,
      JSON.stringify([
        { controllerId: 1, series: { pv: false, sp: false, co: false } },
        freeSlot(),
        freeSlot(),
        freeSlot(),
      ]),
    );
    const { result } = setup([1]);
    expect(result.current.slots[0]).toEqual(freeSlot());
  });

  it('reconciles nothing while the roster is still null', () => {
    localStorage.setItem(
      TREND_SELECTION_KEY,
      JSON.stringify([
        { controllerId: 99, series: { pv: true, sp: true, co: true } },
        freeSlot(),
        freeSlot(),
        freeSlot(),
      ]),
    );
    const { result } = setup(null);
    expect(result.current.slots[0].controllerId).toBe(99);
  });

  it('ignores malformed storage and starts from four free slots', () => {
    localStorage.setItem(TREND_SELECTION_KEY, '{"nope":true}');
    const { result } = setup();
    expect(result.current.slots).toEqual([freeSlot(), freeSlot(), freeSlot(), freeSlot()]);
  });

  it('never restores paused', () => {
    localStorage.setItem(
      TREND_SELECTION_KEY,
      JSON.stringify([
        { controllerId: 1, series: { pv: true, sp: true, co: true } },
        freeSlot(),
        freeSlot(),
        freeSlot(),
      ]),
    );
    const { result } = setup([1]);
    expect(result.current.paused).toBe(false);
  });
});
