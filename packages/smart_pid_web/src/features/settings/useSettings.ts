import { useSyncExternalStore } from 'react';
import { type AppPreferences, DEFAULT_PREFERENCES, PREFERENCES_KEY } from './settingsTypes';

/**
 * One process-wide preference store. The pre-rewrite hook kept per-component
 * `useState`, so a change on the settings page stayed invisible to an already
 * mounted consumer until a reload; a module-level snapshot plus
 * `useSyncExternalStore` removes that staleness without adding a provider.
 */

function load(): AppPreferences {
  try {
    const raw = localStorage.getItem(PREFERENCES_KEY);
    if (raw === null) return DEFAULT_PREFERENCES;
    return { ...DEFAULT_PREFERENCES, ...(JSON.parse(raw) as Partial<AppPreferences>) };
  } catch {
    // Corrupt or unreadable storage must never take the app down.
    return DEFAULT_PREFERENCES;
  }
}

let snapshot: AppPreferences = load();
const listeners = new Set<() => void>();

function emit(): void {
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** Imperative read for non-React callers and one-shot checks inside handlers. */
export function readPreferences(): AppPreferences {
  return snapshot;
}

export function savePreferences(next: AppPreferences): void {
  snapshot = next;
  try {
    localStorage.setItem(PREFERENCES_KEY, JSON.stringify(next));
  } catch {
    // A quota/private-mode failure degrades to session-only preferences.
  }
  emit();
}

export function resetPreferences(): void {
  snapshot = DEFAULT_PREFERENCES;
  try {
    localStorage.removeItem(PREFERENCES_KEY);
  } catch {
    /* see savePreferences */
  }
  emit();
}

/** Re-read storage — tests and a fresh session start from a clean snapshot. */
export function reloadPreferences(): void {
  snapshot = load();
  emit();
}

export function usePreferences(): AppPreferences {
  return useSyncExternalStore(subscribe, readPreferences, readPreferences);
}

export interface SettingsController {
  preferences: AppPreferences;
  save(next: AppPreferences): void;
  reset(): void;
}

export function useSettings(): SettingsController {
  return { preferences: usePreferences(), save: savePreferences, reset: resetPreferences };
}
