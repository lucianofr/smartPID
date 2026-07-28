import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { act, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import {
  DEFAULT_THEME,
  LEGACY_THEME_MAP,
  STORAGE_KEY,
  THEMES,
  ThemeProvider,
  resolveStoredTheme,
  useTheme,
} from './ThemeProvider';

function Probe() {
  const { theme, setTheme, themes } = useTheme();
  return (
    <div>
      <span data-testid="current">{theme}</span>
      <span data-testid="count">{themes.length}</span>
      <button onClick={() => setTheme('phosphor')}>phosphor</button>
    </div>
  );
}

beforeEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute('data-theme');
});

describe('theme registry (spec §6.8 + §10.2)', () => {
  it('ships exactly recorder, phosphor, isa101, neon — neon default', () => {
    expect(THEMES.map((t) => t.id)).toEqual(['recorder', 'phosphor', 'isa101', 'neon']);
    expect(THEMES.map((t) => t.label)).toEqual(['Recorder', 'Phosphor', 'ISA-101', 'Neon']);
    expect(DEFAULT_THEME).toBe('neon');
    expect(STORAGE_KEY).toBe('spid.theme');
  });
});

describe('resolveStoredTheme — every §6.8 migration row', () => {
  it.each([
    ['dark-room', 'phosphor'],
    ['md3-dark', 'recorder'],
    ['md3-light', 'recorder'],
    ['ocean', 'recorder'],
  ] as const)('legacy %s → %s', (legacy, target) => {
    expect(resolveStoredTheme(legacy)).toBe(target);
    expect(LEGACY_THEME_MAP[legacy]).toBe(target);
  });

  it.each([['recorder'], ['phosphor'], ['isa101'], ['neon']] as const)(
    'valid %s passes through',
    (id) => {
      expect(resolveStoredTheme(id)).toBe(id);
    },
  );

  it('unknown and null fall to neon (§10.2 default)', () => {
    expect(resolveStoredTheme('banana')).toBe('neon');
    expect(resolveStoredTheme(null)).toBe('neon');
  });
});

describe('ThemeProvider behavior', () => {
  it('defaults to neon and sets data-theme on <html>', () => {
    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    );
    expect(screen.getByTestId('current').textContent).toBe('neon');
    expect(document.documentElement.getAttribute('data-theme')).toBe('neon');
  });

  it('migrates a legacy stored value ONCE and writes the migrated value back', () => {
    localStorage.setItem(STORAGE_KEY, 'ocean');
    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    );
    expect(screen.getByTestId('current').textContent).toBe('recorder');
    expect(localStorage.getItem(STORAGE_KEY)).toBe('recorder'); // write-back
  });

  it('persists setTheme and applies data-theme', () => {
    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    );
    act(() => {
      screen.getByText('phosphor').click();
    });
    expect(document.documentElement.getAttribute('data-theme')).toBe('phosphor');
    expect(localStorage.getItem(STORAGE_KEY)).toBe('phosphor');
  });

  it('rehydrates a persisted valid theme on remount', () => {
    localStorage.setItem(STORAGE_KEY, 'isa101');
    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    );
    expect(screen.getByTestId('current').textContent).toBe('isa101');
  });
});

describe('index.html pre-paint script stays in sync with LEGACY_THEME_MAP', () => {
  it('contains every mapping row, the valid-id list and the neon fallback', () => {
    const html = readFileSync(resolve(process.cwd(), 'index.html'), 'utf8');
    for (const [legacy, target] of Object.entries(LEGACY_THEME_MAP)) {
      expect(html).toContain(`'${legacy}': '${target}'`);
    }
    expect(html).toContain(`['recorder', 'phosphor', 'isa101', 'neon']`);
    // The static attribute and the script fallback must agree with DEFAULT_THEME,
    // or a fresh profile flashes one theme and settles on another.
    expect(html).toContain(`<html lang="pt-BR" data-theme="${DEFAULT_THEME}">`);
    expect(html).toContain(`legacy[stored] || '${DEFAULT_THEME}'`);
  });
});