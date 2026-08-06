import { describe, expect, it, vi } from 'vitest';
import { createTimeSync } from '@/features/multitrend/timeSync';

describe('createTimeSync', () => {
  it('broadcasts to every chart except the source', () => {
    const sync = createTimeSync();
    const a = { id: 'a', setX: vi.fn() };
    const b = { id: 'b', setX: vi.fn() };
    const c = { id: 'c', setX: vi.fn() };
    sync.register(a);
    sync.register(b);
    sync.register(c);
    sync.publish('a', { min: 1, max: 2 });
    expect(a.setX).not.toHaveBeenCalled();
    expect(b.setX).toHaveBeenCalledWith({ min: 1, max: 2 });
    expect(c.setX).toHaveBeenCalledWith({ min: 1, max: 2 });
  });

  it('does not echo a range published while broadcasting (re-entrancy guard)', () => {
    const sync = createTimeSync();
    const a = { id: 'a', setX: vi.fn() };
    const b = {
      id: 'b',
      setX: vi.fn(() => sync.publish('b', { min: 9, max: 10 })),
    };
    sync.register(a);
    sync.register(b);
    sync.publish('a', { min: 1, max: 2 });
    expect(b.setX).toHaveBeenCalledTimes(1); // re-entrant publish is suppressed
    expect(a.setX).not.toHaveBeenCalled(); // source never receives its own range
  });

  it('unregisters on the returned handle, without evicting a remounted replacement', () => {
    const sync = createTimeSync();
    const a1 = { id: 'a', setX: vi.fn() };
    const a2 = { id: 'a', setX: vi.fn() };
    const off = sync.register(a1);
    sync.register(a2);
    off(); // stale teardown must not drop the new chart
    sync.publish('b', { min: 0, max: 1 });
    expect(a2.setX).toHaveBeenCalledTimes(1);
    expect(a1.setX).not.toHaveBeenCalled();
  });
});
