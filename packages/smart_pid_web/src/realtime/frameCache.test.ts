import { describe, expect, it } from 'vitest';
import type { AnyEnvelope, RealtimeType } from '../lib/envelope';
import { createFrameCache, frameKey, type FrameCache } from './frameCache';

const env = (type: RealtimeType, loopId: number | null, seq: number): AnyEnvelope =>
  ({ type, loop_id: loopId, seq, ts: seq, data: { seq } }) as unknown as AnyEnvelope;

function replayed(cache: FrameCache, type: RealtimeType): AnyEnvelope[] {
  const out: AnyEnvelope[] = [];
  cache.replay(type, (e) => out.push(e));
  return out;
}

describe('frameKey', () => {
  it('scopes a slot to (type, loop_id)', () => {
    expect(frameKey(env('status', 5, 1))).toBe('status:5');
    expect(frameKey(env('stats', 5, 1))).not.toBe(frameKey(env('status', 5, 1)));
  });

  it('never collides a broadcast (loop_id null) with a numeric loop', () => {
    expect(frameKey(env('system', null, 1))).not.toBe(frameKey(env('system', 0, 1)));
  });
});

describe('createFrameCache', () => {
  it('replays nothing when empty', () => {
    expect(replayed(createFrameCache(), 'status')).toEqual([]);
  });

  it('keeps exactly one slot per key — the newest frame wins', () => {
    const cache = createFrameCache();
    cache.put(env('status', 5, 1));
    cache.put(env('status', 5, 2));
    cache.put(env('status', 5, 3));
    const out = replayed(cache, 'status');
    expect(out).toHaveLength(1);
    expect(out[0].seq).toBe(3);
  });

  it('replays only the requested type', () => {
    const cache = createFrameCache();
    cache.put(env('status', 5, 1));
    cache.put(env('stats', 5, 2));
    expect(replayed(cache, 'status').map((e) => e.seq)).toEqual([1]);
    expect(replayed(cache, 'stats').map((e) => e.seq)).toEqual([2]);
  });

  it('replays every loop of a type, oldest-observed first so the newest lands last', () => {
    const cache = createFrameCache();
    cache.put(env('status', 5, 1));
    cache.put(env('status', 9, 2));
    cache.put(env('status', 5, 3)); // loop 5 refreshed → moves to the end
    expect(replayed(cache, 'status').map((e) => e.loop_id)).toEqual([9, 5]);
  });

  it('ignores a seq regression — an older frame never resurrects over a newer one', () => {
    const cache = createFrameCache();
    cache.put(env('status', 5, 7));
    cache.put(env('status', 5, 3));
    expect(replayed(cache, 'status')[0].seq).toBe(7);
  });

  it('accepts any seq after clear() — a new baseline is not a regression', () => {
    const cache = createFrameCache();
    cache.put(env('status', 5, 7));
    cache.clear();
    expect(replayed(cache, 'status')).toEqual([]);
    cache.put(env('status', 5, 1)); // daemon restarted: seq counter restarted too
    expect(replayed(cache, 'status')[0].seq).toBe(1);
  });
});
