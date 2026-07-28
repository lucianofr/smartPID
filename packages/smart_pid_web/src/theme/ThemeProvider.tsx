import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { THEME_IDS, type ContractThemeId } from './contract';

export type ThemeId = ContractThemeId;

export const THEMES: ReadonlyArray<{ id: ThemeId; label: string }> = [
  // The product's own palettes, first because they carry the brand. Everything
  // below them is an instrument skin the operator can fall back to.
  { id: 'optimizer', label: 'Optimizer' },
  { id: 'optimizer-dark', label: 'Optimizer Dark' },
  { id: 'recorder', label: 'Recorder' },
  { id: 'phosphor', label: 'Phosphor' },
  { id: 'isa101', label: 'ISA-101' },
  // §10.2: the siblings are instruments (paper chart recorder, CRT phosphor).
  // Neon breaks that pattern on purpose — it needs no explanation.
  { id: 'neon', label: 'Neon' },
];

export const STORAGE_KEY = 'spid.theme';
/** The design system ships as the product's own face; skins stay opt-in. */
export const DEFAULT_THEME: ThemeId = 'optimizer';

/**
 * §6.8 stored-value migration. Without it a returning user with
 * `spid.theme='ocean'` silently falls to the default constant.
 * Mirrored by the pre-paint script in index.html (test-enforced).
 */
export const LEGACY_THEME_MAP: Readonly<Record<string, ThemeId>> = {
  'dark-room': 'phosphor',
  'md3-dark': 'recorder',
  'md3-light': 'recorder',
  ocean: 'recorder',
};

function isThemeId(v: string | null): v is ThemeId {
  return v !== null && (THEME_IDS as readonly string[]).includes(v);
}

/** Pure resolution: valid passthrough → legacy migration → default. */
export function resolveStoredTheme(raw: string | null): ThemeId {
  if (isThemeId(raw)) return raw;
  if (raw !== null && raw in LEGACY_THEME_MAP) return LEGACY_THEME_MAP[raw];
  return DEFAULT_THEME;
}

function readStored(): ThemeId {
  const raw = localStorage.getItem(STORAGE_KEY);
  const resolved = resolveStoredTheme(raw);
  if (raw !== null && raw !== resolved) {
    localStorage.setItem(STORAGE_KEY, resolved); // migrate once
  }
  return resolved;
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