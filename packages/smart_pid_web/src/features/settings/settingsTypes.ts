export interface AppPreferences {
  trendWindowSeconds: number;
  numberDecimals: number;
  confirmDestructive: boolean;
}

export const DEFAULT_PREFERENCES: AppPreferences = {
  trendWindowSeconds: 120,
  numberDecimals: 2,
  confirmDestructive: true,
};

export const PREFERENCES_KEY = 'spid.preferences';
