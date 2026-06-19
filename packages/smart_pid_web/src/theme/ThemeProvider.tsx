import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';

export type ThemeName = 'isa101' | 'dark-room';
const STORAGE_KEY = 'smart-pid-theme';

interface ThemeCtx {
  theme: ThemeName;
  setTheme: (t: ThemeName) => void;
}
const Ctx = createContext<ThemeCtx | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<ThemeName>(
    () => (localStorage.getItem(STORAGE_KEY) as ThemeName) ?? 'isa101',
  );
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);
  return <Ctx.Provider value={{ theme, setTheme }}>{children}</Ctx.Provider>;
}

export function useTheme(): ThemeCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider');
  return ctx;
}
