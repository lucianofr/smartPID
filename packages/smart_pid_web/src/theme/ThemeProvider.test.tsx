import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { act, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { endpoints } from '@/api/endpoints';
import type { MeResponse } from '@/api/types';
import { TestProviders } from '@/test/providers';
import {
  DEFAULT_THEME,
  LEGACY_THEME_MAP,
  STORAGE_KEY,
  THEMES,
  ThemeProvider,
  ThemeSync,
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
  sessionStorage.clear();
  document.documentElement.removeAttribute('data-theme');
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('theme registry (spec §6.8 + §10.2)', () => {
  it('ships the two Optimizer palettes ahead of the four instrument skins', () => {
    expect(THEMES.map((t) => t.id)).toEqual([
      'optimizer', 'optimizer-dark', 'recorder', 'phosphor', 'isa101', 'neon',
    ]);
    expect(THEMES.map((t) => t.label)).toEqual([
      'Optimizer', 'Optimizer Dark', 'Recorder', 'Phosphor', 'ISA-101', 'Neon',
    ]);
    expect(DEFAULT_THEME).toBe('optimizer-dark');
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

  it.each([
    ['optimizer'], ['optimizer-dark'], ['recorder'], ['phosphor'], ['isa101'], ['neon'],
  ] as const)('valid %s passes through', (id) => {
    expect(resolveStoredTheme(id)).toBe(id);
  });

  it('unknown and null fall to optimizer-dark (the product default)', () => {
    expect(resolveStoredTheme('banana')).toBe('optimizer-dark');
    expect(resolveStoredTheme(null)).toBe('optimizer-dark');
  });
});

describe('ThemeProvider behavior', () => {
  it('defaults to optimizer-dark and sets data-theme on <html>', () => {
    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    );
    expect(screen.getByTestId('current').textContent).toBe('optimizer-dark');
    expect(document.documentElement.getAttribute('data-theme')).toBe('optimizer-dark');
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
    expect(html).toContain(
      `['optimizer', 'optimizer-dark', 'recorder', 'phosphor', 'isa101', 'neon']`,
    );
    // The static attribute and the script fallback must agree with DEFAULT_THEME,
    // or a fresh profile flashes one theme and settles on another.
    expect(html).toContain(`<html lang="pt-BR" data-theme="${DEFAULT_THEME}">`);
    expect(html).toContain(`legacy[stored] || '${DEFAULT_THEME}'`);
  });
});

/**
 * The palette is a per-USER preference, not a per-browser one: an operator who
 * signs in at another station must not be handed the default back. localStorage
 * stays the pre-paint cache; `GET /auth/me` is the authority.
 */
describe('ThemeSync — the theme follows the user', () => {
  /** Seeds a resolved session carrying (or not carrying) a stored palette. */
  function renderWithSession(theme: MeResponse['theme']) {
    localStorage.setItem('smart-pid-token', 'jwt');
    const me = vi
      .spyOn(endpoints, 'me')
      .mockResolvedValue({ user_id: 1, username: 'operador', role: 'user', theme });
    render(
      <TestProviders>
        <ThemeSync />
        <Probe />
      </TestProviders>,
    );
    return me;
  }

  it('adopts the stored user palette on login and mirrors it into the cache', async () => {
    const push = vi.spyOn(endpoints, 'setUserTheme').mockResolvedValue(undefined);
    renderWithSession('neon');

    await waitFor(() => expect(screen.getByTestId('current').textContent).toBe('neon'));
    expect(document.documentElement.getAttribute('data-theme')).toBe('neon');
    expect(localStorage.getItem(STORAGE_KEY)).toBe('neon');
    // Adoption is not a change — echoing the server's own value back is a
    // wasted write on every single login.
    expect(push).not.toHaveBeenCalled();
  });

  it('leaves the cached palette alone for a user who never chose one', async () => {
    localStorage.setItem(STORAGE_KEY, 'isa101');
    const push = vi.spyOn(endpoints, 'setUserTheme').mockResolvedValue(undefined);
    const me = renderWithSession(null);

    await waitFor(() => expect(me).toHaveBeenCalled());
    expect(screen.getByTestId('current').textContent).toBe('isa101');
    expect(push).not.toHaveBeenCalled();
  });

  it('pushes a picked palette to the server', async () => {
    const push = vi.spyOn(endpoints, 'setUserTheme').mockResolvedValue(undefined);
    const me = renderWithSession(null);
    await waitFor(() => expect(me).toHaveBeenCalled());

    act(() => {
      screen.getByText('phosphor').click();
    });

    await waitFor(() => expect(push).toHaveBeenCalledWith('phosphor'));
    expect(localStorage.getItem(STORAGE_KEY)).toBe('phosphor');
  });

  it('keeps the picked palette when the server write fails', async () => {
    const push = vi
      .spyOn(endpoints, 'setUserTheme')
      .mockRejectedValue(new Error('offline'));
    const me = renderWithSession(null);
    await waitFor(() => expect(me).toHaveBeenCalled());

    act(() => {
      screen.getByText('phosphor').click();
    });

    await waitFor(() => expect(push).toHaveBeenCalledWith('phosphor'));
    expect(screen.getByTestId('current').textContent).toBe('phosphor');
    expect(document.documentElement.getAttribute('data-theme')).toBe('phosphor');
  });

  it('does not reset the palette on logout', async () => {
    const me = renderWithSession('neon');
    await waitFor(() => expect(me).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByTestId('current').textContent).toBe('neon'));

    // The session ends where the token does; the station keeps its palette.
    expect(localStorage.getItem(STORAGE_KEY)).toBe('neon');
  });
});