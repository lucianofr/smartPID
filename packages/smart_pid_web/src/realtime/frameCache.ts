import type { AnyEnvelope, RealtimeType } from '../lib/envelope';

/**
 * Last-frame cache — pure module, no React, no DOM (spec §7).
 *
 * One slot per (type, loop_id): the same granularity the backend's
 * ConnectionBuffer coalesces on (realtime.py ConnectionBuffer). A component
 * that mounts after a frame has already arrived would otherwise render empty
 * until the next one — seconds of blank faceplate on a slow loop.
 */

/** Cache/coalesce slot key. `loop_id` is null for broadcasts (EVENT.SYSTEM). */
export function frameKey(env: Pick<AnyEnvelope, 'type' | 'loop_id'>): string {
  return `${env.type}:${env.loop_id ?? 'null'}`;
}

export interface FrameCache {
  /**
   * Record `env` as the last frame for its key. A seq regression is ignored: an
   * out-of-order older frame must never resurrect over a newer one. A genuine
   * regression (daemon restart) arrives with `gap` set, which drives a §7
   * resync — and that clears the cache first, so the new baseline is accepted.
   */
  put(env: AnyEnvelope): void;
  /** Replay every cached frame of one type, oldest-observed first so the most
   *  recent one lands last (a subscriber keeping only `last` ends up correct). */
  replay(type: RealtimeType, handler: (env: AnyEnvelope) => void): void;
  /** Drop every slot — §7 resync makes REST the truth again; pre-resync frames
   *  are stale by definition and must never reach a late subscriber. */
  clear(): void;
}

export function createFrameCache(): FrameCache {
  const frames = new Map<string, AnyEnvelope>();
  return {
    put(env) {
      const key = frameKey(env);
      const prev = frames.get(key);
      if (prev !== undefined && env.seq < prev.seq) return;
      // Re-insert so Map iteration order stays recency order — no sort on replay.
      frames.delete(key);
      frames.set(key, env);
    },
    replay(type, handler) {
      for (const env of frames.values()) {
        if (env.type === type) handler(env);
      }
    },
    clear() {
      frames.clear();
    },
  };
}
