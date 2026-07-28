import { expect, test, type Page } from '@playwright/test';
import { FIC101, TIC202, emitFrames, faceplate, gotoDashboard, settleForShot } from './helpers/harness';

// §6.8 + §10 theme matrix. Four themes ship: recorder, phosphor, isa101 and
// neon — neon is the default (§10.2). MD3 dark/light and Ocean are dropped;
// Dark Room is superseded by Phosphor, and stored legacy values migrate rather
// than silently falling back (a stored `ocean` still resolves to recorder).
//
// Visual baseline set: 4 themes x 4 viewports = 16 dashboard PNGs here, plus
// one faceplate PNG in faceplate.spec.ts = 17 total. The obsolete 5x4 matrix
// (ocean / md3-dark / md3-light / dark-room / isa101) was deleted in 7603b80.

const THEMES = ['recorder', 'phosphor', 'isa101', 'neon'] as const;
const LOOPS = [FIC101, TIC202];

const THEME_LABEL: Record<(typeof THEMES)[number], string> = {
  recorder: 'Recorder',
  phosphor: 'Phosphor',
  isa101: 'ISA-101',
  neon: 'Neon',
};

async function selectTheme(page: Page, theme: (typeof THEMES)[number]): Promise<void> {
  await page.getByRole('button', { name: 'Configurações' }).click();
  await page.getByRole('menuitemradio', { name: THEME_LABEL[theme] }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
}

test('neon is the default when nothing is stored', async ({ page }) => {
  await gotoDashboard(page, { loops: LOOPS });
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'neon');
  // The pre-paint script in index.html and the static attribute agree, so the
  // stored value is only written once the operator picks something.
  expect(await page.evaluate(() => localStorage.getItem('spid.theme'))).toBeNull();
});

for (const theme of THEMES) {
  test(`persists an explicit ${theme} selection across a reload`, async ({ page }) => {
    await gotoDashboard(page, { loops: LOOPS });
    await selectTheme(page, theme);

    await page.reload();
    await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
    // The pre-paint script in index.html applies it before React mounts, so the
    // operator never flashes the default first.
    await expect(page.getByText('FIC-101').first()).toBeVisible();
  });

  test(`the dashboard renders under ${theme}`, async ({ page }) => {
    await gotoDashboard(page, { loops: LOOPS, theme });
    await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
    await expect(page.getByText('FIC-101').first()).toBeVisible();
    await expect(page.getByRole('img', { name: 'Tendência FIC-101' })).toBeVisible();
    await expect(faceplate(page, 'FIC-101')).toBeVisible();
    await expect(page.getByRole('button', { name: 'ACK ALL' })).toBeVisible();
  });
}

// §10.5/D12: the halo is "--glow-trace is non-zero", not "the theme is Phosphor".
// Phosphor declares 4px and Neon 8px; Recorder and ISA-101 declare 0px.
const GLOW_TRACE: Record<(typeof THEMES)[number], { token: string; glow: 'on' | 'off' }> = {
  recorder: { token: '0px', glow: 'off' },
  phosphor: { token: '4px', glow: 'on' },
  isa101: { token: '0px', glow: 'off' },
  neon: { token: '8px', glow: 'on' },
};

test('the PV halo follows --glow-trace, in every theme', async ({ page }) => {
  await gotoDashboard(page, { loops: LOOPS, theme: 'phosphor' });

  for (const theme of THEMES) {
    if ((await page.locator('html').getAttribute('data-theme')) !== theme) {
      await selectTheme(page, theme);
    }
    const expected = GLOW_TRACE[theme];
    const token = await page.evaluate(() =>
      getComputedStyle(document.documentElement).getPropertyValue('--glow-trace').trim(),
    );
    expect(token, `${theme} --glow-trace`).toBe(expected.token);
    await expect(
      page.getByRole('img', { name: 'Tendência FIC-101' }),
      `${theme} data-glow`,
    ).toHaveAttribute('data-glow', expected.glow);
  }
});

const LEGACY: ReadonlyArray<readonly [string, string]> = [
  ['dark-room', 'phosphor'],
  ['md3-dark', 'recorder'],
  ['md3-light', 'recorder'],
  ['ocean', 'recorder'],
  ['not-a-theme', 'neon'],
];

for (const [stored, expected] of LEGACY) {
  test(`migrates the stored value ${stored} to ${expected}`, async ({ page }) => {
    await gotoDashboard(page, { loops: LOOPS, theme: stored });
    await expect(page.locator('html')).toHaveAttribute('data-theme', expected);
    const persisted = await page.evaluate(() => localStorage.getItem('spid.theme'));
    expect(persisted, 'the migration is written back once').toBe(expected);
  });
}

// §6.8 terminal visual baselines. Viewport-sized (not full page), matching the
// {width}x900 geometry of the pre-rewrite set. UTC is pinned because uPlot's
// `x: { time: true }` axis formats tick labels in the browser's local zone.
//
// `samples: 0` + emitFrames() puts the frame count entirely under this spec's
// control: the stub's open-time burst races React's mount, so it lands an
// arbitrary 0-2 samples and the recorder draws no stroke at all. 24 frames of
// the deterministic PV/CO excursion give the matrix a real trace, without which
// a §6.3 regression — trace hue, per-series width, or the ISA-only solid SP —
// would slip past all sixteen shots unnoticed.
test.describe('visual baselines', () => {
  test.use({ timezoneId: 'UTC' });

  const WIDTHS = [320, 768, 1024, 1440] as const;
  const FRAMES = 24;
  const SHOT = { loops: LOOPS, samples: 0, wave: 1, height: 900 } as const;

  for (const theme of THEMES) {
    for (const width of WIDTHS) {
      test(`dashboard renders identically under ${theme} at ${width}`, async ({ page }) => {
        await gotoDashboard(page, { ...SHOT, theme, width });
        await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
        await emitFrames(page, FRAMES);
        await settleForShot(page);
        await expect(page).toHaveScreenshot(`dashboard-${theme}-${width}.png`);
      });
    }
  }
});
