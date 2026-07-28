import { freeSlot, MAX_SLOTS, SIGNALS, type TrendSlot } from './types';

/**
 * Trend-selection persistence (§9.1).
 *
 * Deliberately NOT a `useSyncExternalStore` store: `useSettings` uses that
 * pattern because preferences have many readers, and the trend selection has
 * exactly one. Two pure functions are the whole surface.
 *
 * Its own key, not folded into `AppPreferences`: that is a user-facing form
 * with a "Restaurar padrões" button, and a preference reset must not wipe a
 * trend layout.
 */

export const TREND_SELECTION_KEY = 'spid.multitrend';

function fourFreeSlots(): TrendSlot[] {
  return Array.from({ length: MAX_SLOTS }, freeSlot);
}

/** Anything not exactly four well-formed slots is discarded, never patched. */
function isTrendSlot(value: unknown): value is TrendSlot {
  if (typeof value !== 'object' || value === null) return false;
  const slot = value as { controllerId?: unknown; series?: unknown };
  if (slot.controllerId !== null && typeof slot.controllerId !== 'number') return false;
  if (typeof slot.series !== 'object' || slot.series === null) return false;
  const series = slot.series as Record<string, unknown>;
  return SIGNALS.every((signal) => typeof series[signal] === 'boolean');
}

export function readTrendSelection(): TrendSlot[] {
  try {
    const raw = localStorage.getItem(TREND_SELECTION_KEY);
    if (raw === null) return fourFreeSlots();
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed) || parsed.length !== MAX_SLOTS) return fourFreeSlots();
    if (!parsed.every(isTrendSlot)) return fourFreeSlots();
    return parsed.map(({ controllerId, series }) => ({
      controllerId,
      series: { pv: series.pv, sp: series.sp, co: series.co },
    }));
  } catch {
    // Corrupt, blocked or unreadable storage must never take the page down.
    return fourFreeSlots();
  }
}

export function writeTrendSelection(slots: readonly TrendSlot[]): void {
  try {
    localStorage.setItem(TREND_SELECTION_KEY, JSON.stringify(slots));
  } catch {
    // Quota or private mode: degrade to session-only, surface nothing.
  }
}
