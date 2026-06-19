import { useCallback, useState } from 'react';
import { type AppPreferences, DEFAULT_PREFERENCES, PREFERENCES_KEY } from './settingsTypes';

function load(): AppPreferences {
  try {
    const raw = localStorage.getItem(PREFERENCES_KEY);
    if (!raw) return DEFAULT_PREFERENCES;
    return { ...DEFAULT_PREFERENCES, ...(JSON.parse(raw) as Partial<AppPreferences>) };
  } catch {
    return DEFAULT_PREFERENCES;
  }
}

export function useSettings() {
  const [preferences, setPreferences] = useState<AppPreferences>(load);

  const setPreference = useCallback(
    <K extends keyof AppPreferences>(key: K, value: AppPreferences[K]) => {
      setPreferences((prev) => {
        const next = { ...prev, [key]: value };
        localStorage.setItem(PREFERENCES_KEY, JSON.stringify(next));
        return next;
      });
    },
    [],
  );

  const reset = useCallback(() => {
    localStorage.removeItem(PREFERENCES_KEY);
    setPreferences(DEFAULT_PREFERENCES);
  }, []);

  return { preferences, setPreference, reset };
}

export { DEFAULT_PREFERENCES };
