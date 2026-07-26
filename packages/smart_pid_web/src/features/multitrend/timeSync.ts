/**
 * Shared x-range broadcaster for the 2×2 trend grid (§6.8) — pure module.
 *
 * uPlot fires `setScale` for PROGRAMMATIC scale changes too, so the naive
 * "on pan, tell my siblings" wiring echoes forever: A moves → B.setScale →
 * B publishes → A.setScale → … A single re-entrancy flag breaks it, and the
 * source never receives its own range back.
 */

export interface XRange {
  min: number;
  max: number;
}

export interface SyncChart {
  id: string;
  setX(range: XRange): void;
}

export interface TimeSync {
  /** Returns the unregister handle — call it on chart teardown. */
  register(chart: SyncChart): () => void;
  publish(sourceId: string, range: XRange): void;
}

export function createTimeSync(): TimeSync {
  const charts = new Map<string, SyncChart>();
  let broadcasting = false;

  return {
    register(chart) {
      charts.set(chart.id, chart);
      return () => {
        // Only drop the entry still owned by this chart: a remount registers
        // the replacement first, and its teardown must not evict the new one.
        if (charts.get(chart.id) === chart) charts.delete(chart.id);
      };
    },

    publish(sourceId, range) {
      if (broadcasting) return;
      broadcasting = true;
      try {
        for (const chart of charts.values()) {
          if (chart.id !== sourceId) chart.setX(range);
        }
      } finally {
        broadcasting = false;
      }
    },
  };
}
