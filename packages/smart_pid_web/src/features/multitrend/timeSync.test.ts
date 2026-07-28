import { describe, expect, it, vi, type Mock } from 'vitest';
import { createTimeSync, type SyncChart, type XRange } from './timeSync';

function chart(id: string): SyncChart & { setX: Mock } {
  return { id, setX: vi.fn() };
}

describe('createTimeSync', () => {
  it('never echoes a range back to its source', () => {
    const sync = createTimeSync();
    const a = chart('a');
    const b = chart('b');
    sync.register(a);
    sync.register(b);

    sync.publish('a', { min: 10, max: 20 });

    expect(a.setX).not.toHaveBeenCalled();
    expect(b.setX).toHaveBeenCalledOnce();
    expect(b.setX).toHaveBeenCalledWith({ min: 10, max: 20 });
  });

  it('suppresses the re-entrant publish a sibling setX triggers', () => {
    const sync = createTimeSync();
    const a = chart('a');
    // uPlot fires setScale for a PROGRAMMATIC setScale too, so the sibling
    // immediately publishes back. Without the guard that is an infinite loop.
    const b: SyncChart = {
      id: 'b',
      setX: vi.fn((range: XRange) => sync.publish('b', range)),
    };
    sync.register(a);
    sync.register(b);

    sync.publish('a', { min: 0, max: 5 });

    expect(b.setX).toHaveBeenCalledOnce();
    expect(a.setX).not.toHaveBeenCalled();
  });

  it('fans out to every chart when the source is not registered', () => {
    const sync = createTimeSync();
    const a = chart('a');
    const b = chart('b');
    sync.register(a);
    sync.register(b);

    sync.publish('history', { min: 1, max: 2 });

    expect(a.setX).toHaveBeenCalledOnce();
    expect(b.setX).toHaveBeenCalledOnce();
  });

  it('stops delivering to an unregistered chart', () => {
    const sync = createTimeSync();
    const a = chart('a');
    const b = chart('b');
    sync.register(a);
    const off = sync.register(b);

    off();
    sync.publish('a', { min: 3, max: 4 });

    expect(b.setX).not.toHaveBeenCalled();
  });

  it('replaces a chart re-registered under the same id', () => {
    const sync = createTimeSync();
    const first = chart('slot-0');
    const second = chart('slot-0');
    const other = chart('slot-1');
    sync.register(first);
    sync.register(second);
    sync.register(other);

    sync.publish('slot-1', { min: 7, max: 9 });

    expect(first.setX).not.toHaveBeenCalled();
    expect(second.setX).toHaveBeenCalledOnce();
  });
});
