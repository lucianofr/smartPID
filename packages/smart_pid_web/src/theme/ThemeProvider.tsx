import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';

export type ThemeId = 'isa101' | 'dark-room' | 'md3-dark' | 'md3-light' | 'ocean';

export const THEMES: ReadonlyArray<{ id: ThemeId; label: string }> = [
  { id: 'isa101', label: 'ISA-101' },
  { id: 'dark-room', label: 'Dark Room' },
  { id: 'md3-dark', label: 'Material 3 Dark' },
  { id: 'md3-light', label: 'Material 3 Light' },
  { id: 'ocean', label: 'Ocean' },
];

const STORAGE_KEY = 'spid.theme';
const DEFAULT_THEME: ThemeId = 'isa101';

function readStored(): ThemeId {
  const v = localStorage.getItem(STORAGE_KEY);
  return THEMES.some((t) => t.id === v) ? (v as ThemeId) : DEFAULT_THEME;
}

interface ThemeCtx {
  theme: ThemeId;
  setTheme: (t: ThemeId) => void;
  themes: typeof THEMES;
}
const Ctx = createContext<ThemeCtx | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ThemeId>(readStored);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  const setTheme = (t: ThemeId) => {
    setThemeState(t);
    localStorage.setItem(STORAGE_KEY, t);
  };

  return <Ctx.Provider value={{ theme, setTheme, themes: THEMES }}>{children}</Ctx.Provider>;
}

export function useTheme(): ThemeCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider');
  return ctx;
}
