/**
 * Client-side application preferences.
 *
 * These are NOT backend settings: the API exposes no `/settings` route (65
 * paths, phase-2 codegen), so the pre-rewrite model is kept — a small,
 * versionless preference set persisted in `localStorage` and read by whichever
 * surface needs it (`confirmDestructive` gates the destructive confirms,
 * `numberDecimals`/`trendWindowSeconds` are display defaults).
 */
export interface AppPreferences {
  /** Default trend window, in seconds. */
  trendWindowSeconds: number;
  /** Decimal places for engineering-unit readouts. */
  numberDecimals: number;
  /** Ask before a destructive action (project delete, user deactivation). */
  confirmDestructive: boolean;
}

export const DEFAULT_PREFERENCES: AppPreferences = {
  trendWindowSeconds: 120,
  numberDecimals: 2,
  confirmDestructive: true,
};

/** Kept verbatim from the pre-rewrite tree — existing installs keep their prefs. */
export const PREFERENCES_KEY = 'spid.preferences';

export const DECIMALS_MIN = 0;
export const DECIMALS_MAX = 6;
export const TREND_WINDOW_MIN_S = 10;
export const TREND_WINDOW_MAX_S = 3600;
