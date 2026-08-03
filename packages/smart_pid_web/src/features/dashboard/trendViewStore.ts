/**
 * Trend view persistence (§9.1).
 *
 * A trend chart's VIEW — time window, autoscale, and the pinned Y bounds — is a
 * per-loop working setup: an engineer who framed FIC-101 on a 5-minute window
 * with PV pinned to 40–60 % expects that framing back after a navigation, a
 * reload, or a browser restart, and expects the NEXT loop to keep its own.
 *
 * Same two-pure-function surface and same failure posture as
 * `trendSelectionStore`: anything malformed is discarded rather than patched,
 * and unreadable/unwritable storage degrades to session-only instead of taking
 * the page down. Kept out of `AppPreferences` on purpose — that form has a
 * "Restaurar padrões" button, and resetting preferences must not wipe every
 * loop's chart framing.
 */

export const TREND_VIEW_KEY = 'spid.trendview';

/** Which chart the config belongs to; one namespace per surface, per loop. */
export type TrendViewScope = 'panel' | 'twin';

export type TrendViewUnit = 'segundo' | 'minuto' | 'hora';

const UNITS: readonly TrendViewUnit[] = ['segundo', 'minuto', 'hora'];

export interface TrendViewConfig {
  /** Window length in `unit`s. */
  count: number;
  unit: TrendViewUnit;
  autoScale: boolean;
  pvMin: number;
  pvMax: number;
  coMin: number;
  coMax: number;
}

type TrendViewMap = Record<string, TrendViewConfig>;

function isFiniteNumber(v: unknown): v is number {
  return typeof v === 'number' && Number.isFinite(v);
}

/** A partially-valid entry is not a config — the caller's defaults win instead. */
function isTrendViewConfig(value: unknown): value is TrendViewConfig {
  if (typeof value !== 'object' || value === null) return false;
  const c = value as Record<string, unknown>;
  return (
    isFiniteNumber(c.count) &&
    c.count >= 1 &&
    typeof c.unit === 'string' &&
    (UNITS as readonly string[]).includes(c.unit) &&
    typeof c.autoScale === 'boolean' &&
    isFiniteNumber(c.pvMin) &&
    isFiniteNumber(c.pvMax) &&
    isFiniteNumber(c.coMin) &&
    isFiniteNumber(c.coMax)
  );
}

function readMap(): TrendViewMap {
  try {
    const raw = localStorage.getItem(TREND_VIEW_KEY);
    if (raw === null) return {};
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) return {};
    const out: TrendViewMap = {};
    for (const [key, value] of Object.entries(parsed as Record<string, unknown>)) {
      if (isTrendViewConfig(value)) out[key] = value;
    }
    return out;
  } catch {
    // Corrupt, blocked or unreadable storage must never take the page down.
    return {};
  }
}

/** Stored view for one (scope, loop), or `defaults` when there is none. */
export function readTrendView(
  scope: TrendViewScope,
  loopId: number,
  defaults: TrendViewConfig,
): TrendViewConfig {
  return readMap()[`${scope}:${loopId}`] ?? defaults;
}

export function writeTrendView(
  scope: TrendViewScope,
  loopId: number,
  config: TrendViewConfig,
): void {
  try {
    // Read-modify-write: every loop's framing shares one key, and saving FIC-101
    // must not drop FIC-102's.
    const map = readMap();
    map[`${scope}:${loopId}`] = config;
    localStorage.setItem(TREND_VIEW_KEY, JSON.stringify(map));
  } catch {
    // Quota or private mode: degrade to session-only, surface nothing.
  }
}
